#!/usr/bin/env python3
"""
CLI para generar videos de forma automática contra el backend de VideoAI Studio.

Cubre las TRES formas de generar que tiene la web, vía el REST existente:

  --modo kie     Video estilo Zenn con imágenes generadas por IA (Kie AI).   [default]
  --modo local   Video estilo Zenn con TUS imágenes (sube una carpeta).
  --modo video   Video clásico con clips de Pexels / Pixabay / locales.

Flujo end-to-end en todos los modos:
  1. POST /image-video  (kie/local)  ó  POST /videos  (video)  -> task_id
  2. GET  /tasks/{task_id}            -> polling hasta terminar
  3. GET  /download/{ruta}            -> descarga el MP4 a una carpeta

Expone TODOS los controles de la web (voz, audio, subtítulos, estilo, imágenes),
así que el resultado es 1:1 con lo que generas en el sitio. No toca el backend.
Pensado para cron, terminal o que lo dispare otro agente/app (ej. Hermes).

Ejemplos:
  # Kie AI, con perfil guardado
  python zenn_cli.py --perfil perfil_zenn.json --tema "Mundial 2026" --guion g.txt --max-images 207

  # Imágenes locales (sube y ordena alfabéticamente la carpeta)
  python zenn_cli.py --modo local --tema "Mi video" --guion g.txt --imagenes-dir ./mis_imagenes

  # Video clásico con clips de Pexels
  python zenn_cli.py --modo video --tema "Datos curiosos del espacio" --fuente-clips pexels

  # Por lotes (un tema por línea; el backend genera cada guion)
  python zenn_cli.py --perfil perfil_zenn.json --lote temas.txt --parrafos 30

Cualquier flag CLI SOBREESCRIBE lo que venga en el --perfil.

Variables de entorno:
  MPT_API_BASE   URL base de la API (default: https://virales.saraviamtech.com/api/mpt/v1)
  MPT_BASIC_AUTH usuario:password si activaste auth básica en Traefik (opcional)
"""

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

import requests

DEFAULT_API_BASE = os.environ.get(
    "MPT_API_BASE", "https://virales.saraviamtech.com/api/mpt/v1"
)

DEFAULT_STYLE = (
    "The image must look like an extremely simple beginner drawing made in MS Paint. "
    "It should look like someone who is not good at drawing created it quickly by hand. "
    "Plain white background, thick crude lines, flat colors, no shading, no 3D, "
    "not cinematic, not realistic, no text, no watermark."
)

IMG_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}

# Defaults de cada opción. El perfil JSON y los flags CLI los sobreescriben.
DEFAULTS = {
    # modo
    "modo": "kie",  # kie | local | video
    # guion
    "idioma": "",
    "parrafos": 20,
    "instrucciones": "",
    # imágenes / video Zenn
    "aspect": "9:16",
    "codec": "libx264",
    "tematica": "",
    "estilo": DEFAULT_STYLE,
    "min_dur": 2.5,
    "max_images": 0,
    # video clásico (modo video)
    "fuente_clips": "pexels",       # pexels | pixabay | local
    "terminos": "",                  # palabras clave de búsqueda (coma-separadas)
    "concat": "random",              # random | sequential
    "transicion": "",                # '', FadeIn, FadeOut, SlideIn, SlideOut, Shuffle
    "dur_clip": 5,                   # segundos por clip
    # voz / audio
    "voz": "es-ES-ElviraNeural-Female",
    "voz_velocidad": 1.0,
    "voz_volumen": 1.0,
    "sin_voz": False,
    "musica": "random",
    "musica_volumen": 0.2,
    # subtítulos
    "sin_subtitulos": False,
    "sub_posicion": "bottom",
    "fuente": "MicrosoftYaHeiBold.ttc",
    "tam_fuente": 60,
    "color_texto": "#FFFFFF",
    "color_contorno": "#000000",
    "grosor_contorno": 1.5,
    # ejecución
    "timeout": 7200,
}


def _auth():
    raw = os.environ.get("MPT_BASIC_AUTH", "").strip()
    if raw and ":" in raw:
        u, p = raw.split(":", 1)
        return (u, p)
    return None


def _slug(text: str, maxlen: int = 50) -> str:
    s = re.sub(r"[^\w\s-]", "", text.lower()).strip()
    s = re.sub(r"[\s_-]+", "-", s)
    return s[:maxlen].strip("-") or "video"


def _post(api_base: str, endpoint: str, payload: dict) -> str:
    r = requests.post(f"{api_base}/{endpoint}", json=payload, auth=_auth(), timeout=60)
    if not r.ok:
        try:
            detail = r.json().get("detail") or r.text
        except Exception:
            detail = r.text
        raise RuntimeError(f"Error al crear la tarea (HTTP {r.status_code}): {detail}")
    task_id = (r.json().get("data") or {}).get("task_id")
    if not task_id:
        raise RuntimeError(f"El backend no devolvió task_id: {r.text}")
    return task_id


def subir_imagenes(api_base: str, carpeta: str) -> list:
    """Sube todas las imágenes de una carpeta (orden alfabético) y devuelve sus nombres."""
    p = Path(carpeta)
    if not p.is_dir():
        raise RuntimeError(f"No es una carpeta válida: {carpeta}")
    archivos = sorted(
        [f for f in p.iterdir() if f.suffix.lower() in IMG_EXTS],
        key=lambda f: f.name.lower(),
    )
    if not archivos:
        raise RuntimeError(f"No hay imágenes ({', '.join(IMG_EXTS)}) en {carpeta}")
    nombres = []
    print(f"  subiendo {len(archivos)} imágenes…", flush=True)
    for f in archivos:
        with open(f, "rb") as fh:
            resp = requests.post(
                f"{api_base}/video_materials",
                files={"file": (f.name, fh)},
                auth=_auth(),
                timeout=120,
            )
        if not resp.ok:
            raise RuntimeError(f"Falló subir {f.name} (HTTP {resp.status_code})")
        nombres.append((resp.json().get("data") or {}).get("file") or f.name)
    return nombres


def esperar_tarea(api_base: str, task_id: str, timeout: int, intervalo: int = 5) -> dict:
    deadline = time.time() + timeout
    last_progress = -1
    while time.time() < deadline:
        time.sleep(intervalo)
        r = requests.get(f"{api_base}/tasks/{task_id}", auth=_auth(), timeout=60)
        if not r.ok:
            print(f"  · poll HTTP {r.status_code}, reintentando…", flush=True)
            continue
        data = (r.json() or {}).get("data") or {}
        progress = data.get("progress", 0)
        state = data.get("state")
        if progress != last_progress:
            print(f"  · {progress}%", flush=True)
            last_progress = progress
        if state == 1:
            return data
        if state == -1:
            raise RuntimeError(data.get("message") or "La tarea falló en el backend")
    raise TimeoutError(
        f"La tarea {task_id} no terminó en {timeout}s "
        f"(sigue corriendo en el backend; revísala luego en /tasks/{task_id})"
    )


def descargar(api_base: str, task_id: str, file_path: str, out_dir: Path, nombre: str,
              sufijo: str = "") -> Path:
    filename = os.path.basename(file_path.replace("\\", "/"))
    ext = os.path.splitext(filename)[1] or ".mp4"
    url = f"{api_base}/download/{task_id}/{filename}"
    out_dir.mkdir(parents=True, exist_ok=True)
    destino = out_dir / f"{_slug(nombre)}-{task_id[:8]}{sufijo}{ext}"
    with requests.get(url, auth=_auth(), stream=True, timeout=300) as r:
        r.raise_for_status()
        with open(destino, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
    return destino


def _subs(cfg: dict) -> dict:
    """Bloque común de voz/audio/subtítulos para cualquier modo."""
    return {
        "voice_name": None if cfg["sin_voz"] else cfg["voz"],
        "voice_volume": cfg["voz_volumen"],
        "voice_rate": cfg["voz_velocidad"],
        "bgm_type": cfg["musica"],
        "bgm_volume": cfg["musica_volumen"],
        "subtitle_enabled": not cfg["sin_subtitulos"],
        "subtitle_position": cfg["sub_posicion"],
        "font_name": cfg["fuente"],
        "font_size": cfg["tam_fuente"],
        "text_fore_color": cfg["color_texto"],
        "stroke_color": cfg["color_contorno"],
        "stroke_width": cfg["grosor_contorno"],
    }


def payload_zenn(cfg: dict, tema: str, guion: str | None, imagenes: list | None = None) -> dict:
    """Modos kie y local (endpoint /image-video)."""
    p = {
        "video_subject": tema,
        "video_script": guion or None,
        "video_language": cfg["idioma"] or None,
        "paragraph_number": cfg["parrafos"],
        "video_script_prompt": cfg["instrucciones"] or None,
        "video_aspect": cfg["aspect"],
        "video_codec": cfg["codec"],
        "kie_theme": cfg["tematica"] or None,
        "kie_image_style": cfg["estilo"] or DEFAULT_STYLE,
        "kie_aspect_ratio": cfg["aspect"],
        "kie_resolution": "1K",
        "min_image_duration": cfg["min_dur"],
        "max_images": cfg["max_images"] if cfg["max_images"] > 0 else None,
        "image_source": cfg["modo"],  # "kie" o "local"
        "local_image_files": imagenes if cfg["modo"] == "local" else None,
        "n_threads": 2,
        **_subs(cfg),
    }
    return {k: v for k, v in p.items() if v is not None}


def payload_video(cfg: dict, tema: str, guion: str | None) -> dict:
    """Modo video clásico (endpoint /videos, clips Pexels/Pixabay/local)."""
    terminos = [t.strip() for t in cfg["terminos"].split(",") if t.strip()] or None
    p = {
        "video_subject": tema,
        "video_script": guion or "",
        "video_language": cfg["idioma"] or "",
        "paragraph_number": cfg["parrafos"],
        "video_script_prompt": cfg["instrucciones"] or "",
        "video_aspect": cfg["aspect"],
        "video_codec": cfg["codec"],
        "video_source": cfg["fuente_clips"],
        "video_terms": terminos,
        "video_concat_mode": cfg["concat"],
        "video_transition_mode": cfg["transicion"] or None,
        "video_clip_duration": cfg["dur_clip"],
        "video_count": 1,
        "n_threads": 2,
        **_subs(cfg),
    }
    return {k: v for k, v in p.items() if v is not None}


def generar_uno(cfg, api_base, out_dir, tema, guion, con_capitulos, imagenes_dir):
    modo = cfg["modo"]
    print(f"\n▶ [{modo}] Generando: {tema}", flush=True)

    if modo == "video":
        task_id = _post(api_base, "videos", payload_video(cfg, tema, guion))
    else:
        imagenes = None
        if modo == "local":
            fuente = imagenes_dir or ""
            if not fuente:
                raise RuntimeError("modo local requiere --imagenes-dir <carpeta>")
            imagenes = subir_imagenes(api_base, fuente)
            print(f"  {len(imagenes)} imágenes listas (orden alfabético)", flush=True)
        task_id = _post(api_base, "image-video", payload_zenn(cfg, tema, guion, imagenes))

    print(f"  task_id: {task_id}", flush=True)
    data = esperar_tarea(api_base, task_id, timeout=cfg["timeout"])
    videos = data.get("videos") or []
    if not videos:
        raise RuntimeError("La tarea terminó pero no devolvió ningún video")
    destino = descargar(api_base, task_id, videos[0], out_dir, tema)
    img_count = data.get("image_count")
    extra = f" · {img_count} imágenes" if img_count else ""
    print(f"✔ Listo{extra} → {destino}", flush=True)
    if con_capitulos and data.get("chapters_path"):
        try:
            cap = descargar(api_base, task_id, data["chapters_path"], out_dir, tema, "-chapters")
            print(f"  capítulos → {cap}", flush=True)
        except Exception as e:
            print(f"  (no se pudo descargar chapters.txt: {e})", flush=True)
    return destino


def cargar_config(args) -> dict:
    """Combina: DEFAULTS < perfil JSON < flags CLI explícitos."""
    cfg = dict(DEFAULTS)
    if args.perfil:
        perfil = json.loads(Path(args.perfil).read_text(encoding="utf-8"))
        desconocidas = set(perfil) - set(DEFAULTS)
        if desconocidas:
            print(f"⚠ claves ignoradas en el perfil: {sorted(desconocidas)}", file=sys.stderr)
        cfg.update({k: v for k, v in perfil.items() if k in DEFAULTS})
    for key in DEFAULTS:
        if key in args._explicit:
            cfg[key] = getattr(args, key)
    return cfg


def main():
    p = argparse.ArgumentParser(
        description="Genera videos por CLI en los 3 modos del sitio (kie / local / video), con control total.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument("--tema", help="Tema del video (un solo video).")
    src.add_argument("--lote", help="Archivo .txt con un tema por línea (varios videos).")

    p.add_argument("--modo", choices=["kie", "local", "video"], help="Forma de generar el video.")
    p.add_argument("--perfil", help="Archivo JSON con tu configuración base.")
    p.add_argument("--guion", help="Ruta a archivo de guion (o texto directo). Si se omite, el backend lo genera.")
    p.add_argument("--imagenes-dir", dest="imagenes_dir", help="Carpeta de imágenes (modo local).")
    p.add_argument("--out", default="./videos_generados", help="Carpeta de descarga.")
    p.add_argument("--api-base", default=DEFAULT_API_BASE, help="URL base de la API.")
    p.add_argument("--capitulos", action="store_true", help="Descargar también el chapters.txt de YouTube.")

    # Guion
    p.add_argument("--idioma", help="Idioma del guion (ej. es-ES). Vacío = autodetectar.")
    p.add_argument("--parrafos", type=int, help="Nº de párrafos si el backend genera el guion.")
    p.add_argument("--instrucciones", help="Instrucciones extra para el guion.")

    # Imágenes / video Zenn
    p.add_argument("--aspect", choices=["9:16", "16:9", "1:1"], help="Relación de aspecto.")
    p.add_argument("--codec", help="Codec de video (libx264, h264_nvenc, h264_amf, h264_qsv).")
    p.add_argument("--tematica", help="Temática/nicho para las imágenes (kie_theme).")
    p.add_argument("--estilo", help="Estilo visual de las imágenes (kie_image_style).")
    p.add_argument("--min-dur", dest="min_dur", type=float, help="Duración mínima por imagen (s).")
    p.add_argument("--max-images", dest="max_images", type=int, help="Tope de imágenes (0 = sin tope).")

    # Video clásico
    p.add_argument("--fuente-clips", dest="fuente_clips", choices=["pexels", "pixabay", "local"], help="Fuente de clips (modo video).")
    p.add_argument("--terminos", help="Palabras clave de búsqueda de clips, separadas por coma (modo video).")
    p.add_argument("--concat", choices=["random", "sequential"], help="Modo de concatenación de clips (modo video).")
    p.add_argument("--transicion", choices=["", "FadeIn", "FadeOut", "SlideIn", "SlideOut", "Shuffle"], help="Transición entre clips (modo video).")
    p.add_argument("--dur-clip", dest="dur_clip", type=int, help="Duración por clip en segundos (modo video).")

    # Voz / audio
    p.add_argument("--voz", help="Voz TTS (ej. es-ES-ElviraNeural-Female).")
    p.add_argument("--voz-velocidad", dest="voz_velocidad", type=float, help="Velocidad de voz (1.0 = normal).")
    p.add_argument("--voz-volumen", dest="voz_volumen", type=float, help="Volumen de voz.")
    p.add_argument("--sin-voz", dest="sin_voz", action="store_true", default=None, help="Sin narración.")
    p.add_argument("--musica", help="'random' o '' (sin música).")
    p.add_argument("--musica-volumen", dest="musica_volumen", type=float, help="Volumen música de fondo (0-1).")

    # Subtítulos
    p.add_argument("--sin-subtitulos", dest="sin_subtitulos", action="store_true", default=None, help="Desactivar subtítulos.")
    p.add_argument("--sub-posicion", dest="sub_posicion", choices=["top", "center", "bottom"], help="Posición de subtítulos.")
    p.add_argument("--fuente", help="Fuente de subtítulos (ej. MicrosoftYaHeiBold.ttc).")
    p.add_argument("--tam-fuente", dest="tam_fuente", type=int, help="Tamaño de fuente (px).")
    p.add_argument("--color-texto", dest="color_texto", help="Color del texto (#RRGGBB).")
    p.add_argument("--color-contorno", dest="color_contorno", help="Color del contorno (#RRGGBB).")
    p.add_argument("--grosor-contorno", dest="grosor_contorno", type=float, help="Grosor del contorno.")

    p.add_argument("--timeout", type=int, help="Máx. segundos de espera (default 2h).")

    argv = sys.argv[1:]
    args = p.parse_args(argv)
    explicit = set()
    for action in p._actions:
        for opt in action.option_strings:
            if opt in argv:
                explicit.add(action.dest)
    args._explicit = explicit

    cfg = cargar_config(args)
    out_dir = Path(args.out)

    guion = None
    if args.guion:
        gp = Path(args.guion)
        guion = gp.read_text(encoding="utf-8") if gp.exists() else args.guion

    if args.lote:
        temas = [l.strip() for l in Path(args.lote).read_text(encoding="utf-8").splitlines() if l.strip()]
        if not temas:
            print("El archivo de lote está vacío.", file=sys.stderr)
            sys.exit(1)
        print(f"Lote ({cfg['modo']}): {len(temas)} videos a generar.", flush=True)
        ok, fail = 0, 0
        for i, tema in enumerate(temas, 1):
            print(f"\n=== [{i}/{len(temas)}] ===", flush=True)
            try:
                generar_uno(cfg, args.api_base, out_dir, tema, None, args.capitulos, args.imagenes_dir)
                ok += 1
            except Exception as e:
                print(f"✘ Falló «{tema}»: {e}", file=sys.stderr, flush=True)
                fail += 1
        print(f"\nLote terminado: {ok} ok, {fail} fallidos.", flush=True)
        sys.exit(0 if fail == 0 else 1)
    else:
        try:
            generar_uno(cfg, args.api_base, out_dir, args.tema, guion, args.capitulos, args.imagenes_dir)
        except Exception as e:
            print(f"✘ Error: {e}", file=sys.stderr, flush=True)
            sys.exit(1)


if __name__ == "__main__":
    main()
