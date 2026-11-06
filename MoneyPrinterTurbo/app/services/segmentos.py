"""Tramos de una voz a partir de su SRT: [(inicio, fin, texto), ...], para repartir planos con los tiempos de la voz."""

from app.services import subtitle


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
        segments.append((_srt_time_to_seconds(start_str), _srt_time_to_seconds(end_str), text.strip()))
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

    # normaliza: cada tramo empieza donde termina el anterior; el último cubre
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
