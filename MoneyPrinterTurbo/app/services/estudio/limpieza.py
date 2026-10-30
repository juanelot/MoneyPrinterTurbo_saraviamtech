"""
Liberar espacio: borra de cada proyecto SOLO lo que el Estudio vuelve a generar
solo si hace falta (cache de clips recortados e intermedios del montaje). Nunca
toca lo subido (recursos/, voz_propia/), el guion, la voz ni el video final.

Tras liberar, el proyecto sigue "al dia": el video final no cambia. Si luego se
vuelve a montar, los clips se rehacen (1-3 min).

Tambien cubre la Fabrica: su cache de escenas ya dibujadas (fabrica.liberar).
"""
import os
import shutil

from app.services.estudio import almacen, fabrica, grafo

# Relativo a la carpeta del proyecto.
CARPETAS = ("render/clips", "render/audio_clips", "render/sonido_clips", "render/voz_escenas")
ARCHIVOS = ("render/combinado.mp4", "render/audio_clips.wav", "render/voz_escenas.wav", "render/voz_y_clips.wav",
            "render/sonido_clips.wav", "render/combinado_largo.mp4", "render/combinado_capas.mp4",
            "render/voz_larga.wav", "render/audio_capas.wav", "render/sfx_largo.wav", "render/sonido_clips_largo.wav",
            "render/voz_retocada.wav", "render/voz_mejorada.wav",
            "render/final.tmp.mp4")


class ErrorLimpieza(Exception):
    pass


def _tam(ruta):
    if os.path.isfile(ruta):
        return os.path.getsize(ruta)
    total = 0
    for raiz, _dirs, archivos in os.walk(ruta):
        for n in archivos:
            try:
                total += os.path.getsize(os.path.join(raiz, n))
            except OSError:
                pass
    return total


def _objetivos(pid):
    base = almacen.dir_proyecto(pid)
    rutas = [os.path.join(base, c) for c in CARPETAS + ARCHIVOS]
    clips = os.path.join(base, "render")
    if os.path.isdir(clips):  # restos de un montaje cortado a medias
        rutas += [os.path.join(clips, n) for n in os.listdir(clips) if n.endswith(".tmp.mp4")]
    return [r for r in dict.fromkeys(rutas) if os.path.exists(r)]


def espacio(pid):
    """{"total": bytes del proyecto, "liberable": bytes que se pueden borrar}."""
    return {"total": _tam(almacen.dir_proyecto(pid)), "liberable": sum(_tam(r) for r in _objetivos(pid))}


def liberar(pid):
    """Borra lo regenerable de un proyecto. Devuelve los bytes liberados."""
    if grafo.trabajo(pid)[0]:
        raise ErrorLimpieza("el proyecto tiene un trabajo en marcha: espera a que termine")
    liberado = 0
    with almacen.candado(pid):
        for ruta in _objetivos(pid):
            tam = _tam(ruta)
            try:
                if os.path.isdir(ruta):
                    shutil.rmtree(ruta)
                else:
                    os.remove(ruta)
                liberado += tam
            except OSError:
                pass  # en uso (Windows): se queda para la proxima
    return liberado


def resumen():
    """Espacio de todos los proyectos."""
    filas = []
    for pid in sorted(os.listdir(almacen.dir_proyectos())):
        if almacen.PATRON_ID.match(pid) and os.path.isfile(almacen.dir_proyecto(pid, "proyecto.json")):
            filas.append({"id": pid, **espacio(pid)})
    fab = fabrica.resumen_espacio()
    return {"total": sum(f["total"] for f in filas + fab), "liberable": sum(f["liberable"] for f in filas + fab),
            "proyectos": filas, "fabrica": fab}


def liberar_todo():
    """Libera todos los proyectos que no esten trabajando."""
    liberado, hechos, ocupados = 0, 0, []
    todo = resumen()
    for f in todo["proyectos"]:
        if not f["liberable"]:
            continue
        try:
            liberado += liberar(f["id"])
            hechos += 1
        except ErrorLimpieza:
            ocupados.append(f["id"])
    for f in todo["fabrica"]:
        if not f["liberable"]:
            continue
        try:
            liberado += fabrica.liberar(f["id"])
            hechos += 1
        except RuntimeError:
            ocupados.append(f["id"])
    return {"liberado": liberado, "proyectos": hechos, "ocupados": ocupados}
