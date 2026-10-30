"""
API del Estudio: proyectos por etapas (guion -> voz -> recursos -> asignacion
-> render) con los recursos de la persona y Claude CLI como cerebro.

Todas las rutas cuelgan de /api/v1/estudio.
"""
import hashlib
import json
import os
import re
import shutil
import tempfile
import zipfile

from fastapi import Body, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, PlainTextResponse, Response

from app.controllers.v1.base import new_router
from app.services import claude_cli
from app.services.estudio import (almacen, asistente, creaciones, grafo, maestros, medios, recursos, referencias,
                                  series, voz_clonada)
from app.services.estudio import miniatura as portada_video
from app.services.estudio import (biblioteca, clips, editor, escenas_clip, fabrica, flow_gen, graficos, limpieza, publicar,
                                  retoques, virales, clonar)

router = new_router()
router.tags = ["Estudio"]

NOMBRE_SEGURO = re.compile(r"[^\w.\- ()]+", re.UNICODE)


def _existe(pid):
    try:
        return almacen.cargar(pid)
    except (FileNotFoundError, ValueError):
        raise HTTPException(404, "proyecto no encontrado")


def _vista(pid):
    proyecto, _estado, etapas = grafo.evaluar(pid)
    trabajo, log = grafo.trabajo(pid)
    return {"proyecto": proyecto, "etapas": etapas, "orden": grafo.ETAPAS,
            "deps": grafo.DEPS, "trabajo": trabajo, "log": log}


@router.get("/estudio/proyectos", summary="Listar proyectos del Estudio")
def listar():
    salida = []
    for p in almacen.listar():
        estado = almacen.cargar_estado(p["id"])
        render = (estado["etapas"].get("render") or {}).get("salida") or {}
        mini = portada_video.estado(p["id"])
        salida.append({"id": p["id"], "titulo": p["titulo"], "creado": p["creado"],
                       "actualizado": max(p["actualizado"], mini["version"] or 0), "mp4": render.get("mp4"),
                       "portada": _portada(p["id"]) if render.get("mp4") or mini["final"] else None,
                       "duracion": render.get("duracion"),
                       "trabajando": grafo.trabajo(p["id"])[0] is not None})
    return {"proyectos": salida}


def _portada(pid):
    """La miniatura FINAL subida; si no hay, render/portada.jpg: un fotograma del
    video final (se crea si falta o si es vieja)."""
    final = portada_video.estado(pid)["final"]
    if final:
        return final
    video = almacen.dir_proyecto(pid, "render", "final.mp4")
    portada = almacen.dir_proyecto(pid, "render", "portada.jpg")
    if not os.path.isfile(video):
        return None
    if not os.path.isfile(portada) or os.path.getmtime(portada) < os.path.getmtime(video):
        try:
            medios.correr([medios.ffmpeg(), "-hide_banner", "-loglevel", "error", "-y", "-ss", "1.5",
                           "-i", video, "-frames:v", "1", "-vf", "scale=640:-2", "-q:v", "4", portada], timeout=60)
        except Exception:  # noqa: BLE001
            return None
    return "render/portada.jpg" if os.path.isfile(portada) else None


@router.post("/estudio/proyectos", summary="Crear proyecto")
def crear(body: dict = Body(default={})):
    proyecto = almacen.crear(body.get("titulo", ""))
    params = body.get("params") or {}
    if params:
        proyecto["params"] = {e: v for e, v in params.items() if e in grafo.ETAPAS and isinstance(v, dict)}
        almacen.guardar(proyecto)
    return _vista(proyecto["id"])


@router.get("/estudio/proyectos/{pid}", summary="Proyecto + estado de cada etapa")
def ver(pid: str):
    _existe(pid)
    return _vista(pid)


@router.patch("/estudio/proyectos/{pid}", summary="Cambiar titulo y/o params de etapas")
def editar(pid: str, body: dict = Body(...)):
    """body: {"titulo"?: str, "params"?: {etapa: {clave: valor}}} — se FUSIONA."""
    with almacen.candado(pid):
        proyecto = _existe(pid)
        if "titulo" in body:
            proyecto["titulo"] = str(body["titulo"]).strip()[:200] or proyecto["titulo"]
        for etapa, cambios in (body.get("params") or {}).items():
            if etapa not in grafo.ETAPAS or not isinstance(cambios, dict):
                raise HTTPException(400, f"etapa desconocida: {etapa}")
            actual = proyecto["params"].setdefault(etapa, {})
            for k, v in cambios.items():
                if v is None:
                    actual.pop(k, None)
                else:
                    actual[k] = v
        almacen.guardar(proyecto)
    return _vista(pid)


@router.get("/estudio/espacio", summary="Espacio que ocupan los proyectos y cuanto se puede liberar")
def espacio():
    return limpieza.resumen()


@router.post("/estudio/liberar", summary="Liberar espacio en todos los proyectos (cache y archivos intermedios)")
def liberar_todo():
    return limpieza.liberar_todo()


@router.post("/estudio/proyectos/{pid}/liberar", summary="Liberar espacio del proyecto (cache y archivos intermedios)")
def liberar(pid: str):
    _existe(pid)
    try:
        return {"liberado": limpieza.liberar(pid), **limpieza.espacio(pid)}
    except limpieza.ErrorLimpieza as e:
        raise HTTPException(409, str(e))


@router.delete("/estudio/proyectos/{pid}", summary="Borrar proyecto")
def borrar(pid: str):
    _existe(pid)
    grafo.cancelar(pid)
    shutil.rmtree(almacen.dir_proyecto(pid), ignore_errors=True)
    return {"ok": True}


@router.post("/estudio/proyectos/{pid}/duplicar", summary="Duplicar proyecto (params + recursos subidos)")
def duplicar(pid: str, body: dict = Body(default={})):
    """Copia los ajustes de todas las etapas y los archivos subidos. No copia lo
    generado: el duplicado empieza sin guion, voz ni video (se regeneran)."""
    origen = _existe(pid)
    nuevo = almacen.crear(body.get("titulo") or f"Copia de {origen['titulo']}")
    params = {e: dict(v) for e, v in (origen.get("params") or {}).items()}
    if not body.get("con_guion"):
        params.get("guion", {}).pop("texto_manual", None)
    params.get("asignacion", {}).pop("fijados", None)
    nuevo["params"] = params
    almacen.guardar(nuevo)
    src = almacen.dir_proyecto(pid, "recursos")
    dst = almacen.dir_proyecto(nuevo["id"], "recursos", crear=True)
    if os.path.isdir(src):
        # Con subcarpetas: images/ y videos/ del modo escenas.
        shutil.copytree(src, dst, dirs_exist_ok=True,
                        ignore=lambda d, ns: [n for n in ns if os.path.isfile(os.path.join(d, n)) and not medios.tipo_de(n)])
    return _vista(nuevo["id"])


@router.post("/estudio/proyectos/{pid}/escenas-por-clip", summary="Repartir el guion entre los clips subidos (por su nombre)")
def escenas_por_clip(pid: str, body: dict = Body(default={})):
    """body: {"texto"?: guion}. Sin texto usa el guion ya hecho (o el material).
    Solo calcula: devuelve las escenas fijas para que la interfaz las guarde."""
    proyecto = _existe(pid)
    texto = (body.get("texto") or "").strip()
    if not texto:
        salida = (almacen.cargar_estado(pid)["etapas"].get("guion") or {}).get("salida") or {}
        texto = salida.get("texto") or (proyecto["params"].get("guion") or {}).get("material") or ""
    try:
        return escenas_clip.calcular(pid, texto)
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.post("/estudio/proyectos/{pid}/ejecutar", summary="Ejecutar hasta una etapa")
def ejecutar(pid: str, body: dict = Body(default={})):
    """body: {"hasta": "render", "forzar": ["asignacion"]} — solo corre lo obsoleto."""
    _existe(pid)
    try:
        grafo.lanzar(pid, body.get("hasta", "render"), body.get("forzar") or [])
    except RuntimeError as e:
        raise HTTPException(409, str(e))
    except ValueError as e:
        raise HTTPException(400, str(e))
    return _vista(pid)


@router.post("/estudio/proyectos/{pid}/cancelar", summary="Cancelar el trabajo en curso")
def cancelar(pid: str):
    _existe(pid)
    return {"cancelado": grafo.cancelar(pid)}


# ------------------------------------------------------------------ recursos

@router.get("/estudio/proyectos/{pid}/recursos", summary="Archivos subidos al proyecto")
def listar_subidos(pid: str):
    _existe(pid)
    carpeta = almacen.dir_proyecto(pid, "recursos", crear=True)
    archivos = []
    for base, _dirs, nombres in os.walk(carpeta):
        for n in nombres:
            ruta = os.path.join(base, n)
            if medios.tipo_de(ruta) and not n.endswith(".part"):
                rel = os.path.relpath(ruta, carpeta).replace("\\", "/")
                archivos.append({"nombre": rel, "tipo": medios.tipo_de(ruta), "tam": os.path.getsize(ruta),
                                 "carpeta": recursos.subcarpeta_de(rel), "escena": recursos.numero_escena(rel)})
    archivos.sort(key=lambda a: [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", a["nombre"])])
    return {"archivos": archivos}


def _guardar_subida(origen, carpeta, nombre, sub):
    nombre = NOMBRE_SEGURO.sub("_", os.path.basename(nombre or "")).strip() or "archivo"
    if not medios.tipo_de(nombre):
        return None
    destino_dir = os.path.join(carpeta, sub) if sub else carpeta
    os.makedirs(destino_dir, exist_ok=True)
    destino = almacen.dentro_de(carpeta, os.path.join(sub, nombre) if sub else nombre)
    with open(destino + ".part", "wb") as f:
        shutil.copyfileobj(origen, f, 1 << 20)
    os.replace(destino + ".part", destino)
    return f"{sub}/{nombre}" if sub else nombre


@router.post("/estudio/proyectos/{pid}/recursos", summary="Subir imagenes, videos o un ZIP")
def subir(pid: str, archivos: list[UploadFile] = File(...),
          sub: str = Query("", description="'' | images | videos (formato de la extension)")):
    """Un ZIP se descomprime: lo que este dentro de images/ o videos/ va a esas
    subcarpetas (carpeta de la extension "AI Content Generator"); el resto, suelto."""
    _existe(pid)
    if sub not in ("", "images", "videos"):
        raise HTTPException(400, "sub debe ser '', images o videos")
    carpeta = almacen.dir_proyecto(pid, "recursos", crear=True)
    guardados, rechazados = [], []
    for a in archivos:
        if (a.filename or "").lower().endswith(".zip"):
            try:
                with zipfile.ZipFile(a.file) as z:
                    for info in z.infolist():
                        if info.is_dir() or "__MACOSX" in info.filename:
                            continue
                        sub_zip = recursos.subcarpeta_de(info.filename) or sub
                        with z.open(info) as origen:
                            hecho = _guardar_subida(origen, carpeta, info.filename, sub_zip)
                        (guardados if hecho else rechazados).append(hecho or info.filename)
            except zipfile.BadZipFile:
                rechazados.append(a.filename)
            continue
        hecho = _guardar_subida(a.file, carpeta, a.filename, sub)
        (guardados if hecho else rechazados).append(hecho or a.filename)
    rechazados = [r for r in rechazados if not r.lower().endswith(("script.json", ".ds_store", "thumbs.db"))]
    return {"guardados": guardados, "rechazados": rechazados}


@router.delete("/estudio/proyectos/{pid}/recursos/{nombre:path}", summary="Quitar un archivo subido")
def quitar(pid: str, nombre: str):
    _existe(pid)
    try:
        ruta = almacen.dentro_de(almacen.dir_proyecto(pid, "recursos"), nombre)
    except ValueError:
        raise HTTPException(400, "nombre no valido")
    if os.path.isfile(ruta):
        os.remove(ruta)
    return {"ok": True}


AUDIO_PROPIO = (".wav", ".mp3", ".m4a", ".aac", ".ogg", ".opus", ".flac", ".webm")


@router.get("/estudio/proyectos/{pid}/audios", summary="Audios del proyecto (para las pistas del editor)")
def audios(pid: str):
    _existe(pid)
    carpeta = almacen.dir_proyecto(pid, "audios")
    lista = []
    if os.path.isdir(carpeta):
        for n in sorted(os.listdir(carpeta)):
            ruta = os.path.join(carpeta, n)
            if os.path.isfile(ruta) and n.lower().endswith(AUDIO_PROPIO):
                lista.append({"archivo": f"audios/{n}", "nombre": n, "duracion": medios.sondear(ruta)["duracion"]})
    return {"audios": lista}


@router.post("/estudio/proyectos/{pid}/audios", summary="Subir audios (efectos, sonidos) para el editor")
def subir_audios(pid: str, archivos: list[UploadFile] = File(...)):
    _existe(pid)
    carpeta = almacen.dir_proyecto(pid, "audios", crear=True)
    guardados, rechazados = [], []
    for a in archivos:
        nombre = NOMBRE_SEGURO.sub("_", os.path.basename(a.filename or "")).strip()
        if not nombre.lower().endswith(AUDIO_PROPIO):
            rechazados.append(a.filename)
            continue
        destino = almacen.dentro_de(carpeta, nombre)
        with open(destino + ".part", "wb") as f:
            shutil.copyfileobj(a.file, f, 1 << 20)
        os.replace(destino + ".part", destino)
        guardados.append(f"audios/{nombre}")
    return {"guardados": guardados, "rechazados": rechazados}


@router.delete("/estudio/proyectos/{pid}/audios/{nombre}", summary="Quitar un audio del proyecto")
def quitar_audio(pid: str, nombre: str):
    _existe(pid)
    try:
        ruta = almacen.dentro_de(almacen.dir_proyecto(pid, "audios"), nombre)
    except ValueError:
        raise HTTPException(400, "nombre no valido")
    if os.path.isfile(ruta):
        os.remove(ruta)
    return {"ok": True}


@router.post("/estudio/proyectos/{pid}/voz-propia", summary="Subir una narracion ya grabada como voz")
def voz_propia(pid: str, audio: UploadFile = File(...)):
    """Guarda el audio en voz_propia/<hash><ext> y pone voz = "propia:<archivo>":
    al ejecutar la etapa Voz, Whisper saca los tiempos de cada palabra."""
    _existe(pid)
    ext = os.path.splitext(audio.filename or "")[1].lower()
    if ext not in AUDIO_PROPIO:
        raise HTTPException(400, f"formato no admitido ({ext or 'sin extension'}): usa {', '.join(AUDIO_PROPIO)}")
    carpeta = almacen.dir_proyecto(pid, "voz_propia", crear=True)
    tmp = os.path.join(carpeta, "subida.part")
    h = hashlib.sha256()
    with open(tmp, "wb") as f:
        while trozo := audio.file.read(1 << 20):
            h.update(trozo)
            f.write(trozo)
    nombre = h.hexdigest()[:16] + ext
    info = medios.sondear(tmp)
    if not info.get("duracion"):
        os.remove(tmp)
        raise HTTPException(400, "no parece un audio valido")
    for viejo in os.listdir(carpeta):  # solo se guarda el ultimo audio subido
        if viejo not in ("subida.part", nombre):
            os.remove(os.path.join(carpeta, viejo))
    os.replace(tmp, os.path.join(carpeta, nombre))
    with almacen.candado(pid):
        proyecto = _existe(pid)
        voz = proyecto["params"].setdefault("voz", {})
        voz["voz"] = f"propia:{nombre}"
        voz["propia_nombre"] = os.path.basename(audio.filename or nombre)[:120]
        almacen.guardar(proyecto)
    return _vista(pid)


# ------------------------------------------------------------------ escenas

def _escenas(pid):
    """Escenas de la ultima ejecucion + las ediciones a mano ACTUALES (aunque la
    etapa no se haya vuelto a ejecutar: lo que se descarga es lo que se ve)."""
    _, _, etapas = grafo.evaluar(_existe(pid)["id"])
    salida = etapas["escenas"]["salida"]
    if not salida:
        raise HTTPException(404, "todavia no hay escenas: ejecuta la etapa Escenas")
    ediciones = etapas["escenas"]["params"].get("ediciones") or {}
    escenas = []
    for e in salida["escenas"]:
        e = dict(e)
        ed = ediciones.get(str(e["scene_number"])) or {}
        for campo in ("image_prompt", "video_prompt"):
            if isinstance(ed.get(campo), str) and ed[campo].strip():
                e[campo] = " ".join(ed[campo].split())
        escenas.append(e)
    return escenas


@router.get("/estudio/proyectos/{pid}/script.json", summary="script.json para la extension (Flow/Vibes)")
def script_json(pid: str):
    datos = {"scenes": [{"scene_number": e["scene_number"], "image_prompt": e["image_prompt"],
                         "video_prompt": e["video_prompt"], "narration": e["narration"]} for e in _escenas(pid)]}
    return Response(json.dumps(datos, ensure_ascii=False, indent=2), media_type="application/json",
                    headers={"Content-Disposition": 'attachment; filename="script.json"'})


@router.get("/estudio/proyectos/{pid}/prompts.txt", summary="Prompts en texto, escena por escena")
def prompts_txt(pid: str):
    bloques = []
    for e in _escenas(pid):
        b = [f"ESCENA {e['scene_number']}  ({e['duracion']:.1f}s)", f"Narracion: {e['narration']}"]
        if e.get("image_prompt"):
            b.append(f"IMAGEN: {e['image_prompt']}")
        if e.get("video_prompt"):
            b.append(f"VIDEO: {e['video_prompt']}")
        bloques.append("\n".join(b))
    return PlainTextResponse("\n\n".join(bloques), headers={"Content-Disposition": 'attachment; filename="prompts.txt"'})


# ------------------------------------------------------------------ Google Flow (solo local)

def _flow():
    if not flow_gen.habilitado():
        raise HTTPException(404, "Flow no esta habilitado en esta maquina")


@router.get("/estudio/flow", summary="¿Se puede generar en Google Flow aqui? (+ sesion)")
def flow_info(comprobar: bool = Query(False, description="abrir Flow para ver si hay sesion")):
    if not flow_gen.habilitado():
        return {"habilitado": False}
    salida = {"habilitado": True, "corriendo": flow_gen.corriendo()}
    if comprobar:
        try:
            salida.update(flow_gen.sesion())
        except Exception as e:  # noqa: BLE001
            salida.update({"sesion": None, "motivo": str(e)})
    return salida


@router.post("/estudio/flow/conectar", summary="Abrir el Chrome de Flow para iniciar sesion")
def flow_conectar():
    _flow()
    try:
        return flow_gen.conectar()
    except Exception as e:  # noqa: BLE001
        raise HTTPException(500, str(e))


@router.get("/estudio/proyectos/{pid}/flow", summary="Progreso de la generacion en Flow, por escena")
def flow_estado(pid: str):
    _flow()
    return flow_gen.estado(pid, _escenas(pid))


@router.post("/estudio/proyectos/{pid}/flow/generar", summary="Generar en Flow las imagenes que faltan")
def flow_generar(pid: str, body: dict = Body(default={})):
    """body: {"reintentar_fallidas": true} — solo escenas sin imagen en recursos/images."""
    _flow()
    escenas = _escenas(pid)
    aspecto = grafo.params_efectivos(_existe(pid), "render").get("aspecto") or "16:9"
    try:
        flow_gen.iniciar(pid, escenas, aspecto, bool(body.get("reintentar_fallidas", True)))
    except ValueError as e:
        raise HTTPException(400, str(e))
    except RuntimeError as e:
        raise HTTPException(409, str(e))
    return flow_gen.estado(pid, escenas)


@router.post("/estudio/proyectos/{pid}/flow/detener", summary="Detener la generacion en Flow")
def flow_detener(pid: str, body: dict = Body(default={})):
    _flow()
    flow_gen.detener(pid, bool(body.get("forzar")))
    return flow_gen.estado(pid, _escenas(pid))


# ------------------------------------------------------------------ archivos

@router.get("/estudio/proyectos/{pid}/editor", summary="Palabras y forma de onda de la voz (editor)")
def datos_editor(pid: str):
    return editor.datos(_existe(pid)["id"])


def _retoque(fn, *args):
    try:
        return fn(*args)
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:  # noqa: BLE001 -- Claude o el TTS fallaron: que la persona lo vea
        raise HTTPException(502, str(e)[:500])


@router.post("/estudio/proyectos/{pid}/editor/reescribir", summary="Claude propone otro texto para una parte de la voz")
def reescribir_parte(pid: str, body: dict = Body(...)):
    """body: {"desde", "hasta" (tiempo de la voz), "texto" (lo que dice ahora), "pedido"}."""
    return _retoque(retoques.reescribir, _existe(pid)["id"], body.get("desde"), body.get("hasta"),
                    str(body.get("texto") or ""), str(body.get("pedido") or ""))


# ------------------------------------------------------------------ Clip Studio (video largo -> shorts)

def _clip(fn, *args):
    try:
        return fn(*args)
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))
    except ValueError as e:
        raise HTTPException(400, str(e))
    except RuntimeError as e:
        raise HTTPException(409, str(e))


@router.get("/estudio/clips", summary="Sesiones de Clip Studio")
def clips_listar():
    return {"sesiones": clips.listar()}


@router.post("/estudio/clips", summary="Subir un video largo para sacarle shorts (se transcribe solo)")
def clips_crear(archivo: UploadFile = File(...)):
    return _clip(clips.crear, archivo.filename, archivo.file)


@router.get("/estudio/clips/{cid}", summary="Estado, frases, propuestas y shorts de una sesion")
def clips_ver(cid: str):
    return _clip(clips.ver, cid)


@router.delete("/estudio/clips/{cid}", summary="Borrar una sesion de Clip Studio")
def clips_borrar(cid: str):
    _clip(clips.borrar, cid)
    return {"ok": True}


@router.post("/estudio/clips/{cid}/proponer", summary="Claude propone los mejores momentos")
def clips_proponer(cid: str, body: dict = Body(default={})):
    """body: {"cuantos": 5, "duracion": "corto|medio|largo", "pedido": ""}."""
    _clip(clips.proponer, cid, body.get("cuantos") or 5, body.get("duracion") or "medio", body.get("pedido") or "")
    return clips.ver(cid)


@router.put("/estudio/clips/{cid}/propuestas", summary="Guardar los clips editados a mano")
def clips_propuestas(cid: str, body: dict = Body(...)):
    return {"propuestas": _clip(clips.guardar_propuestas, cid, body.get("propuestas"))}


@router.post("/estudio/clips/{cid}/exportar", summary="Hacer el short vertical de un tramo")
def clips_exportar(cid: str, body: dict = Body(...)):
    return _clip(clips.exportar, cid, body)


@router.get("/estudio/clips/{cid}/original", summary="El video largo")
def clips_original(cid: str):
    return FileResponse(_clip(clips.ruta_original, cid))


@router.get("/estudio/clips/{cid}/shorts/{nombre}", summary="Un short ya hecho")
def clips_short(cid: str, nombre: str, descargar: bool = Query(default=False)):
    ruta = _clip(clips.ruta_export, cid, nombre)
    return FileResponse(ruta, media_type="video/mp4", filename=f"short-{nombre}" if descargar else None)


@router.get("/estudio/fabrica/catalogo", summary="Nichos, estilos y formatos de la Fabrica")
def fabrica_catalogo():
    return fabrica.catalogo()


# (antes que /estudio/fabrica/{fid}: si no, "biblioteca" se tomaria por un id)
@router.get("/estudio/fabrica/moldes", summary="Moldes: opciones guardadas de videos que funcionan")
def fabrica_moldes():
    return {"moldes": fabrica.moldes()}


@router.post("/estudio/fabrica/moldes", summary="Guardar un molde (de las opciones dadas o de un video: desde)")
def fabrica_guardar_molde(body: dict = Body(...)):
    return _clip(fabrica.guardar_molde, body.get("nombre"), body.get("opciones"), body.get("desde"))


@router.delete("/estudio/fabrica/moldes/{mid}", summary="Borrar un molde")
def fabrica_borrar_molde(mid: str):
    return _clip(fabrica.borrar_molde, mid)


@router.get("/estudio/fabrica/ideas", summary="Banco de temas de un nicho")
def fabrica_ideas(nicho: str = "mapas"):
    return {"ideas": fabrica.ideas(nicho)}


@router.post("/estudio/fabrica/ideas", summary="Claude propone temas nuevos para el banco (sin repetir lo hecho)")
def fabrica_sugerir(body: dict = Body(...)):
    return {"ideas": _clip(fabrica.sugerir_temas, body.get("nicho") or "mapas", body.get("serie") or "", int(body.get("cuantos") or 10))}


@router.delete("/estudio/fabrica/ideas", summary="Quitar un tema del banco")
def fabrica_quitar_idea(nicho: str, tema: str):
    return {"ideas": fabrica.quitar_idea(nicho, tema)}


@router.get("/estudio/virales", summary="Ultimo analisis de ideas virales")
def virales_ultimo():
    return {"analisis": virales.ultimo()}


@router.post("/estudio/virales", summary="Analizar cuentas: videos que hacen 3x su mediana (outliers)")
def virales_analizar(body: dict = Body(...)):
    return _clip(virales.analizar, body.get("cuentas") or [])


@router.post("/estudio/virales/detalle", summary="Detalle de un video: gancho de 3 s, likes y comentarios")
def virales_detalle(body: dict = Body(...)):
    return _clip(virales.detalle, str(body.get("url") or ""))


@router.post("/estudio/virales/temas", summary="Convertir videos virales en temas propios del banco de la Fabrica")
def virales_temas(body: dict = Body(...)):
    return {"ideas": _clip(virales.a_temas, body.get("videos") or [], body.get("nicho") or "mapas", body.get("serie") or "")}


@router.get("/estudio/fabrica/parecido", summary="Video ya hecho que se parece a un tema (o null)")
def fabrica_parecido(tema: str, nicho: str = ""):
    return {"parecido": fabrica.parecido(tema, nicho or None)}


@router.get("/estudio/fabrica/estilos", summary="Galeria de estilos de la Fabrica (hace las muestras que falten)")
def fabrica_estilos():
    return fabrica.estilos_galeria()


@router.get("/estudio/fabrica/estilos/{estilo}/muestra", summary="Imagen de muestra de un estilo")
def fabrica_estilo_muestra(estilo: str):
    return FileResponse(_clip(fabrica.ruta_muestra, estilo), media_type="image/jpeg",
                        headers={"Cache-Control": "public, max-age=604800"})


@router.get("/estudio/fabrica/biblioteca", summary="Pegatinas e ilustraciones de la Fabrica (base y propias)")
def fabrica_biblioteca():
    return biblioteca.listar()


@router.get("/estudio/fabrica/biblioteca/{tipo}/{clave}", summary="Imagen de una pegatina o ilustracion")
def fabrica_biblioteca_imagen(tipo: str, clave: str, familia: str = Query("", description="plano, grabado (vacio: madera)")):
    ruta = biblioteca.ruta(tipo, clave, familia or None)
    if not ruta:
        raise HTTPException(404, "ese dibujo no existe")
    return FileResponse(ruta, media_type="image/webp", headers={"Cache-Control": "no-cache"})


@router.post("/estudio/fabrica/biblioteca/crear", summary="Crear un dibujo con Nano Banana (Flow, solo en el PC local)")
def fabrica_biblioteca_crear(body: dict = Body(...)):
    """body: {"tipo": "pegatinas|ilustraciones", "descripcion", "nombre"?, "clase"?: "personaje|objeto",
    "familia"?: "plano|grabado" (sin ella, madera)}. Tarda ~1 min."""
    familia = body.get("familia") if body.get("familia") in biblioteca.FAMILIAS else None
    return _clip(biblioteca.crear, body.get("tipo"), body.get("descripcion"), body.get("nombre") or "",
                 body.get("clase") or "personaje", False, familia)


@router.post("/estudio/fabrica/biblioteca/subir", summary="Subir un dibujo propio a la biblioteca")
async def fabrica_biblioteca_subir(archivo: UploadFile = File(...), tipo: str = Form(...), nombre: str = Form(...),
                                   descripcion: str = Form(default=""), fondo_verde: bool = Form(default=False)):
    datos = await archivo.read()
    if len(datos) > 25 * 1024 * 1024:
        raise HTTPException(400, "la imagen pesa mas de 25 MB")
    return _clip(biblioteca.subir, tipo, datos, nombre, descripcion, fondo_verde)


@router.delete("/estudio/fabrica/biblioteca/{tipo}/{clave}", summary="Borrar un dibujo propio")
def fabrica_biblioteca_borrar(tipo: str, clave: str):
    _clip(biblioteca.borrar, tipo, clave)
    return {"ok": True}


@router.get("/estudio/clones", summary="Videos clonados (recetas)")
def clones_listar():
    return {"clones": clonar.listar()}


@router.post("/estudio/clones", summary="Clonar un video desde un enlace (saca su receta)")
def clones_crear(body: dict = Body(...)):
    return _clip(clonar.crear, str(body.get("url") or ""))


@router.post("/estudio/clones/subir", summary="Clonar un video subido (saca su receta)")
async def clones_subir(video: UploadFile = File(...)):
    datos = await video.read()
    if len(datos) > 300 * 1024 * 1024:
        raise HTTPException(400, "el video pesa mas de 300 MB")
    return _clip(clonar.crear, "", datos, video.filename or "")


@router.get("/estudio/clones/{cid}", summary="Receta, planos y estado de un clon")
def clones_ver(cid: str):
    return _clip(clonar.ver, cid)


@router.delete("/estudio/clones/{cid}", summary="Borrar un clon")
def clones_borrar(cid: str):
    _clip(clonar.borrar, cid)
    return {"ok": True}


@router.get("/estudio/clones/{cid}/foto/{nombre}", summary="Fotograma de un plano del video clonado")
def clones_foto(cid: str, nombre: str):
    return FileResponse(_clip(clonar.ruta_foto, cid, nombre), media_type="image/jpeg")


@router.post("/estudio/fabrica/{fid}/clip/{n}", summary="Subir el clip de video de una escena (hecho aparte con su prompt)")
async def fabrica_subir_clip(fid: str, n: int, video: UploadFile = File(...)):
    datos = await video.read()
    if len(datos) > 300 * 1024 * 1024:
        raise HTTPException(400, "el clip pesa mas de 300 MB")
    return _clip(fabrica.subir_clip, fid, n, datos, video.filename or "")


@router.delete("/estudio/fabrica/{fid}/clip/{n}", summary="Quitar el clip de video de una escena")
def fabrica_borrar_clip(fid: str, n: int):
    return _clip(fabrica.borrar_clip, fid, n)


@router.post("/estudio/fabrica/audio", summary="Subir una narracion grabada (el guion se adapta a ella)")
async def fabrica_audio(audio: UploadFile = File(...)):
    """Devuelve {"voz": "propia:<archivo>", "duracion"}: se pasa esa voz al crear el video."""
    datos = await audio.read()
    if len(datos) > 100 * 1024 * 1024:
        raise HTTPException(400, "el audio pesa mas de 100 MB")
    return _clip(fabrica.subir_audio, datos, audio.filename or "")


@router.get("/estudio/fabrica", summary="Videos de la Fabrica")
def fabrica_listar():
    return {"videos": fabrica.listar()}


@router.post("/estudio/fabrica", summary="Hacer un video entero desde un tema (guion, voz, escenas y montaje)")
def fabrica_crear(body: dict = Body(...)):
    """body: {"tema", "nicho"?, "estilo"?, "formatos"?: ["9:16", "16:9", "1:1"], "voz"?: voz de Microsoft,
    "clon:<id>" o "propia:<archivo>" (de POST /estudio/fabrica/audio; entonces el tema es opcional), "velocidad"?,
    "duracion"?: s, "musica"?: "random" | "" | cancion, "musica_volumen"?, "subtitulos"?: bool, "idioma"?}.
    Trabaja en segundo plano: consulta GET /estudio/fabrica/{id}."""
    return _clip(fabrica.crear, body)


@router.post("/estudio/fabrica/lote", summary="Varios videos de la Fabrica con las mismas opciones (se hacen de uno en uno)")
def fabrica_lote(body: dict = Body(...)):
    """body: {"temas": ["tema", ...] o [{"tema", "estilo"?, "nicho"?...}], "opciones"?: las de POST /estudio/fabrica}."""
    return _clip(fabrica.lote, body.get("temas"), body.get("opciones") or {})


@router.get("/estudio/fabrica/{fid}", summary="Estado, guion y videos de un video de la Fabrica")
def fabrica_ver(fid: str):
    return _clip(fabrica.ver, fid)


@router.delete("/estudio/fabrica/{fid}", summary="Borrar un video de la Fabrica")
def fabrica_borrar(fid: str):
    _clip(fabrica.borrar, fid)
    return {"ok": True}


@router.patch("/estudio/fabrica/{fid}", summary="Renombrar un video de la Fabrica")
def fabrica_renombrar(fid: str, body: dict = Body(...)):
    return _clip(fabrica.renombrar, fid, body.get("titulo"))


@router.post("/estudio/fabrica/{fid}/duplicar", summary="Copiar un video de la Fabrica (guion, voz, escenas y videos)")
def fabrica_duplicar(fid: str):
    return _clip(fabrica.duplicar, fid)


@router.post("/estudio/fabrica/{fid}/liberar", summary="Liberar espacio de un video de la Fabrica (cache de escenas)")
def fabrica_liberar(fid: str):
    return {"liberado": _clip(fabrica.liberar, fid), **_clip(fabrica.espacio, fid)}


@router.post("/estudio/fabrica/{fid}/montar", summary="Seguir un video parado en revision (voz, musica y montaje)")
def fabrica_montar(fid: str, body: dict = Body(default={})):
    return _clip(fabrica.montar, fid, body.get("opciones"))


@router.post("/estudio/fabrica/{fid}/siguiente", summary="Siguiente episodio: un video que sigue la historia de este")
def fabrica_siguiente(fid: str, body: dict = Body(default={})):
    return _clip(fabrica.siguiente_episodio, fid, body.get("idea"))


@router.post("/estudio/fabrica/{fid}/rehacer", summary="Rehacer desde el guion, la voz o el render (con opciones nuevas)")
def fabrica_rehacer(fid: str, body: dict = Body(default={})):
    """body: {"desde": "guion|voz|render", "opciones"?: {estilo, formatos, voz...}}."""
    return _clip(fabrica.rehacer, fid, body.get("desde") or "render", body.get("opciones"))


@router.post("/estudio/fabrica/{fid}/editor", summary="Abrir un video de la Fabrica en el editor del Estudio (crea un proyecto)")
def fabrica_editor(fid: str, body: dict = Body(default={})):
    """body: {"formato"?: "9:16"}. Devuelve {"proyecto": id}; las etapas hasta la asignacion corren solas."""
    return _clip(fabrica.abrir_en_editor, fid, body.get("formato"))


@router.put("/estudio/fabrica/{fid}/guion", summary="Guardar el guion editado y rehacer desde la voz")
def fabrica_guion(fid: str, body: dict = Body(...)):
    return _clip(fabrica.guardar_guion, fid, body.get("guion"))


@router.get("/estudio/fabrica/{fid}/video/{formato}", summary="Un video terminado (formato 9x16, 16x9 o 1x1)")
def fabrica_video(fid: str, formato: str, descargar: bool = Query(default=False)):
    ruta = _clip(fabrica.ruta_video, fid, formato.replace("x", ":"))
    return FileResponse(ruta, media_type="video/mp4", filename=f"fabrica-{fid}-{formato}.mp4" if descargar else None)


@router.get("/estudio/graficos/plantillas", summary="Plantillas de graficos animados (HyperFrames)")
def plantillas_graficos():
    return {"plantillas": graficos.catalogo(), "falta": graficos.disponible()}


@router.post("/estudio/proyectos/{pid}/graficos", summary="Renderizar un grafico animado transparente para el editor")
def crear_grafico(pid: str, body: dict = Body(...)):
    """body: {"plantilla", "valores": {...}, "color"?, "posicion"?, "duracion"?}. Tarda ~30 s (en cache si se repite)."""
    return _retoque(graficos.renderizar, _existe(pid)["id"], str(body.get("plantilla") or ""), body.get("valores") or {},
                    body.get("color"), body.get("posicion"), body.get("duracion"))


@router.get("/estudio/proyectos/{pid}/graficos/ideas", summary="Las ultimas ideas de graficos que propuso Claude")
def ver_ideas_graficos(pid: str):
    return {"ideas": [], **graficos.ideas_guardadas(_existe(pid)["id"])}


@router.post("/estudio/proyectos/{pid}/graficos/ideas", summary="Claude propone graficos animados para todo el video")
def proponer_graficos(pid: str, body: dict = Body(default={})):
    """body: {"cuantos"?: 1-15, "pedido"?: texto}. No renderiza: devuelve las ideas para elegir."""
    return _retoque(graficos.proponer, _existe(pid)["id"], body.get("cuantos") or 6, str(body.get("pedido") or ""))


@router.get("/estudio/proyectos/{pid}/publicar", summary="Lo ya generado para publicar (titulos, capitulos, gancho...)")
def ver_publicar(pid: str):
    return {**publicar.guardado(_existe(pid)["id"]), "idiomas": publicar.IDIOMAS, "plataformas": publicar.PLATAFORMAS}


@router.post("/estudio/proyectos/{pid}/publicar/{accion}", summary="Generar titulos, capitulos, traduccion o analisis del gancho")
def hacer_publicar(pid: str, accion: str, body: dict = Body(default={})):
    """accion: metadatos | capitulos | traducir | gancho. body: {"plataforma"?, "idioma"?}."""
    pid = _existe(pid)["id"]
    plataforma = str(body.get("plataforma") or "youtube")
    acciones = {
        "metadatos": lambda: publicar.metadatos(pid, plataforma),
        "capitulos": lambda: publicar.capitulos(pid),
        "traducir": lambda: publicar.traducir(pid, str(body.get("idioma") or "")),
        "gancho": lambda: publicar.gancho(pid, plataforma),
    }
    if accion not in acciones:
        raise HTTPException(404, "herramienta desconocida")
    return _retoque(acciones[accion])


@router.get("/estudio/proyectos/{pid}/publicar/subtitulos.srt", summary="Descargar los subtitulos del video (o una traduccion)")
def srt_publicar(pid: str, idioma: str = Query(default="")):
    pid = _existe(pid)["id"]
    try:
        texto = publicar.srt_de(pid, idioma)
    except (ValueError, FileNotFoundError) as e:
        raise HTTPException(404, str(e))
    nombre = f"subtitulos{'_' + idioma if idioma else ''}.srt"
    return PlainTextResponse(texto, media_type="application/x-subrip; charset=utf-8",
                             headers={"Content-Disposition": f'attachment; filename="{nombre}"'})


@router.post("/estudio/proyectos/{pid}/editor/grabar", summary="Regrabar una parte de la voz con otro texto")
def grabar_parte(pid: str, body: dict = Body(...)):
    """body: {"desde", "hasta", "texto"}. Devuelve el archivo, su duracion y si cabe en el hueco."""
    return _retoque(retoques.grabar, _existe(pid)["id"], body.get("desde"), body.get("hasta"), body.get("texto"))


@router.get("/estudio/proyectos/{pid}/archivo/{ruta:path}", summary="Servir una salida del proyecto")
def archivo(pid: str, ruta: str):
    _existe(pid)
    try:
        real = almacen.dentro_de(almacen.dir_proyecto(pid), ruta)
    except ValueError:
        raise HTTPException(400, "ruta no valida")
    if not os.path.isfile(real) or real.endswith(".json"):
        raise HTTPException(404, "no existe")
    return FileResponse(real)


@router.get("/estudio/miniatura/{h}", summary="Miniatura de un recurso del catalogo")
def miniatura(h: str):
    if not re.fullmatch(r"[a-f0-9]{16}", h):
        raise HTTPException(400, "id no valido")
    ruta = recursos.ruta_miniatura(h)
    if not os.path.isfile(ruta):
        raise HTTPException(404, "sin miniatura")
    return FileResponse(ruta, headers={"Cache-Control": "public, max-age=86400"})


@router.get("/estudio/proyectos/{pid}/original/{h}", summary="Archivo original de un recurso")
def original(pid: str, h: str):
    _, _, etapas = grafo.evaluar(_existe(pid)["id"])
    for r in ((etapas["recursos"]["salida"] or {}).get("recursos") or []):
        if r["id"] == h and os.path.isfile(r["ruta"]):
            return FileResponse(r["ruta"])
    raise HTTPException(404, "recurso no encontrado")


def _png_ultimo(ruta, nombre):
    with tempfile.TemporaryDirectory() as tmp:
        destino = os.path.join(tmp, "ultimo.png")
        if not medios.ultimo_fotograma(ruta, destino):
            raise HTTPException(422, "no se pudo leer el ultimo fotograma de ese video")
        with open(destino, "rb") as f:
            datos = f.read()
    base = re.sub(r"[^A-Za-z0-9_-]+", "-", os.path.splitext(nombre)[0]).strip("-")[:60] or "clip"
    return Response(datos, media_type="image/png",
                    headers={"Content-Disposition": f'attachment; filename="{base}-ultimo-fotograma.png"'})


@router.get("/estudio/proyectos/{pid}/original/{h}/ultimo-fotograma", summary="Ultimo fotograma de un video subido")
def original_ultimo(pid: str, h: str):
    _, _, etapas = grafo.evaluar(_existe(pid)["id"])
    for r in ((etapas["recursos"]["salida"] or {}).get("recursos") or []):
        if r["id"] == h and os.path.isfile(r["ruta"]) and r["tipo"] == "video":
            return _png_ultimo(r["ruta"], r["nombre"])
    raise HTTPException(404, "video no encontrado")


@router.post("/estudio/herramientas/ultimo-fotograma", summary="Ultimo fotograma de un clip (segmentos encadenados)")
async def herramienta_ultimo(archivo: UploadFile = File(...)):
    ext = os.path.splitext(archivo.filename or "")[1].lower()
    if ext not in medios.EXT_VIDEO:
        raise HTTPException(400, "sube un video (mp4, mov, webm...)")
    with tempfile.TemporaryDirectory() as tmp:
        ruta = os.path.join(tmp, "clip" + ext)
        with open(ruta, "wb") as f:
            while bloque := await archivo.read(1 << 20):
                f.write(bloque)
        return _png_ultimo(ruta, archivo.filename)


@router.get("/estudio/proyectos/{pid}/descargar", summary="Descargar el MP4 final")
def descargar(pid: str):
    proyecto = _existe(pid)
    ruta = almacen.dir_proyecto(pid, "render", "final.mp4")
    if not os.path.isfile(ruta):
        raise HTTPException(404, "todavia no hay video")
    slug = re.sub(r"[^a-z0-9]+", "-", proyecto["titulo"].lower()).strip("-")[:60] or "video"
    return FileResponse(ruta, filename=f"{slug}-{pid[:6]}.mp4", media_type="video/mp4")


# ------------------------------------------------------------------ asistente

@router.post("/estudio/asistente", summary="Preguntar al asistente (Claude CLI)")
def asistente_preguntar(body: dict = Body(...)):
    """body: {"pregunta": str, "charla"?: id, "proyecto"?: id abierto en pantalla}."""
    pid = body.get("proyecto") or None
    if pid and not almacen.PATRON_ID.match(pid):
        pid = None
    try:
        return asistente.preguntar(body.get("charla"), body.get("pregunta", ""), pid)
    except asistente.ErrorAsistente as e:
        raise HTTPException(400, str(e))


@router.get("/estudio/asistente/{cid}", summary="Estado de una charla con el asistente")
def asistente_ver(cid: str):
    try:
        return asistente.ver(cid)
    except asistente.ErrorAsistente as e:
        raise HTTPException(404, str(e))


# ------------------------------------------------------------------ voz clonada

@router.get("/estudio/voces-clonadas", summary="Voces del servidor de clonacion (si hay uno)")
def voces_clonadas():
    if not voz_clonada.url_base():
        return {"activo": False, "voces": [], "error": None}
    try:
        return {"activo": True, "voces": voz_clonada.listar_voces(), "error": None}
    except Exception as e:  # noqa: BLE001 — el servidor externo puede estar apagado
        return {"activo": True, "voces": [], "error": f"no responde el servidor de voz clonada ({type(e).__name__})"}


@router.post("/estudio/voces-clonadas", summary="Crear una voz a partir de 10-15 s de audio")
async def voces_clonadas_crear(audio: UploadFile = File(...), nombre: str = Form(...),
                               transcripcion: str = Form("")):
    datos = await audio.read()
    if len(datos) > 60 * 1024 * 1024:
        raise HTTPException(413, "con 10-15 segundos de voz basta (maximo 60 MB)")
    try:
        return voz_clonada.crear_voz(nombre.strip()[:80] or "Mi voz", datos, audio.filename, transcripcion.strip()[:2000])
    except voz_clonada.NoConfigurado as e:
        raise HTTPException(400, str(e))
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, f"el servidor de voz clonada fallo: {e}")


@router.get("/estudio/voces-clonadas/{vid}/audio", summary="Muestra de referencia de una voz")
def voces_clonadas_audio(vid: str):
    try:
        return Response(voz_clonada.audio_voz(vid), media_type="audio/wav")
    except ValueError:
        raise HTTPException(400, "voz invalida")
    except Exception:  # noqa: BLE001
        raise HTTPException(404, "no se pudo traer la muestra")


# ------------------------------------------------------------------ miniatura

@router.get("/estudio/proyectos/{pid}/miniatura", summary="Conceptos, referencia y miniatura final")
def miniatura_ver(pid: str):
    _existe(pid)
    return portada_video.estado(pid)


@router.post("/estudio/proyectos/{pid}/miniatura/generar", summary="Claude propone conceptos y prompts")
def miniatura_generar(pid: str, body: dict = Body(default={})):
    _existe(pid)
    params = {k: body[k] for k in portada_video.DEFECTOS if k in body}
    try:
        portada_video.generar(pid, params)
    except RuntimeError as e:
        raise HTTPException(409, str(e))
    return portada_video.estado(pid)


@router.post("/estudio/proyectos/{pid}/miniatura/{tipo}", summary="Subir la referencia o la miniatura final")
async def miniatura_subir(pid: str, tipo: str, archivo: UploadFile = File(...)):
    _existe(pid)
    if tipo not in ("referencia", "final"):
        raise HTTPException(404, "tipo desconocido")
    datos = await archivo.read()
    if len(datos) > 25 * 1024 * 1024:
        raise HTTPException(413, "la imagen no puede pasar de 25 MB")
    try:
        portada_video.guardar_archivo(pid, tipo, datos)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return portada_video.estado(pid)


@router.delete("/estudio/proyectos/{pid}/miniatura/{tipo}", summary="Quitar la referencia o la final")
def miniatura_quitar(pid: str, tipo: str):
    _existe(pid)
    if tipo not in ("referencia", "final"):
        raise HTTPException(404, "tipo desconocido")
    portada_video.quitar_archivo(pid, tipo)
    return portada_video.estado(pid)


@router.get("/estudio/proyectos/{pid}/miniatura-descargar", summary="Descargar la miniatura final")
def miniatura_descargar(pid: str):
    proyecto = _existe(pid)
    final = portada_video.estado(pid)["final"]
    if not final:
        raise HTTPException(404, "todavia no hay miniatura final")
    ruta = almacen.dir_proyecto(pid, final)
    slug = re.sub(r"[^a-z0-9]+", "-", proyecto["titulo"].lower()).strip("-")[:60] or "miniatura"
    return FileResponse(ruta, filename=f"{slug}-miniatura{os.path.splitext(ruta)[1]}")


# ------------------------------------------------------------------ prompts maestros

def _maestro(mid):
    if not almacen.PATRON_ID.match(mid or ""):
        raise HTTPException(404, "prompt maestro no encontrado")
    try:
        return maestros.cargar(mid)
    except maestros.ErrorMaestro as e:
        raise HTTPException(404, str(e))


@router.get("/estudio/maestros", summary="Biblioteca de prompts maestros")
def maestros_listar():
    return {"maestros": maestros.listar()}


@router.post("/estudio/maestros", summary="Subir un prompt maestro (.docx/.txt/.md o texto) y desglosarlo")
async def maestros_crear(archivo: UploadFile | None = File(None), texto: str = Form(""), nombre: str = Form(""),
                         modelo: str = Form(""), esfuerzo: str = Form("")):
    try:
        if archivo is not None and archivo.filename:
            datos = await archivo.read()
            if len(datos) > 30 * 1024 * 1024:
                raise HTTPException(413, "el archivo no puede pasar de 30 MB")
            contenido, portada = maestros.extraer(archivo.filename, datos)
            origen = archivo.filename
            nombre = nombre or os.path.splitext(archivo.filename)[0].replace("_", " ").strip()
        else:
            contenido, portada, origen = texto, None, "texto pegado"
        return maestros.crear(nombre, contenido, origen, portada, modelo or None, esfuerzo or None)
    except maestros.ErrorMaestro as e:
        raise HTTPException(400, str(e))


@router.get("/estudio/maestros/exportar", summary="ZIP con los prompts maestros (para llevarlos a otra maquina)")
def maestros_exportar(ids: str = Query("")):
    datos = maestros.exportar([x for x in ids.split(",") if x] or None)
    return Response(datos, media_type="application/zip",
                    headers={"Content-Disposition": 'attachment; filename="prompts_maestros.zip"'})


@router.post("/estudio/maestros/importar", summary="Cargar un ZIP exportado de otra maquina")
async def maestros_importar(archivo: UploadFile = File(...)):
    datos = await archivo.read()
    if len(datos) > 100 * 1024 * 1024:
        raise HTTPException(413, "el ZIP no puede pasar de 100 MB")
    try:
        return {"importados": maestros.importar(datos)}
    except maestros.ErrorMaestro as e:
        raise HTTPException(400, str(e))


@router.post("/estudio/maestros/{mid}/texto", summary="Subir una version nueva del prompt maestro y volver a desglosarlo")
async def maestros_texto(mid: str, archivo: UploadFile | None = File(None), texto: str = Form("")):
    _maestro(mid)
    try:
        if archivo is not None and archivo.filename:
            contenido, _ = maestros.extraer(archivo.filename, await archivo.read())
            return maestros.reemplazar_texto(mid, contenido, archivo.filename)
        return maestros.reemplazar_texto(mid, texto, "texto pegado")
    except maestros.ErrorMaestro as e:
        raise HTTPException(400, str(e))


@router.get("/estudio/maestros/{mid}", summary="Ficha de un prompt maestro")
def maestros_ver(mid: str):
    return _maestro(mid)


@router.get("/estudio/maestros/{mid}/original", summary="Texto original del prompt maestro")
def maestros_original(mid: str):
    _maestro(mid)
    return PlainTextResponse(maestros.texto_original(mid))


@router.get("/estudio/maestros/{mid}/portada", summary="Portada del prompt maestro")
def maestros_portada(mid: str):
    _maestro(mid)
    ruta = os.path.join(almacen.raiz("maestros"), mid, "portada.jpg")
    if not os.path.isfile(ruta):
        raise HTTPException(404, "sin portada")
    return FileResponse(ruta, media_type="image/jpeg")


@router.post("/estudio/maestros/{mid}/portada", summary="Poner una portada propia")
async def maestros_poner_portada(mid: str, archivo: UploadFile = File(...)):
    _maestro(mid)
    datos = await archivo.read()
    if len(datos) > 20 * 1024 * 1024:
        raise HTTPException(413, "la imagen no puede pasar de 20 MB")
    try:
        return maestros.poner_portada(mid, datos)
    except maestros.ErrorMaestro as e:
        raise HTTPException(400, str(e))


@router.delete("/estudio/maestros/{mid}/portada", summary="Quitar la portada")
def maestros_quitar_portada(mid: str):
    _maestro(mid)
    return maestros.quitar_portada(mid)


@router.patch("/estudio/maestros/{mid}", summary="Renombrar, notas o corregir la ficha")
def maestros_editar(mid: str, body: dict = Body(...)):
    _maestro(mid)
    return maestros.editar(mid, body)


@router.post("/estudio/maestros/{mid}/analizar", summary="Volver a desglosar con Claude")
def maestros_analizar(mid: str, body: dict = Body(default={})):
    _maestro(mid)
    try:
        maestros.analizar(mid, body.get("modelo") or None, body.get("esfuerzo") or None)
    except maestros.ErrorMaestro as e:
        raise HTTPException(409, str(e))
    return maestros.cargar(mid)


@router.delete("/estudio/maestros/{mid}", summary="Borrar un prompt maestro")
def maestros_borrar(mid: str):
    _maestro(mid)
    maestros.borrar(mid)
    return {"ok": True}


# ------------------------------------------------------------------ crear contenido con un prompt maestro

def _creacion(mid, cid):
    _maestro(mid)
    if not almacen.PATRON_ID.match(cid or ""):
        raise HTTPException(404, "creacion no encontrada")
    try:
        return creaciones.cargar(mid, cid)
    except creaciones.ErrorCreacion as e:
        raise HTTPException(404, str(e))


@router.get("/estudio/maestros/{mid}/creaciones", summary="Creaciones hechas con un prompt maestro")
def creaciones_listar(mid: str):
    _maestro(mid)
    return {"creaciones": creaciones.listar(mid)}


# ------------------------------------------------------------------ series (episodios con la misma biblia)

def _serie(mid, sid):
    _maestro(mid)
    if not almacen.PATRON_ID.match(sid or ""):
        raise HTTPException(404, "serie no encontrada")
    try:
        return series.cargar(mid, sid)
    except series.ErrorSerie as e:
        raise HTTPException(404, str(e))


@router.get("/estudio/maestros/{mid}/series", summary="Series hechas con un prompt maestro")
def series_listar(mid: str):
    _maestro(mid)
    return {"series": series.listar(mid)}


@router.post("/estudio/maestros/{mid}/series", summary="Convertir una creacion en el episodio 1 de una serie")
def series_crear(mid: str, body: dict = Body(...)):
    _creacion(mid, str(body.get("desde") or ""))
    try:
        sid = creaciones.convertir_en_serie(mid, body["desde"])
    except creaciones.ErrorCreacion as e:
        raise HTTPException(409, str(e))
    return series.cargar(mid, sid)


@router.get("/estudio/maestros/{mid}/series/{sid}", summary="Biblia, referencias y episodios de una serie")
def series_ver(mid: str, sid: str):
    return _serie(mid, sid)


@router.patch("/estudio/maestros/{mid}/series/{sid}", summary="Editar titulo, biblia o referencias de la serie")
def series_cambiar(mid: str, sid: str, body: dict = Body(...)):
    _serie(mid, sid)
    return series.cambiar(mid, sid, body)


@router.post("/estudio/maestros/{mid}/series/{sid}/biblia", summary="Volver a escribir la biblia con Claude")
def series_biblia(mid: str, sid: str):
    _serie(mid, sid)
    try:
        return series.rehacer_biblia(mid, sid)
    except series.ErrorSerie as e:
        raise HTTPException(409, str(e))


@router.post("/estudio/maestros/{mid}/series/{sid}/episodios", summary="Empezar el siguiente episodio")
def series_episodio(mid: str, sid: str, body: dict = Body(default={})):
    _serie(mid, sid)
    try:
        return creaciones.crear(mid, body.get("tema", ""), body.get("modo", "guiado"), body.get("modelo", "sonnet"),
                                serie=sid)
    except creaciones.ErrorCreacion as e:
        raise HTTPException(409, str(e))


@router.delete("/estudio/maestros/{mid}/series/{sid}", summary="Borrar la serie (los episodios quedan sueltos)")
def series_borrar(mid: str, sid: str):
    _serie(mid, sid)
    try:
        series.borrar(mid, sid)
    except series.ErrorSerie as e:
        raise HTTPException(409, str(e))
    return {"ok": True}


@router.get("/estudio/maestros/{mid}/series/{sid}/referencias/{k}", summary="Imagen de una referencia de la serie")
def series_ver_referencia(mid: str, sid: str, k: str):
    _serie(mid, sid)
    ruta = referencias.ruta_imagen(series.dir_ref(mid, sid), referencias.clave(k))
    if not ruta:
        raise HTTPException(404, "sin imagen")
    return FileResponse(ruta, filename=os.path.basename(ruta))


@router.post("/estudio/maestros/{mid}/series/{sid}/referencias/{k}", summary="Subir la imagen de una referencia de la serie")
async def series_subir_referencia(mid: str, sid: str, k: str, archivo: UploadFile = File(...)):
    s = _serie(mid, sid)
    ref = next((r for r in s["referencias"] if r["clave"] == referencias.clave(k)), None)
    if not ref:
        raise HTTPException(404, "referencia no encontrada")
    datos = await archivo.read()
    if len(datos) > 30 * 1024 * 1024:
        raise HTTPException(413, "la imagen no puede pasar de 30 MB")
    try:
        referencias.guardar_imagen(series.dir_ref(mid, sid), ref["nombre"], datos)
    except referencias.ErrorReferencia as e:
        raise HTTPException(400, str(e))
    return series.cargar(mid, sid)


@router.post("/estudio/maestros/{mid}/creaciones", summary="Empezar a crear contenido con el prompt maestro")
def creaciones_crear(mid: str, body: dict = Body(default={})):
    _maestro(mid)
    try:
        return creaciones.crear(mid, body.get("tema", ""), body.get("modo", "guiado"), body.get("modelo", "sonnet"))
    except creaciones.ErrorCreacion as e:
        raise HTTPException(400, str(e))


@router.get("/estudio/maestros/{mid}/creaciones/{cid}", summary="Estado de una creacion")
def creaciones_ver(mid: str, cid: str):
    return _creacion(mid, cid)


@router.post("/estudio/maestros/{mid}/creaciones/{cid}/mensaje", summary="Responder en la creacion")
def creaciones_mensaje(mid: str, cid: str, body: dict = Body(...)):
    _creacion(mid, cid)
    try:
        return creaciones.enviar(mid, cid, body.get("texto", ""))
    except creaciones.ErrorCreacion as e:
        raise HTTPException(409, str(e))


@router.post("/estudio/maestros/{mid}/creaciones/{cid}/reintentar", summary="Repetir el turno que fallo")
def creaciones_reintentar(mid: str, cid: str):
    _creacion(mid, cid)
    try:
        return creaciones.reintentar(mid, cid)
    except creaciones.ErrorCreacion as e:
        raise HTTPException(409, str(e))


@router.post("/estudio/maestros/{mid}/creaciones/{cid}/entregables", summary="Ordenar lo producido en entregables")
def creaciones_entregables(mid: str, cid: str):
    _creacion(mid, cid)
    try:
        return creaciones.preparar_entregables(mid, cid)
    except creaciones.ErrorCreacion as e:
        raise HTTPException(409, str(e))


@router.put("/estudio/maestros/{mid}/creaciones/{cid}/escenas", summary="Editar a mano las escenas (unir, quitar, duracion)")
def creaciones_escenas(mid: str, cid: str, body: dict = Body(...)):
    _creacion(mid, cid)
    try:
        return creaciones.editar_escenas(mid, cid, body.get("escenas"))
    except creaciones.ErrorCreacion as e:
        raise HTTPException(400, str(e))


@router.put("/estudio/maestros/{mid}/creaciones/{cid}/referencias", summary="Quitar referencias o corregir su prompt")
def creaciones_referencias(mid: str, cid: str, body: dict = Body(...)):
    _creacion(mid, cid)
    try:
        return creaciones.editar_referencias(mid, cid, body.get("referencias"))
    except creaciones.ErrorCreacion as e:
        raise HTTPException(400, str(e))


@router.post("/estudio/maestros/{mid}/creaciones/{cid}/referencias/proponer", summary="Claude propone hojas de referencia")
def creaciones_proponer_referencias(mid: str, cid: str):
    _creacion(mid, cid)
    try:
        return creaciones.proponer_referencias(mid, cid)
    except creaciones.ErrorCreacion as e:
        raise HTTPException(400, str(e))
    except claude_cli.LimiteAgotado as e:
        raise HTTPException(429, str(e))


@router.get("/estudio/maestros/{mid}/creaciones/{cid}/referencias/{k}", summary="Imagen de una hoja de referencia")
def creaciones_ver_referencia(mid: str, cid: str, k: str):
    _creacion(mid, cid)
    ruta = creaciones.ruta_referencia(mid, cid, k)
    if not ruta:
        raise HTTPException(404, "sin imagen")
    return FileResponse(ruta, filename=os.path.basename(ruta))


@router.post("/estudio/maestros/{mid}/creaciones/{cid}/referencias/{k}", summary="Subir la imagen de una referencia")
async def creaciones_subir_referencia(mid: str, cid: str, k: str, archivo: UploadFile = File(...)):
    _creacion(mid, cid)
    datos = await archivo.read()
    if len(datos) > 30 * 1024 * 1024:
        raise HTTPException(413, "la imagen no puede pasar de 30 MB")
    try:
        return creaciones.subir_referencia(mid, cid, referencias.clave(k), datos)
    except creaciones.ErrorCreacion as e:
        raise HTTPException(400, str(e))


@router.delete("/estudio/maestros/{mid}/creaciones/{cid}/referencias/{k}", summary="Quitar la imagen de una referencia")
def creaciones_quitar_referencia(mid: str, cid: str, k: str):
    _creacion(mid, cid)
    return creaciones.quitar_referencia(mid, cid, k)


@router.post("/estudio/maestros/{mid}/creaciones/{cid}/video", summary="Crear un proyecto del Estudio con la creacion")
def creaciones_video(mid: str, cid: str, body: dict = Body(...)):
    _creacion(mid, cid)
    try:
        proyecto = creaciones.crear_video(mid, cid, body.get("narracion", ""), body.get("aspecto") or None,
                                          body.get("voz") or None, body.get("titulo") or None)
    except creaciones.ErrorCreacion as e:
        raise HTTPException(400, str(e))
    except claude_cli.LimiteAgotado as e:
        raise HTTPException(429, str(e))
    return {"proyecto": proyecto}


@router.patch("/estudio/maestros/{mid}/creaciones/{cid}", summary="Renombrar o cambiar de modo (guiado/auto)")
def creaciones_cambiar(mid: str, cid: str, body: dict = Body(...)):
    _creacion(mid, cid)
    try:
        return creaciones.cambiar(mid, cid, body)
    except creaciones.ErrorCreacion as e:
        raise HTTPException(409, str(e))


@router.delete("/estudio/maestros/{mid}/creaciones/{cid}", summary="Borrar una creacion")
def creaciones_borrar(mid: str, cid: str):
    _creacion(mid, cid)
    try:
        creaciones.borrar(mid, cid)
    except creaciones.ErrorCreacion as e:
        raise HTTPException(409, str(e))
    return {"ok": True}
