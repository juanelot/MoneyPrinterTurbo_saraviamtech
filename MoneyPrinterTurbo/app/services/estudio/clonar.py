"""Clonar video: de un video que funciona se saca su "receta" (gancho, bloques, tipos de plano y ritmo) para rehacerlo
con otro tema, otro formato o otro estilo en la Fabrica. Idea de hypit-ai/hypit (licencia con condiciones: solo la
idea; el codigo es nuestro).

  1. obtener:  enlace (yt-dlp, sin cuenta: YouTube, TikTok...) o archivo subido -> origen.mp4
  2. escuchar: Whisper -> cada palabra con su segundo (puede no haber voz: solo musica)
  3. cortar:   ffmpeg detecta los cambios de plano -> planos [(desde, hasta)]
  4. mirar:    un fotograma por plano (y tres del gancho) en fotos/
  5. receta:   Claude mira los fotogramas (Read) y el texto de cada plano y devuelve la receta (receta.json)

storage/estudio/clones/<cid>/: sesion.json, origen.mp4, palabras.json, planos.json, fotos/*.jpg, receta.json
Replicar = un video de la Fabrica con opciones["receta"] = cid (fabrica._guion sigue la estructura).
"""
import json
import os
import re
import shutil
import threading
import time
import uuid

from loguru import logger

from app.services import claude_cli
from app.services.estudio import almacen, medios

DURACION_MAX = 300    # segundos del video de referencia
FOTOS_MAX = 36        # fotogramas que mira Claude (si hay mas planos, se reparten)
UMBRAL_CORTE = 0.3    # sensibilidad del detector de planos de ffmpeg
TIPOS_PLANO = ("persona_hablando", "broll", "texto", "grafico", "ranking", "lista", "captura", "mapa", "meme", "producto")

_candado = threading.Lock()
_trabajos = {}


def _dir(cid, *partes, crear=False):
    almacen.validar_id(cid)
    ruta = almacen.raiz("clones", cid, *partes)
    if crear:
        os.makedirs(ruta, exist_ok=True)
    return ruta


def _leer(cid):
    s = almacen.leer_json(_dir(cid, "sesion.json"))
    if s is None:
        raise FileNotFoundError("ese clon no existe")
    return s


def _guardar(cid, **cambios):
    with _candado:
        s = _leer(cid)
        s.update(cambios, actualizado=time.time())
        almacen.escribir_json(_dir(cid, "sesion.json"), s)
        return s


def listar():
    base = almacen.raiz("clones")
    filas = [almacen.leer_json(os.path.join(base, c, "sesion.json")) for c in (os.listdir(base) if os.path.isdir(base) else [])]
    return sorted([f for f in filas if f], key=lambda s: s.get("creado", 0), reverse=True)


def ver(cid):
    return {**_leer(cid), "receta": almacen.leer_json(_dir(cid, "receta.json")),
            "planos": almacen.leer_json(_dir(cid, "planos.json"), []) or []}


def ruta_foto(cid, nombre):
    if not re.fullmatch(r"[a-z0-9_]{1,20}\.jpg", nombre or ""):
        raise FileNotFoundError("foto no valida")
    ruta = _dir(cid, "fotos", nombre)
    if not os.path.isfile(ruta):
        raise FileNotFoundError("no esta esa foto")
    return ruta


def borrar(cid):
    if cid in _trabajos and _trabajos[cid].is_alive():
        raise RuntimeError("se esta analizando: espera a que termine")
    shutil.rmtree(_dir(cid), ignore_errors=True)


def crear(url="", datos=None, nombre_archivo=""):
    """Empieza a analizar un video (enlace o archivo). Devuelve la sesion; el analisis sigue en segundo plano."""
    url = str(url or "").strip()
    if not url and not datos:
        raise ValueError("pega el enlace del video o sube el archivo")
    if url and not url.startswith("http"):
        url = "https://" + url
    if url and "instagram.com" in url:
        raise ValueError("Instagram no deja bajar videos sin cuenta: descargalo y subelo como archivo")
    cid = uuid.uuid4().hex[:12]
    _dir(cid, crear=True)
    if datos:
        ext = os.path.splitext(nombre_archivo or "")[1].lower() or ".mp4"
        if ext not in (".mp4", ".mov", ".webm", ".mkv", ".m4v"):
            shutil.rmtree(_dir(cid), ignore_errors=True)
            raise ValueError("sube un video (mp4, mov, webm...)")
        with open(_dir(cid, "subido" + ext), "wb") as f:
            f.write(datos)
    almacen.escribir_json(_dir(cid, "sesion.json"), {
        "id": cid, "origen": url or nombre_archivo, "titulo": url or nombre_archivo, "estado": "en cola", "progreso": 0,
        "mensaje": "en cola", "error": None, "creado": time.time(), "actualizado": time.time()})
    hilo = threading.Thread(target=_analizar_seguro, args=(cid,), daemon=True, name=f"clon-{cid}")
    _trabajos[cid] = hilo
    hilo.start()
    return _leer(cid)


def _analizar_seguro(cid):
    try:
        _analizar(cid)
    except Exception as e:  # noqa: BLE001 -- se ve en su tarjeta
        logger.exception(f"clon {cid}")
        _guardar(cid, estado="error", error=str(e)[:500], mensaje="")


def _analizar(cid):
    s = _leer(cid)
    origen = _dir(cid, "origen.mp4")
    # 1. obtener
    _guardar(cid, estado="descargando", progreso=5, mensaje="bajando el video")
    subido = next((os.path.join(_dir(cid), n) for n in os.listdir(_dir(cid)) if n.startswith("subido.")), None)
    if subido:
        _a_mp4(subido, origen)
        os.remove(subido)
    else:
        titulo = _bajar(s["origen"], origen)
        if titulo:
            _guardar(cid, titulo=titulo[:160])
    info = medios.sondear(origen)
    duracion = float(info.get("duracion") or 0)
    if duracion <= 0:
        raise RuntimeError("no se pudo leer el video")
    if duracion > DURACION_MAX:
        raise ValueError(f"el video dura {duracion / 60:.1f} min: para clonar, hasta {DURACION_MAX // 60} min")
    ancho, alto = int(info.get("ancho") or 0), int(info.get("alto") or 0)
    _guardar(cid, duracion=round(duracion, 2), formato="9:16" if alto > ancho * 1.2 else "1:1" if alto > ancho * 0.85 else "16:9")
    # 2. escuchar
    _guardar(cid, estado="analizando", progreso=20, mensaje="escuchando lo que se dice (Whisper)")
    palabras = _escuchar(cid, origen)
    almacen.escribir_json(_dir(cid, "palabras.json"), palabras)
    # 3. cortar
    _guardar(cid, progreso=45, mensaje="buscando los cortes de plano")
    planos = _planos(origen, duracion)
    for p in planos:
        p["texto"] = " ".join(w[2] for w in palabras if p["desde"] - 0.05 <= w[0] < p["hasta"])
    # 4. mirar
    _guardar(cid, progreso=55, mensaje=f"{len(planos)} planos: sacando fotogramas")
    _fotos(origen, planos)
    almacen.escribir_json(_dir(cid, "planos.json"), planos)
    # 5. receta
    _guardar(cid, progreso=65, mensaje="Claude mira el video y saca la receta")
    receta = _receta(cid, s, duracion, palabras, planos)
    almacen.escribir_json(_dir(cid, "receta.json"), receta)
    _guardar(cid, estado="listo", progreso=100, mensaje="receta lista", titulo=receta.get("titulo") or _leer(cid)["titulo"])


def _a_mp4(entrada, salida):
    r = medios.correr([medios.ffmpeg(), "-hide_banner", "-loglevel", "error", "-y", "-i", entrada, "-c:v", "libx264",
                       "-preset", "veryfast", "-crf", "23", "-vf", "scale='min(1080,iw)':-2", "-c:a", "aac", salida], timeout=900)
    if r.returncode != 0 or not os.path.isfile(salida):
        raise RuntimeError(f"no se pudo leer el video: {r.stderr[-300:]}")


def _bajar(url, destino):
    import yt_dlp
    plantilla = destino[:-4] + ".%(ext)s"
    opciones = {"quiet": True, "no_warnings": True, "noprogress": True, "outtmpl": plantilla, "merge_output_format": "mp4",
                "format": "bv*[height<=1080][ext=mp4]+ba[ext=m4a]/b[height<=1080][ext=mp4]/bv*[height<=1080]+ba/b",
                "socket_timeout": 30, "noplaylist": True,
                "match_filter": yt_dlp.utils.match_filter_func(f"duration <= {DURACION_MAX}")}
    with yt_dlp.YoutubeDL(opciones) as y:
        info = y.extract_info(url, download=True)
    bajado = next((os.path.join(os.path.dirname(destino), n) for n in os.listdir(os.path.dirname(destino))
                   if n.startswith("origen.") and not n.endswith((".part", ".ytdl"))), None)
    if not bajado:
        raise RuntimeError("no se pudo bajar el video (¿dura mas de 5 min o es privado?)")
    if bajado != destino:
        _a_mp4(bajado, destino)
        os.remove(bajado)
    return (info or {}).get("title") or ""


def _escuchar(cid, origen):
    """[(inicio, fin, palabra)]; [] si no se habla."""
    from app.services.estudio import fabrica
    wav = _dir(cid, "audio.wav")
    medios.correr([medios.ffmpeg(), "-hide_banner", "-loglevel", "error", "-y", "-i", origen, "-vn", "-ac", "1",
                   "-ar", "16000", wav], timeout=600)
    if not os.path.isfile(wav):
        return []
    try:
        segmentos, _info = fabrica._modelo_fino().transcribe(wav, word_timestamps=True, vad_filter=True, beam_size=5)
        return [[round(float(w.start), 3), round(float(w.end), 3), w.word.strip()]
                for seg in segmentos for w in (seg.words or []) if w.word.strip()]
    finally:
        os.remove(wav)


def _planos(origen, duracion):
    """Cortes de plano de ffmpeg (los que estan a menos de 0,4 s del anterior se juntan)."""
    r = medios.correr([medios.ffmpeg(), "-hide_banner", "-i", origen, "-vf", f"select='gt(scene,{UMBRAL_CORTE})',showinfo",
                       "-an", "-f", "null", "-"], timeout=900)
    cortes = [0.0]
    for t in sorted(float(x) for x in re.findall(r"pts_time:([\d.]+)", r.stderr or "")):
        if t - cortes[-1] >= 0.4 and duracion - t >= 0.3:
            cortes.append(round(t, 3))
    cortes.append(round(duracion, 3))
    return [{"n": k + 1, "desde": a, "hasta": b, "foto": f"p{k + 1:02d}.jpg"} for k, (a, b) in enumerate(zip(cortes, cortes[1:]))]


def _fotos(origen, planos):
    """Un fotograma (360 px) de la mitad de cada plano, y tres del gancho (0,3 / 1,2 / 2,5 s)."""
    carpeta = os.path.join(os.path.dirname(origen), "fotos")
    os.makedirs(carpeta, exist_ok=True)
    elegidos = planos if len(planos) <= FOTOS_MAX else [planos[round(k * (len(planos) - 1) / (FOTOS_MAX - 1))] for k in range(FOTOS_MAX)]
    tareas = [(round((p["desde"] + p["hasta"]) / 2, 2), p["foto"]) for p in elegidos]
    tareas += [(t, f"g{k + 1}.jpg") for k, t in enumerate((0.3, 1.2, 2.5)) if t < planos[-1]["hasta"]]
    for t, nombre in tareas:
        medios.correr([medios.ffmpeg(), "-hide_banner", "-loglevel", "error", "-y", "-ss", str(t), "-i", origen,
                       "-frames:v", "1", "-vf", "scale=360:-2,format=yuvj420p", "-q:v", "5", os.path.join(carpeta, nombre)], timeout=60)
    for p in planos:
        p["foto"] = p["foto"] if os.path.isfile(os.path.join(carpeta, p["foto"])) else None


def _receta(cid, s, duracion, palabras, planos):
    from app.services.estudio import fabrica
    con_foto = [p for p in planos if p.get("foto")]
    lineas = "\n".join(f"- plano {p['n']} ({p['desde']:.1f}-{p['hasta']:.1f} s)"
                       + (f" [foto fotos/{p['foto']}]" if p.get("foto") else "") + f": «{p['texto']}»" for p in planos)
    gancho = [f"fotos/g{k}.jpg" for k in (1, 2, 3) if os.path.isfile(_dir(cid, "fotos", f"g{k}.jpg"))]
    cortes_min = round(len(planos) / max(duracion / 60, 0.01), 1)
    prompt = (
        "Eres analista de videos virales. Tienes un video que funciono y hay que sacar su RECETA para rehacerlo con otro "
        "tema y otro formato sin copiarlo.\n"
        f"Titulo: {s.get('titulo') or '(sin titulo)'}\nDuracion: {duracion:.1f} s, {len(planos)} planos "
        f"({cortes_min} cortes por minuto).\n"
        f"Lo que se dice: «{' '.join(w[2] for w in palabras) or '(no se habla: solo musica o texto en pantalla)'}»\n\n"
        f"Planos (mira las fotos con Read; {len(con_foto)} fotos):\n{lineas}\n"
        f"Fotos del gancho (primeros 3 s): {', '.join(gancho) or '(ninguna)'}\n\n"
        "Mira TODAS las fotos antes de responder. Explica la estructura con huecos ([tema], [cifra], [persona]...) para "
        "poder rellenarla con otro tema. Tipos de plano: " + ", ".join(TIPOS_PLANO) + ".\n"
        f"Nichos de nuestra Fabrica: {', '.join(fabrica.NICHOS)}.\n"
        'Responde SOLO con JSON: {"titulo": "de que va en 5-8 palabras", "resumen": "2 frases", '
        '"gancho": {"texto": "lo que dice o pone en los 3 primeros s", "visual": "lo que se ve", '
        '"tipo": "pregunta|dato|polemica|promesa|historia|reto", "patron": "el gancho con huecos"}, '
        '"por_que_funciona": ["3-5 motivos concretos"], '
        '"estructura": [{"bloque": "gancho|contexto|desarrollo|giro|lista|revelacion|cierre|llamada", "desde": s, '
        '"hasta": s, "que_pasa": "1 frase", "patron": "lo que se dice con huecos"}], '
        '"planos": [{"n": 1, "tipo": "uno de los tipos", "describe": "lo que se ve, 1 frase", "texto_pantalla": "o vacio"}], '
        '"subtitulos": "como son (tamano, color, palabra a palabra...)", "efectos": ["zoom de golpe", "flash", ...], '
        '"musica": "tipo y energia", "nicho_sugerido": "uno de los nichos", '
        '"temas_parecidos": ["3 temas que encajarian en esta receta"]}'
    )
    crudo = fabrica._objeto_json(claude_cli.ejecutar(prompt, modelo="sonnet", esfuerzo="low", tiempo_max_s=600,
                                                     cwd=_dir(cid), permitidas=("Read",)))
    if not isinstance(crudo, dict) or not crudo.get("estructura"):
        raise RuntimeError("Claude no devolvio la receta (prueba otra vez)")
    tipos = {p.get("n"): p for p in crudo.get("planos") or [] if isinstance(p, dict)}
    for p in planos:   # el tipo de cada plano, junto a sus tiempos
        t = tipos.get(p["n"]) or {}
        p.update(tipo=t.get("tipo") if t.get("tipo") in TIPOS_PLANO else "broll", describe=str(t.get("describe") or "")[:200],
                 texto_pantalla=str(t.get("texto_pantalla") or "")[:120])
    almacen.escribir_json(_dir(cid, "planos.json"), planos)
    nicho = crudo.get("nicho_sugerido") if crudo.get("nicho_sugerido") in fabrica.NICHOS else "curiosidades"
    return {**{k: crudo.get(k) for k in ("titulo", "resumen", "gancho", "por_que_funciona", "estructura", "subtitulos",
                                         "efectos", "musica", "temas_parecidos")},
            "nicho_sugerido": nicho, "duracion": round(duracion, 1), "formato": _leer(cid).get("formato"),
            "ritmo": {"planos": len(planos), "cortes_por_minuto": cortes_min,
                      "plano_medio_s": round(duracion / max(1, len(planos)), 2)},
            "palabras_por_segundo": round(len(palabras) / max(duracion, 0.1), 2)}


def para_guion(cid):
    """La receta resumida para el prompt del guion de la Fabrica."""
    r = almacen.leer_json(_dir(cid, "receta.json"))
    if not r:
        raise FileNotFoundError("ese clon aun no tiene receta")
    planos = almacen.leer_json(_dir(cid, "planos.json"), []) or []
    tipos = {}
    for p in planos:
        tipos[p.get("tipo", "broll")] = tipos.get(p.get("tipo", "broll"), 0) + 1
    bloques = "\n".join(f"  - {b.get('bloque')} ({b.get('desde')}-{b.get('hasta')} s): {b.get('que_pasa')} | patron: {b.get('patron')}"
                        for b in r.get("estructura") or [] if isinstance(b, dict))
    return (f"RECETA A CLONAR (de un video que funciono: «{r.get('titulo')}», {r.get('duracion')} s):\n"
            f"- Gancho ({(r.get('gancho') or {}).get('tipo')}): patron «{(r.get('gancho') or {}).get('patron')}»; "
            f"se ve: {(r.get('gancho') or {}).get('visual')}\n"
            f"- Por que funciona: {'; '.join(map(str, r.get('por_que_funciona') or []))}\n"
            f"- Estructura (respeta el orden y la proporcion de tiempo de cada bloque):\n{bloques}\n"
            f"- Ritmo: un plano cada {r['ritmo']['plano_medio_s']} s ({r['ritmo']['cortes_por_minuto']} cortes/min): "
            f"escenas igual de cortas; tipos de plano: {json.dumps(tipos, ensure_ascii=False)} "
            "(persona_hablando/broll -> ilustracion o protagonista; texto -> golpe o cifra; ranking/lista -> lista o barras; "
            "grafico -> barras, versus o cifra; mapa -> mapa; captura de pantalla, tuit, noticia, chat -> captura)\n"
            f"- Efectos y subtitulos del original: {', '.join(map(str, r.get('efectos') or []))}; {r.get('subtitulos')}. "
            "Imita sus efectos con los 'extras' (emoji de reaccion, sello, flecha) en los mismos momentos fuertes\n"
            "Copia la ESTRUCTURA, el tipo de gancho y el ritmo; el contenido es del tema nuevo (nunca sus frases).\n\n")
