"""
Etapa VOZ: sintetiza el guion con el TTS de MoneyPrinterTurbo y lo corta en
PLANOS usando los tiempos de ESA voz (igual que el modo local), asi el
cambio de imagen cae justo donde cambia la narracion.

Planos: se fusionan los trozos mas cortos que `plano_min_s` y se parten los mas
largos que `plano_max_s`, para que ningun recurso se quede demasiado en pantalla.

Sin voz (voz = "ninguna", p. ej. estilos ASMR de un prompt maestro): silencio de
la duracion de `tramos` (segundos de cada escena, se lee con .get) y un plano por
tramo; el render usa entonces el sonido de los propios clips.

Audio propio (voz = "propia:<archivo>", subido a voz_propia/): una narracion ya
grabada (p. ej. hecha con Clonar-voz). Whisper da el tiempo de cada palabra; si el
guion coincide con lo que se oye, los subtitulos usan el texto del guion (sin
errores de transcripcion) con los tiempos de Whisper. Si no hay guion o no cuadra,
se usa la transcripcion. Con `quitar_silencios` (segundos, se lee con .get) las
pausas mas largas se acortan a ese maximo ANTES de transcribir.
"""
import difflib
import json
import math
import os
import re
import threading
import unicodedata

from app.config import config
from app.services import subtitle, voice
from app.services.estudio import componentes, medios
from app.services.segmentos import merge_short_segments, parse_segments
from app.utils import utils

DEFECTOS = {
    "voz": "es-ES-AlvaroNeural-Male",
    "velocidad": 1.0,
    "plano_min_s": 2.5,
    "plano_max_s": 6.0,
}


SIN_VOZ = "ninguna"
PROPIA = "propia:"
MODELO_WHISPER = "base"   # rapido en CPU (~8 s por minuto de audio); el texto lo pone el guion
COINCIDENCIA_MIN = 0.6    # fraccion de palabras del guion que deben oirse para usar su texto


def _sin_voz(ctx):
    tramos = [float(t) for t in ctx.params.get("tramos") or [] if float(t) > 0]
    if not tramos:
        raise ValueError("sin voz hace falta la duracion de cada escena (tramos)")
    carpeta = ctx.dir("voz")
    audio = os.path.join(carpeta, "voz.mp3")
    duracion = round(sum(tramos), 3)
    r = medios.correr([medios.ffmpeg(), "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi",
                       "-i", "anullsrc=r=44100:cl=stereo", "-t", f"{duracion:.3f}",
                       "-c:a", "libmp3lame", "-q:a", "4", audio], timeout=300)
    if r.returncode != 0:
        raise RuntimeError(f"ffmpeg no pudo crear la pista muda: {r.stderr[-300:]}")
    with open(os.path.join(carpeta, "subtitulos.srt"), "w", encoding="utf-8") as f:
        f.write("")
    planos, t = [], 0.0
    for i, d in enumerate(tramos):
        planos.append({"i": i, "inicio": round(t, 3), "fin": round(t + d, 3), "texto": ""})
        t += d
    ctx.avisar(f"sin voz: {len(planos)} escenas, {duracion:.1f}s (sonara el audio de los clips)", 100)
    return {"audio": "voz/voz.mp3", "srt": "voz/subtitulos.srt", "duracion": duracion,
            "planos": planos, "sin_voz": True}


def partir_largos(segmentos, maximo):
    salida = []
    for inicio, fin, texto in segmentos:
        dur = fin - inicio
        n = max(1, math.ceil(dur / maximo - 1e-6))
        if n == 1:
            salida.append((inicio, fin, texto))
            continue
        palabras = texto.split()
        paso = dur / n
        for k in range(n):
            a = round(k * len(palabras) / n)
            b = round((k + 1) * len(palabras) / n)
            trozo = " ".join(palabras[a:b]) or texto
            salida.append((inicio + k * paso, inicio + (k + 1) * paso if k < n - 1 else fin, trozo))
    return salida


def ejecutar(ctx):
    p = ctx.params
    if p["voz"] == SIN_VOZ:
        return _sin_voz(ctx)
    propia = str(p["voz"]).startswith(PROPIA)
    texto = (ctx.salidas["guion"] or {}).get("texto", "").strip()
    if not texto and not propia:
        raise ValueError("no hay guion")
    carpeta = ctx.dir("voz")
    audio = os.path.join(carpeta, "voz.mp3")
    srt = os.path.join(carpeta, "subtitulos.srt")
    for f in (audio, srt, os.path.join(carpeta, "palabras.json")):
        if os.path.exists(f):
            os.remove(f)

    extra = {}
    if propia:
        duracion, extra = _voz_propia(ctx, texto, audio, srt)
    else:
        duracion = _voz_tts(ctx, texto, audio, srt)
    crudos = parse_segments(srt)
    if not crudos:
        raise RuntimeError("no salieron tiempos de la voz (SRT vacio)")

    planos = merge_short_segments(crudos, float(p["plano_min_s"]), duracion)
    planos = partir_largos(planos, max(float(p["plano_max_s"]), float(p["plano_min_s"]) + 0.5))
    segmentos = [{"i": i, "inicio": round(a, 3), "fin": round(b, 3), "texto": t}
                 for i, (a, b, t) in enumerate(planos)]
    with open(os.path.join(carpeta, "planos.json"), "w", encoding="utf-8") as f:
        json.dump(segmentos, f, ensure_ascii=False, indent=1)
    ctx.avisar(f"voz lista: {duracion:.1f}s, {len(segmentos)} planos", 100)
    return {"audio": "voz/voz.mp3", "srt": "voz/subtitulos.srt",
            "duracion": round(duracion, 3), "planos": segmentos, **extra}


def _voz_tts(ctx, texto, audio, srt):
    """Voces de Microsoft (y demas TTS de MPT): dan el tiempo de cada palabra."""
    p = ctx.params
    nombre = voice.parse_voice_name(p["voz"])
    if componentes.es_voz_microsoft(nombre):
        # Si Microsoft rechaza la version de edge-tts, avisar ya (no tras 3 x 120 s).
        componentes.comprobar_edge_tts(nombre)
    ctx.avisar(f"sintetizando voz {p['voz']}", 10)
    sub_maker = voice.tts(
        text=texto,
        voice_name=nombre,
        voice_rate=float(p["velocidad"]),
        voice_file=audio,
        voice_volume=1.0,  # el volumen se aplica en render (no obliga a re-sintetizar)
    )
    if sub_maker is None or not os.path.exists(audio):
        raise RuntimeError("el TTS no genero audio: revisa que la voz coincida con el idioma del guion y la conexion")
    duracion = float(voice.get_audio_duration(sub_maker) or 0)
    if duracion <= 0:
        raise RuntimeError("no se pudo medir la duracion del audio")

    palabras = _guardar_palabras(sub_maker, os.path.join(ctx.dir("voz"), "palabras.json"))
    ctx.avisar("calculando tiempos de cada frase", 70)
    if palabras and srt_de_palabras(texto, palabras, srt):
        pass  # frases con los tiempos exactos de cada palabra
    elif config.app.get("subtitle_provider", "edge").strip().lower() == "edge":
        voice.create_subtitle(text=texto, sub_maker=sub_maker, subtitle_file=srt)
    if not os.path.exists(srt):
        subtitle.create(audio_file=audio, subtitle_file=srt)
        subtitle.correct(subtitle_file=srt, video_script=texto)
    return duracion


def _guardar_palabras(sub_maker, destino):
    """Tiempos de CADA palabra (los da edge-tts con WordBoundary): los usa la
    edicion editorial para los subtitulos palabra a palabra. Si el TTS solo da
    frases, no se guarda nada y la edicion reparte los tiempos por frase."""
    palabras = []
    try:
        if getattr(sub_maker, "cues", None):
            palabras = [[round(c.start.total_seconds(), 3), round(c.end.total_seconds(), 3), str(c.content)]
                        for c in sub_maker.cues]
        elif getattr(sub_maker, "subs", None) and len(sub_maker.subs) == len(getattr(sub_maker, "offset", [])):
            palabras = [[round(a / 1e7, 3), round(b / 1e7, 3), str(t)]
                        for t, (a, b) in zip(sub_maker.subs, sub_maker.offset)]
    except Exception:  # noqa: BLE001
        palabras = []
    # edge agrupa a veces varias palabras en una marca ("8 de marzo", "239 personas"):
    # se reparten a partes iguales para tener siempre UNA palabra por entrada.
    sueltas = []
    for a, b, t in palabras:
        trozos = t.split()
        paso = (b - a) / max(1, len(trozos))
        sueltas += [[round(a + k * paso, 3), round(a + (k + 1) * paso, 3), w] for k, w in enumerate(trozos)]
    if sueltas:
        with open(destino, "w", encoding="utf-8") as f:
            json.dump(sueltas, f, ensure_ascii=False)
    return sueltas


# Fin de frase: signo de puntuacion seguido de espacio (asi "00:41" o "3.5" no cortan),
# salvo tras una inicial ("John D. Rockefeller").
FIN_FRASE = re.compile(r"(?<![\s(][A-Z]\.)(?<=[.!?;:,\u2026])\s+|\n+")


def srt_de_palabras(texto, palabras, destino):
    """SRT por frases con los tiempos de cada palabra. Solo si las palabras del
    TTS cuadran una a una con las del guion; si no, False (se usa el de MPT)."""
    frases = [f.strip() for f in FIN_FRASE.split(texto) if f and f.strip()]
    if sum(len(f.split()) for f in frases) != len(palabras):
        return False
    lineas, k = [], 0
    for n, frase in enumerate(frases, start=1):
        m = len(frase.split())
        a, b = palabras[k][0], palabras[k + m - 1][1]
        k += m
        limpio = frase.rstrip(",;:.")
        lineas.append(utils.text_to_srt(n, limpio, a, b))
    tiempos = [p[0] for p in palabras]
    if any(y < x for x, y in zip(tiempos, tiempos[1:])):
        return False
    with open(destino, "w", encoding="utf-8") as f:
        f.write("\n".join(lineas) + "\n")
    return True


# ------------------------------------------------------------------ audio propio

_whisper = None
_whisper_candado = threading.Lock()


def _modelo_whisper():
    global _whisper
    with _whisper_candado:
        if _whisper is None:
            from faster_whisper import WhisperModel
            _whisper = WhisperModel(MODELO_WHISPER, device="cpu", compute_type="int8")
    return _whisper


def _norm(palabra):
    t = unicodedata.normalize("NFD", palabra.lower())
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    return re.sub(r"[^\w%$€]+", "", t)


def alinear(texto, oidas):
    """Pone a cada palabra del guion el tiempo de la palabra que se oye. Las que no
    casan (numeros dichos con letras, cambios al grabar) se reparten entre las
    vecinas que si casan. None si el guion no se parece a lo que se oye."""
    guion = texto.split()
    if not guion or not oidas:
        return None
    sm = difflib.SequenceMatcher(None, [_norm(w) for w in guion], [_norm(w[2]) for w in oidas], autojunk=False)
    tiempos = [None] * len(guion)
    for bloque in sm.get_matching_blocks():
        for k in range(bloque.size):
            a, b, _w = oidas[bloque.b + k]
            tiempos[bloque.a + k] = (a, b)
    casadas = sum(t is not None for t in tiempos)
    if casadas < COINCIDENCIA_MIN * len(guion):
        return None
    i = 0
    while i < len(guion):
        if tiempos[i] is not None:
            i += 1
            continue
        j = i
        while j < len(guion) and tiempos[j] is None:
            j += 1
        ini = tiempos[i - 1][1] if i > 0 else oidas[0][0]
        fin = tiempos[j][0] if j < len(guion) else oidas[-1][1]
        fin = max(fin, ini)
        pesos = [len(w) + 1 for w in guion[i:j]]
        total, cursor = sum(pesos), ini
        for k, pz in zip(range(i, j), pesos):
            d = (fin - ini) * pz / total
            tiempos[k] = (cursor, cursor + d)
            cursor += d
        i = j
    palabras = [[round(a, 3), round(b, 3), w] for (a, b), w in zip(tiempos, guion)]
    return palabras, casadas / len(guion)


def _voz_propia(ctx, texto, audio, srt):
    """Narracion subida: se convierte a mp3 y Whisper da el tiempo de cada palabra."""
    nombre = str(ctx.params["voz"])[len(PROPIA):]
    origen = ctx.dir("voz_propia", nombre, crear=False)
    if not nombre or os.path.basename(nombre) != nombre or not os.path.isfile(origen):
        raise FileNotFoundError("no esta el audio subido: vuelve a subirlo en el paso Voz")
    ctx.avisar("convirtiendo el audio subido", 3)
    pausa = min(3.0, max(0.0, float(ctx.params.get("quitar_silencios") or 0)))
    filtro = ["-af", f"silenceremove=stop_periods=-1:stop_duration={pausa + 0.15:.2f}:stop_threshold=-40dB"
                     f":stop_silence={pausa:.2f}"] if pausa else []
    r = medios.correr([medios.ffmpeg(), "-hide_banner", "-loglevel", "error", "-y", "-i", origen, "-vn", *filtro,
                       "-c:a", "libmp3lame", "-q:a", "2", audio], timeout=1800)
    if r.returncode != 0 or not os.path.exists(audio):
        raise RuntimeError(f"ffmpeg no pudo leer el audio subido: {r.stderr[-300:]}")
    duracion = float(medios.sondear(audio).get("duracion") or 0)
    if duracion <= 0:
        raise RuntimeError("no se pudo medir la duracion del audio subido")

    ctx.avisar("cargando Whisper", 5)
    # Sin silencios recortados, Whisper oye el original (sin perdida de mp3).
    segmentos, info = _modelo_whisper().transcribe(audio if pausa else origen, word_timestamps=True,
                                                   vad_filter=True, beam_size=1)
    oidas = []
    for s in segmentos:
        oidas += [(float(w.start), float(w.end), w.word.strip()) for w in (s.words or []) if w.word.strip()]
        ctx.avisar(f"transcribiendo {int(s.end) // 60}:{int(s.end) % 60:02d} de "
                   f"{int(duracion) // 60}:{int(duracion) % 60:02d}", 8 + 80 * min(1.0, s.end / duracion))
    if not oidas:
        raise RuntimeError("Whisper no entendio ninguna palabra en el audio subido")

    alineado = alinear(texto, oidas) if texto else None
    if alineado:
        palabras, coincidencia = alineado
        texto_final, fuente = texto, "guion"
    else:
        palabras = [[round(a, 3), round(b, 3), w] for a, b, w in oidas]
        texto_final, fuente, coincidencia = " ".join(w for _a, _b, w in oidas), "transcripcion", 0.0
    with open(os.path.join(ctx.dir("voz"), "palabras.json"), "w", encoding="utf-8") as f:
        json.dump(palabras, f, ensure_ascii=False)
    with open(os.path.join(ctx.dir("voz"), "transcripcion.txt"), "w", encoding="utf-8") as f:
        f.write(" ".join(w for _a, _b, w in oidas))
    ctx.avisar("calculando tiempos de cada frase", 90)
    if not srt_de_palabras(texto_final, palabras, srt):
        raise RuntimeError("no se pudieron ordenar los tiempos de las frases")
    if pausa:
        ctx.avisar(f"silencios de mas de {pausa:g}s acortados: el audio dura {duracion:.1f}s", 91)
    ctx.avisar(f"audio propio: {len(palabras)} palabras, texto del "
               f"{'guion (' + str(round(coincidencia * 100)) + '% coincide)' if fuente == 'guion' else 'Whisper'}", 92)
    return duracion, {"texto": texto_final, "texto_de": fuente, "coincidencia": round(coincidencia, 3),
                      "idioma_detectado": info.language}
