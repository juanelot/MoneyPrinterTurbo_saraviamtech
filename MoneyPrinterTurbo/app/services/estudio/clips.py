"""
Clip Studio: de un video largo (podcast, entrevista, directo) a shorts.

  1. Se sube el video: storage/estudio/clips/<cid>/original.<ext>.
  2. Whisper lo transcribe con el tiempo de cada palabra y se parte en FRASES
     (por puntuacion, pausas o largo): palabras.json y frases.json.
  3. Claude propone los mejores momentos (titulo, gancho, nota, por que), siempre
     de frase completa a frase completa: propuestas.json. Los largos se leen por
     ventanas y se quedan los de mejor nota.
  4. Cada clip se exporta en vertical (9:16): recorte por donde diga `encuadre_x`
     (0 izquierda, 1 derecha), el video entero sobre un fondo desenfocado o
     "documental" (para videos sin rostro: el dibujo grande en el centro, el gancho
     arriba y los subtitulos debajo), con subtitulos palabra por palabra.
     `banda` (0-0.35) quita abajo los subtitulos que el original ya trae grabados.
     `broll` ("" todo del video | pexels | banco | ambos): Claude (haiku, una llamada corta)
     elige frases que ganan con un plano de otra fuente (que buscar en Pexels o un clip de
     los bancos de la Fabrica) y lo pone encima 2-3 s (la voz sigue).

Cada sesion tiene sesion.json con su estado (transcribiendo, listo, proponiendo,
error) y los trabajos van en hilos: la interfaz consulta el estado.
"""
import hashlib
import json
import os
import re
import shutil
import threading
import time
import uuid

from loguru import logger

from app.models.schema import VideoAspect
from app.services import claude_cli, material
from app.services.estudio import acabado, almacen, banco, medios, voz
from app.utils import utils

EXTENSIONES = {".mp4", ".mov", ".mkv", ".webm", ".m4v", ".avi"}
FRASE_MAX_PALABRAS = 22
PAUSA_FRASE_S = 0.7
VENTANA_FRASES = 260   # frases por llamada a Claude en videos largos
DURACIONES = {"corto": (15, 35), "medio": (30, 60), "largo": (55, 90)}
VERSION_EXPORT = 2
ENCUADRES = ("recortar", "ajustar", "documental")
BROLL_CADA_S = 12   # un plano de B-roll cada tantos segundos de short (maximo BROLL_MAX)
BROLL_MAX = 4
BROLL_MODOS = ("pexels", "banco", "ambos")   # "" = todo del video
BROLL_BANCO_MAX = 80   # clips del banco que se le ensenan a Claude (menos tokens)
BROLL_DUR = (2.0, 3.2)
DOC_ANCHO = 0.80   # documental: parte del ancho del original que se ve (un poco de zoom, casi todo el dibujo)
_candado = threading.RLock()
_trabajos = {}         # cid -> hilo vivo


def _dir(cid, *partes, crear=False):
    almacen.validar_id(cid)
    ruta = almacen.raiz("clips", cid, *partes)
    if crear:
        os.makedirs(ruta, exist_ok=True)
    return ruta


def _leer(cid):
    s = almacen.leer_json(_dir(cid, "sesion.json"))
    if s is None:
        raise FileNotFoundError("esa sesion de Clip Studio no existe")
    return s


def _guardar(cid, **cambios):
    with _candado:
        s = _leer(cid)
        s.update(cambios)
        s["actualizado"] = time.time()
        almacen.escribir_json(_dir(cid, "sesion.json"), s)
        return s


def listar():
    base = almacen.raiz("clips")
    if not os.path.isdir(base):
        return []
    salida = []
    for cid in os.listdir(base):
        s = almacen.leer_json(os.path.join(base, cid, "sesion.json"))
        if s:
            salida.append(s)
    return sorted(salida, key=lambda s: s.get("creado", 0), reverse=True)


def ver(cid):
    s = _leer(cid)
    return {**s, "frases": almacen.leer_json(_dir(cid, "frases.json"), []) or [],
            "propuestas": almacen.leer_json(_dir(cid, "propuestas.json"), []) or [],
            "exportados": almacen.leer_json(_dir(cid, "exportados.json"), []) or []}


def ruta_original(cid):
    s = _leer(cid)
    return _dir(cid, s["original"])


def ruta_export(cid, nombre):
    if not re.fullmatch(r"[0-9a-f]{16}\.mp4", nombre or ""):
        raise ValueError("archivo no valido")
    ruta = _dir(cid, "exportados", nombre)
    if not os.path.isfile(ruta):
        raise FileNotFoundError("ese short no existe")
    return ruta


def crear(nombre_archivo, fichero):
    """Guarda el video subido (un objeto con .read) y empieza a transcribirlo."""
    ext = os.path.splitext(nombre_archivo or "")[1].lower()
    if ext not in EXTENSIONES:
        raise ValueError(f"formato no soportado ({ext or 'sin extension'}): sube MP4, MOV, MKV, WEBM, M4V o AVI")
    cid = uuid.uuid4().hex[:12]
    destino = _dir(cid, f"original{ext}")
    os.makedirs(_dir(cid), exist_ok=True)
    with open(destino, "wb") as f:
        shutil.copyfileobj(fichero, f, length=4 * 1024 * 1024)
    info = medios.sondear(destino)
    if not info["duracion"]:
        shutil.rmtree(_dir(cid), ignore_errors=True)
        raise ValueError("no se pudo leer el video")
    titulo = os.path.splitext(os.path.basename(nombre_archivo))[0][:120]
    almacen.escribir_json(_dir(cid, "sesion.json"), {
        "id": cid, "titulo": titulo, "original": f"original{ext}", "creado": time.time(), "actualizado": time.time(),
        "duracion": info["duracion"], "ancho": info["ancho"], "alto": info["alto"],
        "estado": "transcribiendo", "progreso": 0, "mensaje": "en cola", "error": None,
    })
    _lanzar(cid, _transcribir, cid)
    return _leer(cid)


def borrar(cid):
    with _candado:
        if cid in _trabajos and _trabajos[cid].is_alive():
            raise RuntimeError("esta trabajando: espera a que termine")
        shutil.rmtree(_dir(cid), ignore_errors=True)


def _lanzar(cid, fn, *args):
    with _candado:
        if cid in _trabajos and _trabajos[cid].is_alive():
            raise RuntimeError("ya esta trabajando: espera a que termine")

        def correr():
            try:
                fn(*args)
            except Exception as e:  # noqa: BLE001 -- se ve en la interfaz
                logger.exception(f"clip studio {cid}")
                _guardar(cid, estado="error", error=str(e)[:500], mensaje="")
        hilo = threading.Thread(target=correr, daemon=True, name=f"clips-{cid}")
        _trabajos[cid] = hilo
        hilo.start()


# ------------------------------------------------------------------ transcribir

def _transcribir(cid):
    s = _leer(cid)
    _guardar(cid, estado="transcribiendo", progreso=1, mensaje="cargando Whisper", error=None)
    segmentos, info = voz._modelo_whisper().transcribe(_dir(cid, s["original"]), word_timestamps=True,
                                                       vad_filter=True, beam_size=1)
    palabras = []
    dur = s["duracion"] or 1
    for seg in segmentos:
        palabras += [[round(float(w.start), 3), round(float(w.end), 3), w.word.strip()] for w in (seg.words or []) if w.word.strip()]
        _guardar(cid, progreso=int(2 + 95 * min(1.0, seg.end / dur)),
                 mensaje=f"transcribiendo {int(seg.end) // 60}:{int(seg.end) % 60:02d} de {int(dur) // 60}:{int(dur) % 60:02d}")
    if not palabras:
        raise RuntimeError("Whisper no entendio ninguna palabra: el video no tiene habla")
    almacen.escribir_json(_dir(cid, "palabras.json"), palabras)
    almacen.escribir_json(_dir(cid, "frases.json"), frases_de(palabras))
    _guardar(cid, estado="listo", progreso=100, mensaje=f"{len(palabras)} palabras", idioma=info.language)


def frases_de(palabras):
    """[(inicio, fin, texto)]: se corta en punto final, pausa larga o demasiadas palabras."""
    frases, actual = [], []
    for k, (a, b, w) in enumerate(palabras):
        actual.append((a, b, w))
        sigue = palabras[k + 1][0] if k + 1 < len(palabras) else None
        fin = (re.search(r"[.!?…]$", w) or (sigue is not None and sigue - b > PAUSA_FRASE_S)
               or len(actual) >= FRASE_MAX_PALABRAS or sigue is None)
        if fin:
            frases.append([actual[0][0], actual[-1][1], " ".join(x[2] for x in actual)])
            actual = []
    return frases


# ------------------------------------------------------------------ proponer

def proponer(cid, cuantos=5, duracion="medio", pedido=""):
    s = _leer(cid)
    if s["estado"] not in ("listo", "error") or not os.path.isfile(_dir(cid, "frases.json")):
        raise RuntimeError("primero tiene que terminar la transcripcion")
    _guardar(cid, estado="proponiendo", progreso=1, mensaje="Claude busca los mejores momentos", error=None)
    _lanzar(cid, _proponer, cid, max(1, min(15, int(cuantos))), duracion if duracion in DURACIONES else "medio",
            str(pedido or "")[:300])


def _mmss(t):
    return f"{int(t) // 60}:{int(t) % 60:02d}"


IDIOMAS = {"es": "espanol", "en": "ingles", "pt": "portugues", "fr": "frances", "it": "italiano", "de": "aleman"}


def _proponer(cid, cuantos, duracion, pedido):
    frases = almacen.leer_json(_dir(cid, "frases.json"), [])
    idioma = IDIOMAS.get(_leer(cid).get("idioma") or "", "el idioma del video")
    lo, hi = DURACIONES[duracion]
    ventanas = [list(range(k, min(len(frases), k + VENTANA_FRASES))) for k in range(0, len(frases), VENTANA_FRASES)]
    por_ventana = max(2, -(-cuantos * 2 // len(ventanas))) if len(ventanas) > 1 else cuantos
    candidatos = []
    for n, idx in enumerate(ventanas):
        _guardar(cid, progreso=int(5 + 90 * n / len(ventanas)), mensaje=f"Claude lee el tramo {n + 1} de {len(ventanas)}")
        texto = "\n".join(f"[{i}] {_mmss(frases[i][0])} {frases[i][2]}" for i in idx)
        prompt = (
            "Eres editor de shorts virales (TikTok, Reels, YouTube Shorts). De esta transcripcion de un video largo, "
            f"elige los {por_ventana} mejores momentos para shorts de {lo}-{hi} s: que se entiendan solos, con un "
            "arranque que enganche y un final que cierre la idea. Evita saludos, despedidas y relleno.\n"
            + (f"Pedido: {pedido}\n" if pedido else "")
            + "Cada momento va de la frase [desde] a la frase [hasta] (incluidas). Da un titulo corto y un gancho para "
            f"poner en pantalla (hasta 8 palabras), los dos en {idioma.upper()} (el idioma del video, aunque estas "
            "instrucciones esten en espanol), una nota de 1 a 10 de "
            "potencial viral y el motivo en una frase en espanol.\n"
            f"{texto}\n"
            'Responde SOLO con una lista JSON: [{"desde": 0, "hasta": 5, "titulo": "...", "gancho": "...", "nota": 8, "motivo": "..."}]'
        )
        try:
            lista = claude_cli.extraer_json(claude_cli.ejecutar(prompt, modelo="sonnet", esfuerzo="low", tiempo_max_s=300))
        except Exception as e:  # noqa: BLE001 -- un tramo sin propuestas no tumba el resto
            logger.warning(f"clip studio {cid}: tramo {n + 1} sin propuestas ({e})")
            continue
        for x in lista if isinstance(lista, list) else []:
            try:
                a, b = int(x["desde"]), int(x["hasta"])
            except (KeyError, TypeError, ValueError):
                continue
            if 0 <= a <= b < len(frases):
                candidatos.append(_ajustar(frases, a, b, lo, hi) | {
                    "titulo": str(x.get("titulo") or "").strip()[:100], "gancho": str(x.get("gancho") or "").strip()[:80],
                    "nota": _nota(x.get("nota")), "motivo": str(x.get("motivo") or "").strip()[:200]})
    if not candidatos:
        raise RuntimeError("Claude no propuso ningun momento (prueba otra vez)")
    # Los mejores, sin pisarse.
    elegidos = []
    for c in sorted(candidatos, key=lambda c: -(c["nota"] or 0)):
        if all(c["fin"] <= y["inicio"] or c["inicio"] >= y["fin"] for y in elegidos):
            elegidos.append(c)
        if len(elegidos) >= cuantos:
            break
    for c in elegidos:
        c["id"] = uuid.uuid4().hex[:8]
    almacen.escribir_json(_dir(cid, "propuestas.json"), sorted(elegidos, key=lambda c: c["inicio"]))
    _guardar(cid, estado="listo", progreso=100, mensaje=f"{len(elegidos)} momentos propuestos")


def _nota(v):
    try:
        return max(1, min(10, int(round(float(v)))))
    except (TypeError, ValueError):
        return None


def _ajustar(frases, a, b, lo, hi):
    """De frase a frase, sin pasar de `hi` (se quitan frases del final) ni quedarse corto si se puede."""
    while b > a and frases[b][1] - frases[a][0] > hi:
        b -= 1
    while b + 1 < len(frases) and frases[b][1] - frases[a][0] < lo and frases[b + 1][1] - frases[a][0] <= hi:
        b += 1
    return {"inicio": round(max(0.0, frases[a][0] - 0.15), 2), "fin": round(frases[b][1] + 0.25, 2)}


def guardar_propuestas(cid, propuestas):
    """La lista editada a mano (tiempos, textos, clips nuevos o quitados)."""
    s = _leer(cid)
    limpio = []
    for x in propuestas if isinstance(propuestas, list) else []:
        try:
            a, b = round(float(x["inicio"]), 2), round(float(x["fin"]), 2)
        except (KeyError, TypeError, ValueError):
            continue
        if 0 <= a < b <= s["duracion"] + 0.5 and b - a >= 1:
            limpio.append({"id": str(x.get("id") or uuid.uuid4().hex[:8])[:12], "inicio": a, "fin": b,
                           "titulo": str(x.get("titulo") or "")[:100], "gancho": str(x.get("gancho") or "")[:80],
                           "nota": _nota(x.get("nota")), "motivo": str(x.get("motivo") or "")[:200]})
    almacen.escribir_json(_dir(cid, "propuestas.json"), sorted(limpio, key=lambda c: c["inicio"]))
    return limpio


# ------------------------------------------------------------------ exportar

def exportar(cid, opciones):
    """Lanza el short de un tramo. opciones: inicio, fin, encuadre ("recortar"|"ajustar"|"documental"), encuadre_x (0-1),
    banda (0-0.35: alto de los subtitulos grabados del original que se quitan), subtitulos (bool), gancho (texto arriba),
    titulo (nombre)."""
    s = _leer(cid)
    a, b = float(opciones["inicio"]), float(opciones["fin"])
    if not (0 <= a < b <= s["duracion"] + 0.5) or b - a < 1 or b - a > 180:
        raise ValueError("el tramo debe durar entre 1 s y 3 min")
    o = {"inicio": round(a, 2), "fin": round(b, 2),
         "encuadre": opciones.get("encuadre") if opciones.get("encuadre") in ENCUADRES else "recortar",
         "banda": round(min(0.35, max(0.0, float(opciones.get("banda") or 0))), 3),
         "encuadre_x": round(min(1.0, max(0.0, float(opciones.get("encuadre_x", 0.5)))), 3),
         "subtitulos": bool(opciones.get("subtitulos", True)), "broll": "pexels" if opciones.get("broll") is True else opciones.get("broll") if opciones.get("broll") in BROLL_MODOS else "",
         "bancos": [x for x in (opciones.get("bancos") or []) if re.fullmatch(r"[0-9a-f]{12}", str(x))][:3], "gancho": str(opciones.get("gancho") or "").strip()[:80],
         "titulo": str(opciones.get("titulo") or "").strip()[:100], "color": str(opciones.get("color") or "#FFD447")[:7]}
    huella = hashlib.sha1(json.dumps([VERSION_EXPORT, s["original"], o], sort_keys=True).encode()).hexdigest()[:16]
    _guardar(cid, estado="exportando", progreso=1, mensaje="preparando el short", error=None)
    _lanzar(cid, _exportar, cid, o, huella)
    return {"archivo": f"{huella}.mp4"}


def _ass(palabras, a, b, w, h, gancho, color, abajo=0.2):
    """Subtitulos palabra por palabra (de 3 en 3, la que suena resaltada) y el gancho arriba.
    abajo: distancia del borde inferior a los subtitulos (parte del alto)."""
    fuente = acabado.familia_fuente("STHeitiMedium.ttc")
    tam = int(h * 0.045)
    estilos = [
        f"Style: Sub,{fuente},{tam},&H00FFFFFF,&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,{max(3, tam // 12)},2,2,60,60,{int(h * abajo)},1",
        f"Style: Gancho,{fuente},{int(tam * 1.05)},&H00FFFFFF,&H000000FF,&H50000000,&H80000000,-1,0,0,0,100,100,0,0,3,{max(8, tam // 5)},0,8,70,70,{int(h * 0.1)},1",
    ]
    resalte = acabado._color_ass(color)
    lineas = []
    dentro = [(x - a, y - a, t) for x, y, t in palabras if x >= a - 0.05 and y <= b + 0.05]
    for k in range(0, len(dentro), 3):
        grupo = dentro[k:k + 3]
        for j, (x, y, _t) in enumerate(grupo):
            fin = grupo[j + 1][0] if j + 1 < len(grupo) else y
            texto = " ".join((f"{{\\c{resalte}}}{acabado.limpio(t).upper()}{{\\c&H00FFFFFF&}}" if n == j else acabado.limpio(t).upper())
                             for n, (_x, _y, t) in enumerate(grupo))
            lineas.append(f"Dialogue: 0,{acabado._t_ass(max(0, x))},{acabado._t_ass(max(x + 0.05, fin))},Sub,,0,0,0,,{texto}")
    if gancho:
        lineas.append(f"Dialogue: 1,{acabado._t_ass(0)},{acabado._t_ass(min(b - a, 3.5))},Gancho,,0,0,0,,{{\\fad(150,300)}}{acabado.limpio(gancho)}")
    return acabado.cabecera(w, h, estilos) + "\n".join(lineas) + "\n"


def _plan_broll(cid, a, b, modo, bancos):
    """[{t, d, buscar | clip}] en tiempo del short: frases del tramo que ganan con un plano de otra fuente
    (Pexels: que buscar; banco: el clip 'k-n' de banco.para_guion que pega con la frase)."""
    frases = [f for f in almacen.leer_json(_dir(cid, "frases.json"), []) if f[0] >= a - 0.2 and f[1] <= b + 0.3]
    if len(frases) < 3:
        return []
    n = max(1, min(BROLL_MAX, int((b - a) // BROLL_CADA_S)))
    filas = []
    for k, bid in enumerate(bancos if modo != "pexels" else [], 1):
        try:
            filas += [f"{k}-{c['n']}: {c['describe']}" for c in almacen.leer_json(banco._dir(bid, "clips.json"), []) or []
                      if c.get("sirve", True) and c.get("describe")]
        except ValueError:
            continue
    if len(filas) > BROLL_BANCO_MAX:   # menos tokens: una muestra repartida
        filas = [filas[round(i * (len(filas) - 1) / (BROLL_BANCO_MAX - 1))] for i in range(BROLL_BANCO_MAX)]
    if modo == "banco" and not filas:
        return []
    pexels = modo in ("pexels", "ambos")
    como = ('"buscar": 2-3 palabras EN INGLES para buscar en Pexels (algo que se pueda filmar: nada abstracto ni nombres '
            'propios)' if pexels else "")
    if filas:
        como = (como + (" o, si uno pega mejor, " if pexels else "")
                + '"clip": el id de uno de estos clips (que pegue con la frase: accion, emocion o cosa; sin repetir):\n'
                + "\n".join(filas))
    prompt = (f"Editor de shorts. Elige hasta {n} frases de este clip que ganen con un plano de B-roll (otro video que "
              "ilustra lo que se dice: un objeto, un lugar, una accion concreta). Nunca la [0] ni la ultima. Para cada una "
              f"da {como}\nFRASES DEL CLIP:\n" + "\n".join(f"[{k}] {f[2]}" for k, f in enumerate(frases))
              + "\nResponde SOLO JSON: [" + ('{"frase": 2, "buscar": "oil barrels"}' if pexels else '{"frase": 2, "clip": "1-14"}') + "]")
    lista = claude_cli.extraer_json(claude_cli.ejecutar(prompt, modelo="haiku", esfuerzo="low", tiempo_max_s=120))
    pedidos = {}
    for x in lista if isinstance(lista, list) else []:
        try:
            k = int(x["frase"])
        except (KeyError, TypeError, ValueError):
            continue
        clip = banco.resolver(bancos, x.get("clip")) if filas and x.get("clip") else None
        buscar = str(x.get("buscar") or "").strip()[:40] if pexels else ""
        if 0 < k < len(frases) - 1 and (clip or buscar):
            pedidos[k] = {"clip": list(clip)} if clip else {"buscar": buscar}
    plan, fin_prev = [], -1.0
    for k in sorted(pedidos):
        t = max(0.0, frases[k][0] - a)
        d = min(BROLL_DUR[1], max(BROLL_DUR[0], frases[k][1] - frases[k][0] + 0.3))
        if t >= fin_prev + 1.5 and t + d < b - a - 1:   # sin pisarse y nunca al final
            plan.append({"t": round(t, 2), "d": round(d, 2), **pedidos[k]})
            fin_prev = t + d
    return plan[:n]


def _bajar_broll(plan, horizontal):
    """El archivo de cada plano: el clip del banco o un video de Pexels (sin repetir); los que no aparecen se quitan."""
    usados, listos = set(), []
    for p in plan:
        if p.get("clip"):
            try:
                ruta = banco.ruta_clip(*p["clip"])
            except (FileNotFoundError, ValueError):
                continue
            if ruta not in usados:
                usados.add(ruta)
                listos.append(p | {"archivo": ruta})
            continue
        for v in material.search_videos_pexels(p["buscar"], 3, VideoAspect.landscape if horizontal else VideoAspect.portrait):
            if v.url in usados:
                continue
            ruta = material.save_video(v.url)
            if ruta:
                usados.add(v.url)
                listos.append(p | {"archivo": ruta})
                break
    return listos


def _exportar(cid, o, huella):
    s = _leer(cid)
    carpeta = _dir(cid, "exportados", crear=True)
    final = os.path.join(carpeta, f"{huella}.mp4")
    if not os.path.isfile(final):
        w, h = 1080, 1920
        a, b = o["inicio"], o["fin"]
        partes = []
        # sin la franja de subtitulos grabados del original (abajo)
        quitar = f"crop=iw:ih*{1 - o['banda']:.3f}:0:0," if o["banda"] else ""
        abajo = 0.2
        caja = (0, 0, w, h)   # donde va el B-roll
        if o["encuadre"] == "documental":
            # el dibujo a lo ancho un poco por encima del centro; arriba el gancho, debajo los subtitulos
            ancho = DOC_ANCHO if s["ancho"] > s["alto"] else 1.0
            alto_v = min(h * 0.62, w * s["alto"] * (1 - o["banda"]) / max(1, s["ancho"] * ancho))
            y = int(h * 0.44 - alto_v / 2)
            alto_v = int(alto_v) // 2 * 2
            caja = (0, y, w, alto_v)
            abajo = max(0.08, 1 - (y + alto_v) / h - 0.1)
            filtro = (f"[0:v]{quitar}split=2[f][v];[f]scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},"
                      f"boxblur=30:3,eq=brightness=-0.12[fondo];"
                      f"[v]crop=iw*{ancho}:ih:(iw-iw*{ancho})/2:0,scale={w}:{alto_v}:force_original_aspect_ratio=increase,crop={w}:{alto_v}[delante];"
                      f"[fondo][delante]overlay=(W-w)/2:{y},setsar=1")
        elif o["encuadre"] == "ajustar":
            filtro = (f"[0:v]{quitar}split=2[f][v];[f]scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},boxblur=30:3,"
                      f"eq=brightness=-0.08[fondo];[v]scale={w}:{h}:force_original_aspect_ratio=decrease[delante];"
                      f"[fondo][delante]overlay=(W-w)/2:(H-h)/2,setsar=1")
        else:
            # Recorte vertical por donde diga encuadre_x (centro del recorte, 0-1).
            filtro = (f"[0:v]{quitar}scale=-2:{h},crop='min(iw,ih*9/16)':ih:'(iw-min(iw,ih*9/16))*{o['encuadre_x']}':0,"
                      f"scale={w}:{h},setsar=1")
        if o["subtitulos"] or o["gancho"]:
            palabras = almacen.leer_json(_dir(cid, "palabras.json"), []) if o["subtitulos"] else []
            with open(os.path.join(carpeta, f"{huella}.ass"), "w", encoding="utf-8") as f:
                f.write(_ass(palabras, a, b, w, h, o["gancho"], o["color"], abajo))
            partes.append(f"subtitles={huella}.ass:fontsdir={acabado._ruta_filtro(utils.font_dir(), carpeta)}")
        entradas = []
        if o["broll"]:
            _guardar(cid, progreso=5, mensaje="B-roll: Claude elige los planos de otras fuentes")
            try:
                rolls = _bajar_broll(_plan_broll(cid, a, b, o["broll"], o["bancos"]), caja[2] > caja[3])
            except Exception as e:  # noqa: BLE001 -- sin B-roll el short sale igual
                logger.warning(f"clip studio {cid}: sin B-roll ({e})")
                rolls = []
            etiqueta = "base"
            filtro += "[base]"
            for k, p in enumerate(rolls, start=1):
                entradas += ["-t", f"{p['d'] + 0.3:.2f}", "-i", p["archivo"]]
                filtro += (f";[{k}:v]scale={caja[2]}:{caja[3]}:force_original_aspect_ratio=increase,crop={caja[2]}:{caja[3]},"
                           f"setsar=1,fps=30,setpts=PTS-STARTPTS+{p['t']:.2f}/TB[b{k}];[{etiqueta}][b{k}]overlay={caja[0]}:{caja[1]}:"
                           f"enable='between(t,{p['t']:.2f},{p['t'] + p['d']:.2f})':eof_action=pass[o{k}]")
                etiqueta = f"o{k}"
            filtro += f";[{etiqueta}]" + (",".join(partes) if partes else "null") + "[v]"
            almacen.escribir_json(os.path.join(carpeta, f"{huella}.broll.json"), rolls)
        else:
            filtro += ("," + ",".join(partes) if partes else "") + "[v]"
        _guardar(cid, progreso=10, mensaje="cortando y encuadrando")
        tmp = os.path.join(carpeta, f"{huella}.tmp.mp4")
        r = medios.correr([medios.ffmpeg(), "-hide_banner", "-loglevel", "error", "-y", "-ss", f"{a:.3f}", "-to", f"{b:.3f}",
                           "-i", _dir(cid, s["original"]), *entradas, "-filter_complex", filtro, "-map", "[v]", "-map", "0:a?",
                           "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", "-r", "30",
                           "-c:a", "aac", "-b:a", "160k", "-af", "loudnorm=I=-14:TP=-1.5:LRA=11", "-movflags", "+faststart", tmp],
                          timeout=3600, cwd=carpeta)
        if r.returncode != 0 or not os.path.isfile(tmp):
            raise RuntimeError(f"ffmpeg no pudo hacer el short: {r.stderr[-500:]}")
        os.replace(tmp, final)
    hechos = [x for x in almacen.leer_json(_dir(cid, "exportados.json"), []) or [] if x["archivo"] != f"{huella}.mp4"]
    hechos.insert(0, {"archivo": f"{huella}.mp4", "titulo": o["titulo"] or o["gancho"] or f"{_mmss(o['inicio'])}-{_mmss(o['fin'])}",
                      "inicio": o["inicio"], "fin": o["fin"], "creado": time.time(),
                      "tam_mb": round(os.path.getsize(final) / 1e6, 1)})
    almacen.escribir_json(_dir(cid, "exportados.json"), hechos)
    _guardar(cid, estado="listo", progreso=100, mensaje="short listo")
