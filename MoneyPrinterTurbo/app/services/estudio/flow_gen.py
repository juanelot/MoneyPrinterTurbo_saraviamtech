"""
Imagenes de las escenas generadas en Google Flow (Nano Banana, gratis), SOLO en la
maquina local (config `estudio_flow_habilitado`). Automatiza el paso manual del modo
escenas: en vez de bajar script.json, usar la extension y subir images/, se lanza
tools/flow/lote.js, que maneja el Chrome dedicado y deja cada imagen directamente en
recursos/images/scene_NNNN.<ext>.

El ARCHIVO manda (como en la extension): una escena con imagen en recursos/images
esta hecha; sin archivo, esta pendiente. flow/estado.json solo guarda lo que no se
ve en los archivos (fallos, intentos, motivo, como acabo la ultima corrida), asi
que reiniciar el backend o apagar la maquina no pierde nada.

Una sola generacion a la vez en toda la maquina: Flow solo admite una accion.
"""
import json
import os
import shutil
import subprocess
import threading
import time

from loguru import logger

from app.config import config
from app.services.estudio import almacen, medios, recursos
from app.utils import utils

SIN_VENTANA = {"creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)} if os.name == "nt" else {}
CODIGOS = {0: "fin", 2: "detenido", 3: "sin_sesion", 4: "limite"}
MODELOS = ("pro", "2", "lite")

_actual = {}            # {"pid", "proceso", "hilo"} de la corrida en marcha
_candado = threading.Lock()


class NoHabilitado(RuntimeError):
    pass


def habilitado():
    return bool(config.app.get("estudio_flow_habilitado", False))


def _dir_flow():
    d = (config.app.get("estudio_flow_dir", "") or "").strip()
    return os.path.abspath(d or os.path.join(utils.root_dir(), "..", "tools", "flow"))


def _node():
    ruta = shutil.which("node")
    if not ruta:
        raise RuntimeError("no se encontro Node.js (hace falta Node 18+ para generar en Flow)")
    return ruta


def _exigir():
    if not habilitado():
        raise NoHabilitado("Flow no esta habilitado en esta maquina (estudio_flow_habilitado)")
    if not os.path.isfile(os.path.join(_dir_flow(), "node_modules", "playwright-core", "package.json")):
        raise RuntimeError(f"falta instalar el generador: ejecuta `npm install` en {_dir_flow()}")


def _cli(*args, timeout=60):
    _exigir()
    r = subprocess.run([_node(), os.path.join(_dir_flow(), "cli.js"), *args], cwd=_dir_flow(),
                       capture_output=True, text=True, encoding="utf-8", errors="replace",
                       timeout=timeout, **SIN_VENTANA)
    lineas = [x for x in (r.stdout or "").splitlines() if x.strip().startswith("{")]
    if not lineas:
        raise RuntimeError((r.stderr or r.stdout or "sin respuesta del generador de Flow").strip()[-300:])
    return json.loads(lineas[-1])


def sesion():
    """{"chrome", "sesion", "ocupado"}: sesion None = Chrome cerrado (no se sabe)."""
    return _cli("sesion")


def conectar():
    """Abre el Chrome de Flow (perfil dedicado) para iniciar sesion una vez."""
    return _cli("chrome")


def cerrar():
    """Cierra el Chrome de Flow (no borra la sesion de Google: queda en el perfil)."""
    if corriendo():
        raise RuntimeError("Flow esta generando: detén la generacion antes de desconectar")
    return _cli("cerrar")


# ------------------------------------------------------------------ estado

def _ruta_estado(pid):
    return almacen.dir_proyecto(pid, "flow", "estado.json")


def _leer(pid):
    return almacen.leer_json(_ruta_estado(pid), {}) or {}


def _imagenes(pid):
    """{escena: archivo} de las que ya tienen imagen en recursos/ (en images/ o
    suelta: asignacion._por_escenas acepta las dos), como la extension."""
    carpeta = almacen.dir_proyecto(pid, "recursos")
    hechas = {}
    for base, _dirs, nombres in os.walk(carpeta):
        for n in nombres:
            ruta = os.path.join(base, n)
            if n.endswith(".part") or medios.tipo_de(ruta) != "imagen":
                continue
            rel = os.path.relpath(ruta, carpeta).replace("\\", "/")
            k = recursos.numero_escena(rel)
            if k is not None and (k not in hechas or recursos.subcarpeta_de(rel) == "images"):
                hechas[k] = rel
    return hechas


def corriendo(pid=None):
    with _candado:
        vivo = bool(_actual) and _actual["proceso"].poll() is None
        return vivo and (pid is None or _actual["pid"] == pid)


def estado(pid, escenas):
    """Progreso por escena. `escenas` = las del proyecto (con ediciones aplicadas)."""
    datos = _leer(pid)
    hechas = _imagenes(pid)
    en_marcha = corriendo(pid)
    por_escena = datos.get("escenas") or {}
    filas = []
    for e in escenas:
        n = e["scene_number"]
        info = por_escena.get(str(n)) or {}
        if not (e.get("image_prompt") or "").strip():
            est = "sin_prompt"
        elif n in hechas:
            est = "lista"
        elif en_marcha and info.get("estado") in ("generando", "intento"):
            est = "en_curso"
        elif info.get("estado") == "error":
            est = "error"
        else:
            est = "pendiente"
        filas.append({"escena": n, "estado": est, "archivo": hechas.get(n),
                      "intento": info.get("intento"), "motivo": info.get("motivo") or ""})
    cuenta = {k: sum(1 for f in filas if f["estado"] == k) for k in ("lista", "pendiente", "error", "en_curso", "sin_prompt")}
    return {"habilitado": True, "corriendo": en_marcha, "otro_proyecto": corriendo() and not en_marcha,
            "deteniendo": en_marcha and os.path.exists(_ruta_detener(pid)),
            "resultado": None if en_marcha else datos.get("resultado"), "motivo": datos.get("motivo") or "",
            "pasada": datos.get("pasada"), "inicio": datos.get("inicio"), "fin": datos.get("fin"),
            "cuenta": cuenta, "escenas": filas, "log": (datos.get("log") or [])[-30:]}


def _ruta_detener(pid):
    return almacen.dir_proyecto(pid, "flow", ".detener")


# ------------------------------------------------------------------ corrida

def iniciar(pid, escenas, aspecto, reintentar_fallidas=True):
    """Lanza el lote en segundo plano. Solo las escenas sin imagen; las que fallaron
    en una corrida anterior entran salvo reintentar_fallidas=False."""
    _exigir()
    previo = _leer(pid)
    hechas = _imagenes(pid)
    excluir = set()
    if not reintentar_fallidas:
        excluir = {int(k) for k, v in (previo.get("escenas") or {}).items() if v.get("estado") == "error"}
    elegidas = [e for e in escenas if (e.get("image_prompt") or "").strip()
                and e["scene_number"] not in hechas and e["scene_number"] not in excluir]
    if not elegidas:
        raise ValueError("no hay escenas pendientes con prompt de imagen")

    modelo = str(config.app.get("estudio_flow_modelo", "2") or "2")
    if modelo not in MODELOS:
        modelo = "2"
    carpeta = almacen.dir_proyecto(pid, "flow", crear=True)
    script = os.path.join(carpeta, "script.json")
    almacen.escribir_json(script, {"scenes": [{"scene_number": e["scene_number"], "image_prompt": e["image_prompt"],
                                               "video_prompt": e.get("video_prompt", ""),
                                               "narration": e.get("narration", "")} for e in elegidas]})
    detener = _ruta_detener(pid)
    if os.path.exists(detener):
        os.remove(detener)
    salida = almacen.dir_proyecto(pid, "recursos", "images", crear=True)
    orden = [_node(), os.path.join(_dir_flow(), "lote.js"), "--script", script, "--out", salida,
             "--aspect", aspecto if aspecto in ("16:9", "9:16", "1:1", "4:3", "3:4") else "16:9",
             "--model", modelo, "--pasadas-extra", str(int(config.app.get("estudio_flow_pasadas_extra", 2) or 0)),
             "--detener", detener]

    with _candado:
        if _actual and _actual["proceso"].poll() is None:
            otro = _actual["pid"]
            raise RuntimeError("ya se esta generando en Flow" + ("" if otro == pid else " para otro proyecto"))
        # Se conservan los fallos previos (motivo) hasta que la escena se vuelva a intentar.
        datos = {"escenas": {k: v for k, v in (previo.get("escenas") or {}).items() if v.get("estado") == "error"},
                 "inicio": time.time(), "fin": None, "pasada": 1, "resultado": None, "motivo": "",
                 "log": (previo.get("log") or [])[-100:]}
        _anotar(datos, f"inicio: {len(elegidas)} escenas ({len(hechas)} ya tenian imagen)")
        almacen.escribir_json(_ruta_estado(pid), datos)
        proceso = subprocess.Popen(orden, cwd=_dir_flow(), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   text=True, encoding="utf-8", errors="replace", **SIN_VENTANA)
        hilo = threading.Thread(target=_seguir, args=(pid, proceso, datos), daemon=True, name=f"flow-{pid}")
        _actual.clear()
        _actual.update({"pid": pid, "proceso": proceso, "hilo": hilo})
        hilo.start()
    return {"lanzadas": len(elegidas)}


def _anotar(datos, linea):
    datos.setdefault("log", []).append(f"{time.strftime('%H:%M:%S')} {linea}")
    datos["log"] = datos["log"][-200:]


def _seguir(pid, proceso, datos):
    """Lee las lineas JSON del lote y las vuelca en flow/estado.json."""
    escenas = datos["escenas"]
    errores_stderr = []
    hilo_err = threading.Thread(target=lambda: errores_stderr.extend(proceso.stderr), daemon=True)
    hilo_err.start()
    try:
        for linea in proceso.stdout:
            linea = linea.strip()
            if not linea.startswith("{"):
                continue
            try:
                ev = json.loads(linea)
            except json.JSONDecodeError:
                continue
            if "escena" in ev and "estado" in ev:
                n = str(ev["escena"])
                previo = escenas.get(n) or {}
                escenas[n] = {"estado": ev["estado"], "intento": ev.get("intento", previo.get("intento")),
                              "motivo": ev.get("motivo", previo.get("motivo", "") if ev["estado"] == "error" else "")}
                if ev["estado"] == "ok":
                    escenas.pop(n, None)
                    _anotar(datos, f"escena {n} lista ({ev.get('segundos')} s)")
                elif ev["estado"] == "intento":
                    _anotar(datos, f"escena {n}: intento {ev.get('intento')} fallido: {ev.get('motivo', '')[:120]}")
                elif ev["estado"] == "error":
                    _anotar(datos, f"escena {n}: sin imagen tras {ev.get('intentos')} intentos")
            elif ev.get("evento") == "pasada":
                datos["pasada"] = ev.get("n")
                _anotar(datos, f"repaso {ev.get('n')}: {ev.get('pendientes')} escenas fallidas")
            elif ev.get("evento") in ("sin_sesion", "limite", "error"):
                datos["motivo"] = ev.get("motivo", "")
                _anotar(datos, f"{ev['evento']}: {datos['motivo'][:200]}")
            elif ev.get("evento") == "fin":
                _anotar(datos, f"fin: {ev.get('ok')} listas, {ev.get('error')} sin imagen"
                        + (" (detenido)" if ev.get("detenido") else ""))
            almacen.escribir_json(_ruta_estado(pid), datos)
        codigo = proceso.wait()
    except Exception as e:  # noqa: BLE001
        logger.exception(f"flow {pid}: fallo leyendo el lote")
        codigo, datos["motivo"] = 1, str(e)
    hilo_err.join(timeout=2)
    # Las escenas que quedaron "generando" al cortar vuelven a pendientes.
    for n in [n for n, v in escenas.items() if v.get("estado") in ("generando", "intento")]:
        escenas.pop(n)
    datos["resultado"] = CODIGOS.get(codigo, "error")
    if datos["resultado"] == "error" and not datos.get("motivo"):
        datos["motivo"] = "".join(errores_stderr).strip()[-300:] or f"el generador termino con codigo {codigo}"
    datos["fin"] = time.time()
    almacen.escribir_json(_ruta_estado(pid), datos)
    detener = _ruta_detener(pid)
    if os.path.exists(detener):
        os.remove(detener)
    logger.info(f"flow {pid}: {datos['resultado']} {datos.get('motivo', '')[:200]}")


def detener(pid, forzar=False):
    """Pide parar: el lote termina el intento en curso (hasta ~2 min) y sale.
    forzar=True mata el proceso; la escena en curso queda pendiente."""
    with _candado:
        if not _actual or _actual["pid"] != pid or _actual["proceso"].poll() is not None:
            return False
        proceso = _actual["proceso"]
    with open(_ruta_detener(pid), "w") as f:
        f.write(str(time.time()))
    if forzar:
        if os.name == "nt":
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(proceso.pid)], capture_output=True, **SIN_VENTANA)
        else:
            proceso.terminate()
    return True
