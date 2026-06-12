"""
Orquestador del flujo NUEVO: "video de imágenes" estilo Zenn.

NO toca el pipeline existente. Reutiliza sus piezas ya probadas:
  - task.generate_script   -> guion (o el que pase el usuario)
  - task.generate_audio    -> voz TTS  (+ sub_maker para timestamps)
  - subtitle/voz           -> SRT con timestamps exactos de ESA voz
  - kie_image              -> 1 imagen por segmento (NUEVO)
  - (combine local)        -> cada imagen dura exactamente su segmento (NUEVO)
  - video.generate_video   -> voz + música + subtítulos quemados + códec

La sincronización voz<->imagen está garantizada porque los timestamps salen de
la misma voz: la imagen cambia justo cuando cambia la narración.
"""

import math
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from os import path

from loguru import logger
from moviepy import ColorClip, CompositeVideoClip, ImageClip

from app.config import config
from app.models import const
from app.models.schema import ImageVideoParams, VideoAspect
from app.services import kie_image, subtitle, video, voice
from app.services import state as sm
from app.services import task as tm
from app.utils import utils


def _srt_time_to_seconds(ts: str) -> float:
    # formato: "00:00:07,000"
    ts = ts.strip().replace(",", ".")
    hh, mm, ss = ts.split(":")
    return int(hh) * 3600 + int(mm) * 60 + float(ss)


def parse_segments(subtitle_path: str):
    """Devuelve [(start, end, text), ...] a partir del SRT."""
    rows = subtitle.file_to_subtitles(subtitle_path)
    segments = []
    for _index, times_line, text in rows:
        if "-->" not in times_line:
            continue
        start_str, end_str = times_line.split("-->")
        segments.append(
            (
                _srt_time_to_seconds(start_str),
                _srt_time_to_seconds(end_str),
                text.strip(),
            )
        )
    return segments


def merge_short_segments(segments, min_duration: float, total_duration: float):
    """
    Fusiona segmentos más cortos que min_duration con el siguiente, y estira el
    último hasta total_duration para que el video dure EXACTO lo que la voz.
    """
    if not segments:
        return []

    merged = []
    cur_start, cur_end, cur_text = segments[0]
    for start, end, text in segments[1:]:
        if (cur_end - cur_start) < min_duration:
            cur_end = end
            cur_text = f"{cur_text} {text}".strip()
        else:
            merged.append((cur_start, cur_end, cur_text))
            cur_start, cur_end, cur_text = start, end, text
    merged.append((cur_start, cur_end, cur_text))

    # normaliza: cada imagen empieza donde termina la anterior; la última cubre
    # hasta el final del audio para que no quede un hueco al cierre.
    normalized = []
    for i, (start, end, text) in enumerate(merged):
        next_start = merged[i + 1][0] if i + 1 < len(merged) else total_duration
        seg_end = max(next_start, start + 0.1)
        normalized.append((start, seg_end, text))
    if normalized:
        s, _e, t = normalized[-1]
        normalized[-1] = (s, total_duration, t)
    return normalized


def expand_segments_to_target(segments, target: int):
    """
    Si el audio produce MENOS segmentos que el tope pedido, subdivide los más
    largos para acercarse a `target`. Así max_images=10 da ~10 imágenes aunque
    el audio solo tuviera 7 pausas naturales.
    Nunca crea segmentos de menos de 1 segundo.
    """
    MIN_SEG = 1.0
    result = list(segments)
    while len(result) < target:
        # busca el segmento más largo que se pueda dividir
        best = max(range(len(result)), key=lambda i: result[i][1] - result[i][0])
        s, e, text = result[best]
        mid = (s + e) / 2
        if (mid - s) < MIN_SEG or (e - mid) < MIN_SEG:
            break  # ningún segmento es divisible — no se puede llegar a target
        half = len(text) // 2
        # cortar en el espacio más cercano al centro del texto
        cut = text.rfind(" ", 0, half) if " " in text[:half] else half
        t1 = text[:cut].strip() or text
        t2 = text[cut:].strip() or text
        result[best:best + 1] = [(s, mid, t1), (mid, e, t2)]
    return result


def build_prompt(scene_text: str, params: ImageVideoParams) -> str:
    """
    Prompt por imagen = estilo fijo (consistencia) + temática elegida + lo que
    se narra en ese segmento. Así el look es uniforme y encaja con el guion.
    """
    parts = [params.kie_image_style or ""]
    if params.kie_theme:
        parts.append(f"Theme/topic: {params.kie_theme}.")
    if scene_text:
        parts.append(f"Scene to illustrate: {scene_text}")
    return " ".join(p.strip() for p in parts if p and p.strip())


def _nearest_image(results, i):
    """Busca la imagen exitosa más cercana al índice i (para rellenar fallos)."""
    total = len(results)
    for dist in range(1, total):
        for j in (i - dist, i + dist):
            if 0 <= j < total and results[j] is not None:
                return results[j]
    return None


def _load_local_images(params: ImageVideoParams, total: int) -> list:
    """
    Carga las imágenes locales y las distribuye/cicla para cubrir `total` segmentos.
    - Si hay más imágenes que segmentos: usa las primeras `total`.
    - Si hay menos: cicla (img1, img2, img1, img2...) hasta completar.
    """
    local_videos_dir = utils.storage_dir("local_videos")
    files = params.local_image_files or []
    if not files:
        raise ValueError("image_source='local' pero no se enviaron local_image_files")

    # Validar que existen y son imágenes
    valid = []
    allowed_ext = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
    for fname in files:
        # solo nombre de archivo, sin path traversal
        safe_name = path.basename(fname)
        full = path.join(local_videos_dir, safe_name)
        ext = path.splitext(safe_name)[1].lower()
        if ext not in allowed_ext:
            logger.warning(f"archivo ignorado (no es imagen): {safe_name}")
            continue
        if not path.exists(full):
            logger.warning(f"imagen local no encontrada: {full}")
            continue
        valid.append(full)

    if not valid:
        raise ValueError("No se encontraron imágenes locales válidas en storage/local_videos/")

    logger.info(f"imágenes locales disponibles: {len(valid)}, segmentos: {total}")

    # Distribuir/ciclar
    result = []
    for i in range(total):
        result.append(valid[i % len(valid)])
    return result


def generate_images(task_id, params: ImageVideoParams, segments):
    """
    Genera/carga una imagen por segmento.
    - image_source="kie"   → genera con Kie AI en paralelo (comportamiento original)
    - image_source="local" → usa imágenes subidas por el usuario, sin costo
    """
    total = len(segments)
    source = (params.image_source or "kie").lower()
    logger.info(f"image_source recibido: '{source}' · local_image_files: {len(params.local_image_files or [])} archivos")

    # ── MODO LOCAL ────────────────────────────────────────────────────────────
    if source == "local":
        logger.info(f"modo local: distribuyendo {total} imágenes locales")
        results = _load_local_images(params, total)
        sm.state.update_task(task_id, progress=80)
        return results

    # ── MODO KIE AI (paralelo) ────────────────────────────────────────────────
    images_dir = path.join(utils.task_dir(task_id), "images")
    os.makedirs(images_dir, exist_ok=True)

    results = [None] * total
    max_workers = max(1, int(config.app.get("kie_max_concurrency", 6)))
    logger.info(f"generando {total} imágenes Kie en paralelo (concurrencia={max_workers})")

    def work(i, text):
        prompt = build_prompt(text, params)
        save_path = path.join(images_dir, f"img-{i + 1:04d}.png")
        kie_image.generate_image(
            prompt=prompt,
            save_path=save_path,
            aspect_ratio=params.kie_aspect_ratio or "9:16",
            # Forzado a 1K: 2K cobra 10 créditos/imagen, 1K solo 6.
            resolution="1K",
        )
        return i, save_path

    completed = 0
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futures = {
            ex.submit(work, i, seg[2]): i for i, seg in enumerate(segments)
        }
        for fut in as_completed(futures):
            i = futures[fut]
            try:
                idx, save_path = fut.result()
                results[idx] = save_path
            except Exception as e:
                logger.error(f"falló la imagen {i + 1}/{total}: {e}")
            completed += 1
            progress = 30 + int(50 * completed / max(total, 1))
            sm.state.update_task(task_id, progress=progress)

    # rellena los fallos con la imagen exitosa más cercana
    for i in range(total):
        if results[i] is None:
            nb = _nearest_image(results, i)
            if nb is None:
                raise RuntimeError("todas las imágenes de Kie fallaron")
            results[i] = nb

    return results


def combine_image_clips(
    task_id,
    params: ImageVideoParams,
    segments,
    image_paths,
    combined_path: str,
):
    """
    Arma un video SILENCIOSO donde cada imagen dura EXACTAMENTE su segmento.
    Reutiliza los helpers de códec/concat de video.py. La voz y la música se
    agregan después en video.generate_video.
    """
    aspect = VideoAspect(params.video_aspect)
    video_width, video_height = aspect.to_resolution()
    output_dir = path.dirname(combined_path)
    codec = params.video_codec or video._get_configured_video_codec()

    clip_files = []
    for i, ((start, end, _text), image_path) in enumerate(zip(segments, image_paths)):
        duration = max(end - start, 0.1)
        clip = ImageClip(image_path).with_duration(duration)

        clip_w, clip_h = clip.size
        if clip_w != video_width or clip_h != video_height:
            clip_ratio = clip_w / clip_h
            video_ratio = video_width / video_height
            if abs(clip_ratio - video_ratio) < 1e-3:
                clip = clip.resized(new_size=(video_width, video_height))
            else:
                # letterbox: encaja la imagen sin deformar sobre fondo blanco
                if clip_ratio > video_ratio:
                    scale = video_width / clip_w
                else:
                    scale = video_height / clip_h
                new_w, new_h = int(clip_w * scale), int(clip_h * scale)
                background = ColorClip(
                    size=(video_width, video_height), color=(255, 255, 255)
                ).with_duration(duration)
                resized = clip.resized(new_size=(new_w, new_h)).with_position("center")
                clip = CompositeVideoClip([background, resized]).with_duration(duration)

        clip_file = path.join(output_dir, f"img-clip-{i + 1:04d}.mp4")
        video._write_videofile_with_codec_fallback(
            clip,
            clip_file,
            codec=codec,
            logger=None,
            fps=30,
        )
        video.close_clip(clip)
        clip_files.append(clip_file)

    if len(clip_files) == 1:
        import shutil

        shutil.copy(clip_files[0], combined_path)
    else:
        video.concat_video_clips_with_ffmpeg(
            clip_files=clip_files,
            output_file=combined_path,
            threads=params.n_threads or 2,
            output_dir=output_dir,
        )
    video.delete_files(clip_files)
    return combined_path


def _save_chapters(chapters_path: str, segments):
    """
    Guarda los capítulos en formato YouTube:
    0:00 Descripción del segmento
    0:45 Siguiente segmento
    ...
    El primer capítulo SIEMPRE empieza en 0:00 (requisito de YouTube).
    """
    lines = []
    for i, (start, _end, text) in enumerate(segments):
        t = int(start) if i > 0 else 0  # YouTube requiere 0:00 como primer capítulo
        mm = t // 60
        ss = t % 60
        # Limitar texto a ~60 chars para que quede limpio en YouTube
        label = text[:60].strip().rstrip(".,;:")
        lines.append(f"{mm}:{ss:02d} {label}")
    with open(chapters_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    logger.info(f"chapters.txt guardado: {len(lines)} capítulos")


def _build_timing_srt(task_id, params, video_script, sub_maker, audio_file):
    """
    Genera un SRT con timestamps SIEMPRE (aunque el usuario no quiera subtítulos
    quemados), porque los timestamps definen la duración de cada imagen.
    """
    subtitle_path = path.join(utils.task_dir(task_id), "subtitle.srt")
    provider = config.app.get("subtitle_provider", "edge").strip().lower()

    if provider == "edge" and sub_maker is not None:
        voice.create_subtitle(
            text=video_script, sub_maker=sub_maker, subtitle_file=subtitle_path
        )
    if not os.path.exists(subtitle_path):
        subtitle.create(audio_file=audio_file, subtitle_file=subtitle_path)
        subtitle.correct(subtitle_file=subtitle_path, video_script=video_script)
    return subtitle_path


def start(task_id, params: ImageVideoParams, stop_at: str = "video"):
    logger.info(f"start IMAGE task: {task_id}")
    sm.state.update_task(task_id, state=const.TASK_STATE_PROCESSING, progress=5)

    # 1. Guion (reutilizado)
    video_script = tm.generate_script(task_id, params)
    if not video_script or "Error: " in video_script:
        sm.state.update_task(task_id, state=const.TASK_STATE_FAILED)
        return

    # 2. Voz TTS (reutilizado)
    sm.state.update_task(task_id, progress=15)
    audio_file, audio_duration, sub_maker = tm.generate_audio(
        task_id, params, video_script
    )
    if not audio_file:
        sm.state.update_task(task_id, state=const.TASK_STATE_FAILED)
        return

    # 3. SRT con timestamps de ESA voz (para sincronizar imágenes)
    sm.state.update_task(task_id, progress=25)
    subtitle_path = _build_timing_srt(
        task_id, params, video_script, sub_maker, audio_file
    )
    segments = parse_segments(subtitle_path)
    if not segments:
        logger.error("no se pudieron extraer segmentos/timestamps del audio")
        sm.state.update_task(task_id, state=const.TASK_STATE_FAILED)
        return

    # Duración mínima efectiva: respeta el tope de imágenes (max_images) subiendo
    # la duración por imagen si hiciera falta, para nunca pasarse del presupuesto.
    min_dur = float(params.min_image_duration or 2.0)
    max_images = int(getattr(params, "max_images", 0) or 0)

    # En modo LOCAL las imágenes son gratis: usar TODAS las que subió el usuario.
    # El tope max_images (pensado para limitar el costo de Kie) no aplica aquí.
    source_check = (getattr(params, "image_source", "kie") or "kie").lower()
    if source_check == "local":
        n_local = len(params.local_image_files or [])
        if n_local > 0:
            max_images = n_local
            logger.info(f"modo local: objetivo fijado a {n_local} imágenes (todas las subidas)")

    if max_images > 0:
        min_dur = max(min_dur, float(audio_duration) / max_images)

    segments = merge_short_segments(
        segments,
        min_duration=min_dur,
        total_duration=float(audio_duration),
    )

    # Si el audio produjo MENOS segmentos que el tope pedido, subdividir
    # los más largos para llegar al número deseado.
    if max_images > 0 and len(segments) < max_images:
        segments = expand_segments_to_target(segments, max_images)

    n_imgs = len(segments)
    if source_check == "local":
        logger.info(f"segmentos finales (imágenes a usar): {n_imgs} · modo local ($0.00 en Kie)")
    else:
        credits = n_imgs * 6
        logger.info(
            f"segmentos finales (imágenes a generar): {n_imgs} "
            f"≈ {credits} créditos ≈ ${credits / 1000 * 5:.2f}"
        )

    if stop_at == "segments":
        sm.state.update_task(
            task_id, state=const.TASK_STATE_COMPLETE, progress=100,
            segments=segments,
        )
        return {"segments": segments}

    # 4. Imágenes con Kie AI (NUEVO) — 1 por segmento
    image_paths = generate_images(task_id, params, segments)

    # 5. Video silencioso: cada imagen con su duración exacta (NUEVO)
    sm.state.update_task(task_id, progress=82)
    combined_path = path.join(utils.task_dir(task_id), "combined-1.mp4")
    combine_image_clips(task_id, params, segments, image_paths, combined_path)

    # 6. Render final: voz + música + subtítulos quemados + códec (reutilizado)
    sm.state.update_task(task_id, progress=90)
    final_path = path.join(utils.task_dir(task_id), "final-1.mp4")
    burn_subtitle = subtitle_path if params.subtitle_enabled else ""
    video.generate_video(
        video_path=combined_path,
        audio_path=audio_file,
        subtitle_path=burn_subtitle,
        output_file=final_path,
        params=params,
    )

    # Generar chapters.txt con timestamps para YouTube
    chapters_path = path.join(utils.task_dir(task_id), "chapters.txt")
    _save_chapters(chapters_path, segments)

    kwargs = {
        "videos": [final_path],
        "combined_videos": [combined_path],
        "script": video_script,
        "audio_file": audio_file,
        "audio_duration": audio_duration,
        "subtitle_path": subtitle_path,
        "image_count": len(image_paths),
        "chapters_path": chapters_path,
    }
    sm.state.update_task(
        task_id, state=const.TASK_STATE_COMPLETE, progress=100, **kwargs
    )
    logger.success(
        f"task {task_id} finished: {len(image_paths)} imágenes -> {final_path}"
    )
    return kwargs
