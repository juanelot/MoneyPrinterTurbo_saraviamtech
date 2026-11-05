"""Banco de clips: de videos largos (MrBeast, peliculas, series...) salen clips cortos de un plano cada uno que
Claude describe una vez; luego la Fabrica los pone detras de las escenas de ilustracion donde encajan con la frase.

  1. obtener:  enlace (yt-dlp) o archivo subido -> origen.mp4 (hasta 720p; se borra al acabar)
  2. cortar:   cambios de plano de ffmpeg (clonar._planos) -> clips de CLIP_MIN-CLIP_MAX s, sin audio
  3. mirar:    hojas de contacto numeradas (12 fotos cada una)
  4. describir: Claude mira las hojas (Read) y dice que se ve en cada clip (y cuales no sirven: texto, logos, negro)

storage/estudio/banco/<bid>/: sesion.json, clips.json, clips/c001.mp4, fotos/c001.jpg, hojas/h01.jpg
En el guion un clip se nombra "<k>-<n>" (k = posicion del banco en opciones["banco"], n = numero del clip).
El audio original no se usa (encima va la narracion).
"""
import os
import re
import shutil
import threading
import time
import uuid

from loguru import logger

from app.services import claude_cli
from app.services.estudio import almacen, medios

DURACION_MAX = 3 * 3600   # segundos del video de origen
CLIP_MIN, CLIP_MAX = 1.2, 3.0
CLIPS_MAX = 160           # por video: si salen mas planos se reparten
POR_HOJA = 12             # fotos por hoja de contacto (4 x 3)
EN_GUION_MAX = 180        # clips que se le ensenan a Claude al escribir un guion (entre todos los bancos)
MODOS = ("insertos", "mayoria")

_candado = threading.Lock()
_trabajos = {}


def _dir(bid, *partes, crear=False):
    almacen.validar_id(bid)
    ruta = almacen.raiz("banco", bid, *partes)
    if crear:
        os.makedirs(ruta, exist_ok=True)
    return ruta


def _leer(bid):
    s = almacen.leer_json(_dir(bid, "sesion.json"))
    if s is None:
        raise FileNotFoundError("ese video del banco no existe")
    return s


def _guardar(bid, **cambios):
    with _candado:
        s = _leer(bid)
        s.update(cambios, actualizado=time.time())
        almacen.escribir_json(_dir(bid, "sesion.json"), s)
        return s


def listar():
    base = almacen.raiz("banco")
    filas = [almacen.leer_json(os.path.join(base, b, "sesion.json")) for b in (os.listdir(base) if os.path.isdir(base) else [])]
    return sorted([f for f in filas if f], key=lambda s: s.get("creado", 0), reverse=True)


def ver(bid):
    return {**_leer(bid), "clips": almacen.leer_json(_dir(bid, "clips.json"), []) or []}


def _nombre(n):
    return f"c{int(n):03d}"


def ruta_foto(bid, n):
    ruta = _dir(bid, "fotos", _nombre(n) + ".jpg")
    if not os.path.isfile(ruta):
        raise FileNotFoundError("no esta esa foto")
    return ruta


def ruta_clip(bid, n):
    ruta = _dir(bid, "clips", _nombre(n) + ".mp4")
    if not os.path.isfile(ruta):
        raise FileNotFoundError("no esta ese clip")
    return ruta


def borrar(bid):
    if bid in _trabajos and _trabajos[bid].is_alive():
        raise RuntimeError("se esta cortando: espera a que termine")
    shutil.rmtree(_dir(bid), ignore_errors=True)


def quitar_clip(bid, n):
    """Marca un clip como que no sirve (no se le ofrece a Claude)."""
    clips = almacen.leer_json(_dir(bid, "clips.json"), []) or []
    for c in clips:
        if c["n"] == int(n):
            c["sirve"] = not c.get("sirve", True)
    almacen.escribir_json(_dir(bid, "clips.json"), clips)
    return {"clips": clips}


def crear(url="", datos=None, nombre_archivo=""):
    """Empieza a cortar un video (enlace o archivo). El trabajo sigue en segundo plano."""
    url = str(url or "").strip()
    if not url and not datos:
        raise ValueError("pega el enlace del video o sube el archivo")
    if url and not url.startswith("http"):
        url = "https://" + url
    if url and "instagram.com" in url:
        raise ValueError("Instagram no deja bajar videos sin cuenta: descargalo y subelo como archivo")
    bid = uuid.uuid4().hex[:12]
    _dir(bid, crear=True)
    if datos:
        ext = os.path.splitext(nombre_archivo or "")[1].lower() or ".mp4"
        if ext not in (".mp4", ".mov", ".webm", ".mkv", ".m4v", ".avi"):
            shutil.rmtree(_dir(bid), ignore_errors=True)
            raise ValueError("sube un video (mp4, mov, webm, mkv...)")
        with open(_dir(bid, "subido" + ext), "wb") as f:
            f.write(datos)
    almacen.escribir_json(_dir(bid, "sesion.json"), {
        "id": bid, "origen": url or nombre_archivo, "titulo": url or nombre_archivo, "estado": "en cola", "progreso": 0,
        "mensaje": "en cola", "error": None, "creado": time.time(), "actualizado": time.time(), "n_clips": 0})
    hilo = threading.Thread(target=_trabajar_seguro, args=(bid,), daemon=True, name=f"banco-{bid}")
    _trabajos[bid] = hilo
    hilo.start()
    return _leer(bid)


def _trabajar_seguro(bid):
    try:
        _trabajar(bid)
    except Exception as e:  # noqa: BLE001 -- se ve en su tarjeta
        logger.exception(f"banco {bid}")
        _guardar(bid, estado="error", error=str(e)[:500], mensaje="")
    finally:
        origen = _dir(bid, "origen.mp4")
        if os.path.isfile(origen):
            os.remove(origen)


def _trabajar(bid):
    from app.services.estudio import clonar
    s = _leer(bid)
    origen = _dir(bid, "origen.mp4")
    _guardar(bid, estado="descargando", progreso=3, mensaje="bajando el video")
    subido = next((os.path.join(_dir(bid), n) for n in os.listdir(_dir(bid)) if n.startswith("subido.")), None)
    if subido:
        os.replace(subido, origen) if subido.endswith(".mp4") else _a_mp4(subido, origen)
        if os.path.isfile(subido):
            os.remove(subido)
    else:
        titulo = _bajar(s["origen"], origen)
        if titulo:
            _guardar(bid, titulo=titulo[:160])
    info = medios.sondear(origen)
    duracion = float(info.get("duracion") or 0)
    if duracion <= 0:
        raise RuntimeError("no se pudo leer el video")
    if duracion > DURACION_MAX:
        raise ValueError(f"el video dura {duracion / 3600:.1f} h: hasta {DURACION_MAX // 3600} h")
    _guardar(bid, duracion=round(duracion, 1), estado="cortando", progreso=15, mensaje="buscando los cambios de plano")
    clips = _trozos(clonar._planos(origen, duracion))
    if not clips:
        raise RuntimeError("no salieron planos utiles (¿video sin cortes o muy corto?)")
    _dir(bid, "clips", crear=True)
    _dir(bid, "fotos", crear=True)
    for k, c in enumerate(clips):
        if k % 10 == 0:
            _guardar(bid, progreso=15 + round(55 * k / len(clips)), mensaje=f"cortando clip {k + 1} de {len(clips)}")
        _cortar(origen, c, _dir(bid, "clips", _nombre(c["n"]) + ".mp4"), _dir(bid, "fotos", _nombre(c["n"]) + ".jpg"))
    clips = [c for c in clips if os.path.isfile(_dir(bid, "clips", _nombre(c["n"]) + ".mp4"))]
    almacen.escribir_json(_dir(bid, "clips.json"), clips)
    os.remove(origen)
    _guardar(bid, n_clips=len(clips), progreso=72, mensaje="Claude mira los clips y los describe")
    _hojas(bid, clips)
    _describir(bid, clips)
    almacen.escribir_json(_dir(bid, "clips.json"), clips)
    shutil.rmtree(_dir(bid, "hojas"), ignore_errors=True)
    _guardar(bid, estado="listo", progreso=100, mensaje=f"{sum(c.get('sirve', True) for c in clips)} clips listos",
             n_clips=len(clips))


def _a_mp4(entrada, salida):
    r = medios.correr([medios.ffmpeg(), "-hide_banner", "-loglevel", "error", "-y", "-i", entrada, "-an", "-c:v", "libx264",
                       "-preset", "veryfast", "-crf", "22", "-vf", "scale=-2:'min(720,ih)'", salida], timeout=7200)
    if r.returncode != 0 or not os.path.isfile(salida):
        raise RuntimeError(f"no se pudo leer el video: {r.stderr[-300:]}")


def _bajar(url, destino):
    import yt_dlp
    opciones = {"quiet": True, "no_warnings": True, "noprogress": True, "outtmpl": destino[:-4] + ".%(ext)s",
                "merge_output_format": "mp4", "format": "bv*[height<=720][ext=mp4]/bv*[height<=720]/b[height<=720]/b",
                "socket_timeout": 30, "noplaylist": True,
                "match_filter": yt_dlp.utils.match_filter_func(f"duration <= {DURACION_MAX}")}
    with yt_dlp.YoutubeDL(opciones) as y:
        info = y.extract_info(url, download=True)
    bajado = next((os.path.join(os.path.dirname(destino), n) for n in os.listdir(os.path.dirname(destino))
                   if n.startswith("origen.") and not n.endswith((".part", ".ytdl"))), None)
    if not bajado:
        raise RuntimeError("no se pudo bajar el video (¿es privado o dura demasiado?)")
    if bajado != destino:
        _a_mp4(bajado, destino)
        os.remove(bajado)
    return (info or {}).get("title") or ""


def _trozos(planos):
    """Clips de un plano: se salta el borde de cada corte (fundidos) y los planos largos dan dos clips."""
    trozos = []
    for p in planos:
        a, b = p["desde"] + 0.12, p["hasta"] - 0.12
        if b - a < CLIP_MIN:
            continue
        trozos.append((a, min(b, a + CLIP_MAX)))
        if b - a >= 2 * CLIP_MAX + 1:   # plano largo: otro trozo de la mitad en adelante
            m = (a + b) / 2
            trozos.append((m, min(b, m + CLIP_MAX)))
    if len(trozos) > CLIPS_MAX:
        trozos = [trozos[round(k * (len(trozos) - 1) / (CLIPS_MAX - 1))] for k in range(CLIPS_MAX)]
    return [{"n": k + 1, "desde": round(a, 2), "dur": round(b - a, 2), "sirve": True} for k, (a, b) in enumerate(trozos)]


def _cortar(origen, c, salida, foto):
    medios.correr([medios.ffmpeg(), "-hide_banner", "-loglevel", "error", "-y", "-ss", str(c["desde"]), "-i", origen,
                   "-t", str(c["dur"]), "-an", "-vf", "scale=-2:'min(720,ih)'", "-c:v", "libx264", "-preset", "veryfast",
                   "-crf", "20", "-pix_fmt", "yuv420p", salida], timeout=120)
    medios.correr([medios.ffmpeg(), "-hide_banner", "-loglevel", "error", "-y", "-ss", str(round(c["dur"] / 2, 2)), "-i",
                   salida, "-frames:v", "1", "-vf", "scale=320:-2,format=yuvj420p", "-q:v", "5", foto], timeout=60)


def _hojas(bid, clips):
    """Hojas de contacto de POR_HOJA fotos con el numero de cada clip encima (Claude las lee de una en una)."""
    from PIL import Image, ImageDraw, ImageFont
    carpeta = _dir(bid, "hojas", crear=True)
    try:
        fuente = ImageFont.truetype("arial.ttf", 30)
    except OSError:
        fuente = ImageFont.load_default()
    for h in range(0, len(clips), POR_HOJA):
        grupo = clips[h:h + POR_HOJA]
        hoja = Image.new("RGB", (4 * 320, 3 * 200), "black")
        d = ImageDraw.Draw(hoja)
        for k, c in enumerate(grupo):
            x, y = (k % 4) * 320, (k // 4) * 200
            try:
                im = Image.open(_dir(bid, "fotos", _nombre(c["n"]) + ".jpg")).convert("RGB")
                im.thumbnail((316, 196))
                hoja.paste(im, (x + 2 + (316 - im.width) // 2, y + 2 + (196 - im.height) // 2))
            except OSError:
                pass
            d.rectangle((x + 4, y + 4, x + 70, y + 40), fill="#ffd400")
            d.text((x + 10, y + 6), str(c["n"]), font=fuente, fill="black")
        hoja.save(os.path.join(carpeta, f"h{h // POR_HOJA + 1:02d}.jpg"), quality=80)


def _describir(bid, clips):
    s = _leer(bid)
    hojas = sorted(os.listdir(_dir(bid, "hojas")))
    prompt = (
        "Vas a catalogar clips cortos de video (un plano cada uno) para usarlos de fondo en otros videos. "
        f"Video de origen: {s.get('titulo') or '(sin titulo)'}.\n"
        f"Mira con Read TODAS estas hojas de contacto (cada foto lleva su numero en amarillo): "
        f"{', '.join(os.path.abspath(_dir(bid, 'hojas', h)).replace(os.sep, '/') for h in hojas)}.\n"
        "De cada numero di en espanol lo que SE VE (8-14 palabras: quien o que, que hace, donde; sin nombres propios "
        "salvo que salga texto que lo diga) y 2-4 etiquetas cortas (dinero, coche, multitud, reaccion, comida, "
        "naturaleza, ciudad...). Marca sirve=false si el plano no vale como fondo: casi todo texto o titulo, logo o "
        "pantalla de suscribirse, negro, borroso, o una cara gritando a camara sin contexto.\n"
        'Responde SOLO con JSON: {"clips": [{"n": 1, "describe": "...", "etiquetas": ["..."], "sirve": true}]}'
    )
    from app.services.estudio import fabrica
    crudo = fabrica._objeto_json(claude_cli.ejecutar(prompt, modelo="sonnet", esfuerzo="low", tiempo_max_s=900,
                                                     cwd=_dir(bid), permitidas=("Read",)))
    datos = {int(c["n"]): c for c in (crudo or {}).get("clips") or [] if isinstance(c, dict) and str(c.get("n", "")).isdigit()}
    if not datos:
        raise RuntimeError("Claude no describio los clips (prueba otra vez)")
    for c in clips:
        x = datos.get(c["n"]) or {}
        c["describe"] = str(x.get("describe") or "")[:160]
        c["etiquetas"] = [str(t)[:24] for t in (x.get("etiquetas") or [])[:4]]
        c["sirve"] = bool(x.get("sirve", True)) and bool(c["describe"])


# ------------------------------------------------------------------ para la Fabrica

def para_guion(bids, modo):
    """La lista de clips para el prompt del guion ("" si no hay)."""
    filas = []
    for k, bid in enumerate(bids, 1):
        try:
            clips = almacen.leer_json(_dir(bid, "clips.json"), []) or []
        except ValueError:
            continue
        filas += [f"{k}-{c['n']}: {c['describe']}" for c in clips if c.get("sirve", True) and c.get("describe")]
    if not filas:
        return ""
    if len(filas) > EN_GUION_MAX:
        filas = [filas[round(i * (len(filas) - 1) / (EN_GUION_MAX - 1))] for i in range(EN_GUION_MAX)]
    cuanto = ("en la MAYORIA del video: al menos 2 de cada 3 escenas (sin contar la portada) son 'ilustracion' con "
              "clip; cifras, listas y graficas solo cuando el dato no se entiende sin ellas (como mucho 1 de cada 3 "
              "escenas), y el numero fuerte puede ir de 'golpe' encima del clip" if modo == "mayoria" else
              "solo en 1 de cada 3 escenas 'ilustracion' mas o menos, donde de verdad pegue con la frase (insertos)")
    return ("CLIPS DE VIDEO REALES (id: lo que se ve). Una escena 'ilustracion' puede llevar \"clip\": \"id\" y entonces "
            "se ve ese clip detras de sus textos en vez de una imagen (no pongas 'nueva' ni 'imagen' en esa escena). "
            f"Ponlos {cuanto}. El clip tiene que pegar con lo que dice la frase (accion, emocion o cosa); no repitas "
            "un clip en el mismo video, y como los numeros seguidos son del mismo momento del original (y una escena "
            "larga sigue con los siguientes), deja al menos 6 numeros entre dos clips del mismo video.\n" + "\n".join(filas) + "\n\n")


def resolver(bids, ref):
    """'k-n' -> (bid, n) o None."""
    m = re.fullmatch(r"\s*(\d+)\s*-\s*(\d+)\s*", str(ref or ""))
    if not m or not 1 <= int(m.group(1)) <= len(bids):
        return None
    bid, n = bids[int(m.group(1)) - 1], int(m.group(2))
    try:
        ruta_clip(bid, n)
    except (FileNotFoundError, ValueError):
        return None
    return bid, n


def armar(bid, n, dur, destino):
    """El clip n alargado hasta dur con los siguientes clips del mismo video (planos seguidos del original)."""
    clips = {c["n"]: c for c in almacen.leer_json(_dir(bid, "clips.json"), []) or []}
    # sigue con los planos de despues (los que no sirven se saltan: textos, pantalla final) y, si se acaban, de antes
    orden = [n] + [k for k in sorted(clips) if k > n] + [k for k in sorted(clips, reverse=True) if k < n]
    partes, total = [], 0.0
    for k in orden:
        if total >= dur or len(partes) >= 8:
            break
        if k != n and not clips[k].get("sirve", True):
            continue
        partes.append(ruta_clip(bid, k))
        total += clips[k]["dur"]
    if not partes:
        raise FileNotFoundError("ese clip ya no esta en el banco")
    entradas = [x for p in partes for x in ("-i", p)]
    filtro = "".join(f"[{i}:v]scale=-2:720,setsar=1,fps=30[v{i}];" for i in range(len(partes))) \
        + "".join(f"[v{i}]" for i in range(len(partes))) + f"concat=n={len(partes)}:v=1:a=0[v]"
    r = medios.correr([medios.ffmpeg(), "-hide_banner", "-loglevel", "error", "-y", *entradas, "-filter_complex", filtro,
                       "-map", "[v]", "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p",
                       destino], timeout=300)
    if r.returncode != 0 or not os.path.isfile(destino):
        raise RuntimeError(f"no se pudo armar el clip: {r.stderr[-200:]}")
    return destino
