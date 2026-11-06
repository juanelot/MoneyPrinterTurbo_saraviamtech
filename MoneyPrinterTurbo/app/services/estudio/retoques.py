"""
Retoques de la voz desde el editor: una parte de la narracion dicha de otra forma
sin rehacer la voz entera (rehacerla cambiaria sus tiempos: Claude volveria a
asignar los clips y se perderian los cortes y todo lo editado).

  reescribir(pid, desde, hasta, texto, pedido)  Claude propone otros textos para ese
      tramo, con un presupuesto de palabras para que quepan en el mismo hueco.
  grabar(pid, desde, hasta, texto)  lo sintetiza con la voz del proyecto (TTS o
      clon) en voz/retoques/<huella>.mp3 y dice cuanto mide y si cabe.

En el render (render.voz_parches: [{desde, hasta, archivo, texto}], en tiempo de la
voz) cada parche sustituye ese tramo, encajado en la MISMA duracion: si es mas
largo se acelera hasta FACTOR_MAX; si es mas corto, sigue a su ritmo y el resto es
silencio. Nada se corre: planos, cortes, subtitulos y capas siguen donde estaban.
"""
import hashlib
import os
import shutil
import tempfile

from loguru import logger

from app.services import claude_cli
from app.services.estudio import almacen, grafo, guion, medios, voz

FACTOR_MAX = 1.3   # cuanto se puede acelerar un retoque para que quepa (mas ya se nota)
MAX_LETRAS = 600


class _Ctx:
    """Lo que piden las funciones de voz.py, apuntando a una carpeta temporal (asi no
    tocan voz/voz.mp3 ni voz/palabras.json)."""

    def __init__(self, proyecto, carpeta):
        self.proyecto = proyecto
        self.params = grafo.params_efectivos(proyecto, "voz")
        self._carpeta = carpeta

    def dir(self, *partes, crear=True):
        return self._carpeta

    def params_de(self, etapa):
        return grafo.params_efectivos(self.proyecto, etapa)

    def avisar(self, mensaje=None, progreso=None):
        pass


def _proyecto(pid):
    proyecto = almacen.cargar(pid)
    v = str(grafo.params_efectivos(proyecto, "voz").get("voz") or "")
    if v == voz.SIN_VOZ or v.startswith(voz.PROPIA):
        raise ValueError("con una narracion propia o sin voz no se puede regrabar una parte: "
                         "sube otra grabacion o cambia la voz a una sintetica")
    return proyecto


def _tramo(desde, hasta):
    a, b = float(desde), float(hasta)
    if a < 0 or b - a < 0.3:
        raise ValueError("el tramo es demasiado corto")
    return round(a, 3), round(b, 3)


def palabras_que_caben(proyecto, segundos):
    idioma = str(grafo.params_efectivos(proyecto, "guion").get("idioma") or "es").split("-")[0]
    vel = float(grafo.params_efectivos(proyecto, "voz").get("velocidad") or 1.0)
    return max(1, round(segundos * guion.PALABRAS_POR_SEGUNDO.get(idioma, 2.5) * vel))


def reescribir(pid, desde, hasta, texto, pedido=""):
    """Tres textos para ese tramo (lo que se dice ahora + el pedido de la persona)."""
    proyecto = _proyecto(pid)
    a, b = _tramo(desde, hasta)
    n = palabras_que_caben(proyecto, b - a)
    g = grafo.params_efectivos(proyecto, "guion")
    idioma = guion.NOMBRE_IDIOMA.get(str(g.get("idioma") or "es").split("-")[0], "espanol")
    estado = almacen.cargar_estado(pid)
    completo = ((estado["etapas"].get("guion") or {}).get("salida") or {}).get("texto", "")
    prompt = (
        f"Eres guionista de videos cortos. Reescribe SOLO este fragmento de una locucion en {idioma}.\n"
        f"Guion completo (contexto, no lo repitas):\n\"\"\"{completo[:3000]}\"\"\"\n\n"
        f"Fragmento actual: \"{texto.strip()[:MAX_LETRAS]}\"\n"
        f"Pedido: {pedido.strip()[:300] or 'que suene mas claro y con mas fuerza, sin cambiar la idea'}\n"
        f"Debe caber en {b - a:.1f} s: como mucho {n} palabras (mejor {max(1, n - 2)}-{n}).\n"
        "Tiene que encajar con lo que va antes y despues. Sin comillas, sin emojis, sin hashtags.\n"
        'Responde SOLO con una lista JSON de tres textos: ["...", "...", "..."]'
    )
    datos = claude_cli.extraer_json(claude_cli.ejecutar(prompt, modelo="sonnet", esfuerzo="low", tiempo_max_s=120))
    if isinstance(datos, dict):
        datos = datos.get("opciones")
    opciones = [" ".join(str(x).split()) for x in datos or [] if isinstance(x, str) and x.strip()]
    if not opciones:
        raise RuntimeError("Claude no propuso ningun texto")
    return {"opciones": opciones[:3], "palabras": n}


def grabar(pid, desde, hasta, texto):
    """Sintetiza `texto` con la voz del proyecto. Se reutiliza si ya se grabo igual."""
    proyecto = _proyecto(pid)
    a, b = _tramo(desde, hasta)
    texto = " ".join(str(texto or "").split())[:MAX_LETRAS]
    if not texto:
        raise ValueError("escribe lo que debe decir")
    p = grafo.params_efectivos(proyecto, "voz")
    huella = hashlib.sha1(repr((p.get("voz"), p.get("velocidad"), texto)).encode()).hexdigest()[:16]
    rel = f"voz/retoques/{huella}.mp3"
    destino = almacen.dir_proyecto(pid, "voz", "retoques", crear=True)
    final = os.path.join(destino, f"{huella}.mp3")
    if not os.path.isfile(final):
        tmp = tempfile.mkdtemp(prefix="retoque_", dir=destino)
        try:
            ctx = _Ctx(proyecto, tmp)
            audio, srt = os.path.join(tmp, "voz.mp3"), os.path.join(tmp, "voz.srt")
            voz._voz_tts(ctx, texto, audio, srt)
            _recortar_silencios(audio, final)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
    dur = float(medios.sondear(final).get("duracion") or 0)
    hueco = b - a
    factor = round(max(1.0, dur / hueco), 3)
    cabe = factor <= FACTOR_MAX
    sobran = 0
    if not cabe:  # cuantas palabras habria que quitar, a ojo
        sobran = max(1, round(len(texto.split()) * (1 - FACTOR_MAX * hueco / dur)))
    return {"archivo": rel, "duracion": round(dur, 3), "factor": factor, "cabe": cabe, "sobran": sobran,
            "texto": texto, "desde": a, "hasta": b}


def _recortar_silencios(origen, destino):
    """Sin el silencio del principio y del final (el hueco ya trae sus pausas)."""
    filtro = ("silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.05,"
              "areverse,silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.08,areverse")
    r = medios.correr([medios.ffmpeg(), "-hide_banner", "-loglevel", "error", "-y", "-i", origen, "-af", filtro,
                       "-ar", "44100", "-c:a", "libmp3lame", "-q:a", "2", destino], timeout=300)
    if r.returncode != 0 or not os.path.isfile(destino):
        logger.warning(f"retoque: no se pudieron recortar los silencios ({r.stderr[-200:]})")
        shutil.copyfile(origen, destino)


def validos(pid, parches, dur_voz):
    """Los parches que existen en disco y caen dentro de la voz, sin pisarse (gana el ultimo)."""
    salida = []
    for x in reversed(parches if isinstance(parches, list) else []):
        if not isinstance(x, dict):
            continue
        try:
            a, b = round(float(x["desde"]), 3), round(min(float(x["hasta"]), dur_voz), 3)
        except (KeyError, TypeError, ValueError):
            continue
        archivo = str(x.get("archivo") or "")
        try:
            ruta = almacen.dentro_de(almacen.dir_proyecto(pid, "voz", "retoques"), archivo[len("voz/retoques/"):])
        except ValueError:
            ruta = None
        if not archivo.startswith("voz/retoques/"):
            ruta = None
        if b - a < 0.3 or not ruta or not os.path.isfile(ruta):
            continue
        if any(a < y["hasta"] and y["desde"] < b for y in salida):
            continue
        salida.append({"desde": a, "hasta": b, "ruta": ruta})
    return sorted(salida, key=lambda y: y["desde"])


def aplicar(voz_audio, parches, destino):
    """La voz con cada parche en su hueco: el original se calla ahi y suena el retoque,
    acelerado si hace falta para que no pase de `hasta`."""
    ff = medios.ffmpeg()
    args = [ff, "-hide_banner", "-loglevel", "error", "-y", "-i", voz_audio]
    callar = "+".join(f"between(t,{x['desde']:.3f},{x['hasta']:.3f})" for x in parches)
    filtros = [f"[0:a]aresample=44100,aformat=channel_layouts=stereo,volume=0:enable='{callar}'[v]"]
    nombres = ["[v]"]
    for k, x in enumerate(parches, start=1):
        hueco = x["hasta"] - x["desde"]
        dur = float(medios.sondear(x["ruta"]).get("duracion") or hueco)
        factor = min(FACTOR_MAX, max(1.0, dur / hueco))
        args += ["-i", x["ruta"]]
        filtros.append(f"[{k}:a]aresample=44100,aformat=channel_layouts=stereo,"
                       + (f"atempo={factor:.4f}," if factor > 1.001 else "")
                       + f"atrim=0:{hueco:.3f},afade=t=out:st={max(0, hueco - 0.06):.3f}:d=0.06,"
                       f"adelay={int(x['desde'] * 1000)}:all=1[p{k}]")
        nombres.append(f"[p{k}]")
    filtros.append("".join(nombres) + f"amix=inputs={len(nombres)}:duration=first:dropout_transition=0:normalize=0[a]")
    r = medios.correr(args + ["-filter_complex", ";".join(filtros), "-map", "[a]", "-ar", "44100",
                              "-c:a", "pcm_s16le", destino], timeout=900)
    if r.returncode != 0 or not os.path.isfile(destino):
        raise RuntimeError(f"no se pudieron poner los retoques de la voz: {r.stderr[-400:]}")
    return destino
