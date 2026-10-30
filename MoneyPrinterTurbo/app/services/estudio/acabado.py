"""
Acabado RAPIDO: voz + musica + subtitulos quemados con UNA pasada de ffmpeg.

El acabado clasico de MoneyPrinterTurbo (video.generate_video) compone cada
fotograma en Python con MoviePy: medido en el Estudio, 468 s para un video de
27 s. Aqui los subtitulos van como ASS (libass) y el audio con amix: segundos.

Requiere un ffmpeg con libass (el de apt/Docker y los builds de gyan.dev lo
traen). Si no lo tiene, render.py cae al acabado clasico.

Mapeo de estilos (los mismos controles que la web de MPT):
  sub_fondo      -> BorderStyle=3 (caja; en ASS la caja usa OutlineColour)
  sin fondo      -> BorderStyle=1 con contorno color_contorno / grosor_contorno
  sub_posicion   -> bottom | top | center | custom (+ sub_posicion_pct desde arriba)
  sub_fondo_redondeado -> no existe en ASS: se ignora (caja recta)
"""
import os
from functools import lru_cache

from loguru import logger
from PIL import ImageFont

from app.services import subtitle
from app.services import video as mpt_video
from app.services.estudio import medios
from app.utils import utils


@lru_cache(maxsize=4)
def tiene_libass(ffmpeg_bin: str) -> bool:
    r = medios.correr([ffmpeg_bin, "-hide_banner", "-filters"], timeout=20)
    return " subtitles " in r.stdout


@lru_cache(maxsize=32)
def familia_fuente(archivo: str) -> str:
    try:
        return ImageFont.truetype(os.path.join(utils.font_dir(), archivo), 20).getname()[0]
    except Exception:  # noqa: BLE001
        return "Arial"


def _color_ass(hexa: str, alfa: int = 0) -> str:
    h = (hexa or "#FFFFFF").lstrip("#")
    if len(h) != 6:
        h = "FFFFFF"
    r, g, b = h[0:2], h[2:4], h[4:6]
    return f"&H{alfa:02X}{b}{g}{r}".upper()


def _t_ass(seg: float) -> str:
    cs = int(round(seg * 100))
    h, cs = divmod(cs, 360000)
    m, cs = divmod(cs, 6000)
    s, cs = divmod(cs, 100)
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def _srt_t(ts: str) -> float:
    ts = ts.strip().replace(",", ".")
    h, m, s = ts.split(":")
    return int(h) * 3600 + int(m) * 60 + float(s)


def estilo_base(p: dict, w: int, h: int):
    """(linea `Style: Default,...`, prefijo de posicion para cada Dialogue)."""
    tam = int(p["tam_fuente"])
    posicion = p["sub_posicion"]
    alineacion, margen_v, prefijo = 2, int(h * 0.12), ""
    if posicion == "top":
        alineacion, margen_v = 8, int(h * 0.08)
    elif posicion == "center":
        alineacion, margen_v = 5, 0
    elif posicion == "custom":
        y = int(h * float(p["sub_posicion_pct"]) / 100)
        prefijo = f"{{\\an5\\pos({w // 2},{y})}}"
    if p["sub_fondo"]:
        borde, contorno, sombra = 3, max(6, tam // 6), 0
        color_contorno = _color_ass("#000000", 0x50)
    else:
        borde, contorno, sombra = 1, max(1.0, float(p["grosor_contorno"]) * 1.6), 0
        color_contorno = _color_ass(p["color_contorno"])
    margen_h = int(w * 0.08)
    estilo = (f"Style: Default,{familia_fuente(p['fuente'])},{tam},{_color_ass(p['color_texto'])},&H000000FF,"
              f"{color_contorno},&H80000000,0,0,0,0,100,100,0,0,{borde},{contorno},{sombra},{alineacion},"
              f"{margen_h},{margen_h},{margen_v},1")
    return estilo, prefijo


def cabecera(w: int, h: int, estilos: list) -> str:
    return f"""[Script Info]
ScriptType: v4.00+
PlayResX: {w}
PlayResY: {h}
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
""" + "\n".join(estilos) + """

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


def lineas_srt(srt: str):
    """[(inicio, fin, texto)] de un SRT."""
    salida = []
    for _i, tiempos, texto in subtitle.file_to_subtitles(srt):
        if "-->" not in tiempos:
            continue
        a, b = tiempos.split("-->")
        salida.append((_srt_t(a), _srt_t(b), " ".join(texto.split())))
    return salida


def limpio(texto: str) -> str:
    """Texto seguro dentro de un Dialogue (las llaves abren etiquetas ASS)."""
    return texto.replace("{", "(").replace("}", ")").replace("\\", "/")


def con_cambios(lineas, cambios):
    """Las lineas con el texto que corrigio el editor (`subs_texto`: {indice: texto};
    vacio la quita). Mismo numero de lineas y mismos tiempos: las marcas de Claude
    apuntan a las lineas por su indice."""
    if not isinstance(cambios, dict) or not cambios:
        return lineas
    salida = []
    for k, (a, b, t) in enumerate(lineas):
        nuevo = cambios.get(str(k))
        salida.append((a, b, t if nuevo is None else " ".join(str(nuevo).split())))
    return salida


def srt_a_ass(srt: str, ass: str, p: dict, w: int, h: int, cambios=None):
    estilo, prefijo = estilo_base(p, w, h)
    lineas = [f"Dialogue: 0,{_t_ass(a)},{_t_ass(b)},Default,,0,0,0,,{prefijo}{limpio(t)}"
              for a, b, t in con_cambios(lineas_srt(srt), cambios) if t]
    with open(ass, "w", encoding="utf-8") as f:
        f.write(cabecera(w, h, [estilo]) + "\n".join(lineas) + "\n")


def _ruta_filtro(ruta: str, cwd: str) -> str:
    """Ruta segura para el filtro subtitles: relativa (sin 'C:'), o escapada."""
    try:
        rel = os.path.relpath(ruta, cwd).replace("\\", "/")
        if ":" not in rel and "'" not in rel:
            return rel
    except ValueError:
        pass
    return "'" + ruta.replace("\\", "/").replace(":", "\\:").replace("'", "\\'") + "'"


@lru_cache(maxsize=64)
def entrada_fuerte(musica: str, _mtime: float = 0) -> float:
    """Segundo en que la cancion ya suena a su volumen normal (4 s seguidos a menos de 6 dB de su mediana).
    Con la musica baja y el ducking, una intro suave no se oye y parece que la musica entra tarde."""
    import numpy as np
    import subprocess
    r = subprocess.run([medios.ffmpeg(), "-v", "error", "-t", "90", "-i", musica, "-ac", "1", "-ar", "8000",
                        "-f", "f32le", "-"], capture_output=True, timeout=120, **medios.SIN_VENTANA)
    a = np.frombuffer(r.stdout or b"", np.float32)
    db = [20 * np.log10(np.sqrt(np.mean(a[i:i + 8000] ** 2)) + 1e-9) for i in range(0, len(a) - 8000, 8000)]
    if len(db) < 8:
        return 0.0
    umbral = float(np.median(db)) - 6
    k = next((i for i in range(len(db) - 3) if min(db[i:i + 4]) >= umbral), 0)
    return float(min(k, 60))


def acabar(combinado: str, audio: str, srt: str | None, p: dict, w: int, h: int,
           duracion: float, destino: str, ass: str | None = None, sfx: str | None = None,
           ducking: bool = False, color: str | None = None, ass_extra: str | None = None):
    """`ass`: subtitulos ya preparados (edicion editorial) en vez de convertir `srt`.
    `ass_extra`: textos propios del editor, encima de los subtitulos.
    Musica: `musica_desde`/`musica_hasta` (segundos del video) y `musica_offset`
    (segundo de la cancion por el que entra), del editor.
    `sfx`: pista de efectos (misma duracion que el video). `ducking`: la musica
    baja sola mientras habla la voz. `color`: filtros de color/grano que van ANTES
    de los subtitulos (el texto no se tine ni lleva grano)."""
    ff = medios.ffmpeg()
    carpeta = os.path.dirname(destino)
    musica = mpt_video.get_bgm_file(bgm_type="random" if p.get("musica") else "",
                                    bgm_file="" if p.get("musica") in ("", "random", None) else p["musica"])
    args = [ff, "-hide_banner", "-loglevel", "error", "-y", "-i", combinado, "-i", audio]
    m_desde = max(0.0, float(p.get("musica_desde") or 0))
    m_hasta = min(duracion, float(p.get("musica_hasta") or duracion))
    m_offset = max(0.0, float(p.get("musica_offset") or 0))
    if musica and "musica_offset" not in p:   # sin offset del editor: se salta la intro suave de la cancion
        m_offset = entrada_fuerte(musica, os.path.getmtime(musica))
    if musica and m_hasta - m_desde < 0.2:
        musica = ""
    if musica:
        args += ["-stream_loop", "-1"] + (["-ss", f"{m_offset:.3f}"] if m_offset else []) + ["-i", musica]
    if sfx:
        args += ["-i", sfx]
    i_sfx = 3 if musica else 2

    filtros = []
    if srt and not ass:
        ass = os.path.join(carpeta, "subtitulos.ass")
        srt_a_ass(srt, ass, p, w, h)
    if ass or color or ass_extra:
        cadena = [color] if color else []
        for archivo in (ass, ass_extra):
            if archivo:
                cadena.append(f"subtitles={_ruta_filtro(archivo, carpeta)}:"
                              f"fontsdir={_ruta_filtro(utils.font_dir(), carpeta)}")
        filtros.append("[0:v]" + ",".join(cadena) + "[v]")
    vv = float(p["volumen_voz"])
    pistas = ["[voz]"]
    if musica and ducking:
        filtros.append(f"[1:a]volume={vv},asplit=2[voz][guia]")
    else:
        filtros.append(f"[1:a]volume={vv}[voz]")
    if musica:
        mv = float(p["musica_volumen"])
        largo = m_hasta - m_desde
        cadena = (f"[2:a]atrim=0:{largo:.3f},asetpts=PTS-STARTPTS,volume={mv},"
                  f"afade=t=out:st={max(0.0, largo - 2):.2f}:d={min(2.0, largo):.2f}")
        if m_desde > 0:
            cadena += f",adelay={int(m_desde * 1000)}:all=1"
        if ducking:
            # La voz controla un compresor sobre la musica: baja al hablar, vuelve en las pausas.
            filtros.append(cadena + "[mus0];[mus0][guia]sidechaincompress="
                           "threshold=0.025:ratio=5:attack=25:release=450:makeup=1.4[mus]")
        else:
            filtros.append(cadena + "[mus]")
        pistas.append("[mus]")
    if sfx:
        filtros.append(f"[{i_sfx}:a]volume={float(p.get('sfx_volumen', 1.0))}[sfx]")
        pistas.append("[sfx]")
    if len(pistas) > 1:
        filtros.append("".join(pistas) + f"amix=inputs={len(pistas)}:duration=first:"
                       "dropout_transition=0:normalize=0[a]")
    else:
        filtros.append("[voz]anull[a]")
    recodificar = bool(ass or color or ass_extra)
    args += ["-filter_complex", ";".join(filtros),
             "-map", "[v]" if recodificar else "0:v", "-map", "[a]"]

    if recodificar:
        codec = mpt_video._get_effective_video_codec(p.get("codec") or None)
        args += ["-c:v", codec]
        if codec in ("libx264", "libx265"):
            args += ["-preset", "veryfast", "-crf", "20"]  # "fast" tardaba el doble en CPU modesta
        args += ["-pix_fmt", "yuv420p"]
    else:
        args += ["-c:v", "copy"]
    args += ["-c:a", "aac", "-b:a", "192k", "-t", f"{duracion:.3f}", "-movflags", "+faststart", destino]

    logger.info(f"acabado rapido: subtitulos={'si' if ass else 'no'}, musica={os.path.basename(musica) if musica else 'no'}"
                f"{', efectos de sonido' if sfx else ''}{', musica bajo la voz' if ducking else ''}")
    r = medios.correr(args, timeout=3600, cwd=carpeta)
    if r.returncode != 0 or not os.path.exists(destino):
        raise RuntimeError(f"ffmpeg fallo en el acabado: {r.stderr[-600:]}")
