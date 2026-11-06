"""
Configuracion del Estudio desde la UI (pagina /configuracion).

- Claude: estado de la sesion del CLI (`claude auth status`), iniciar sesion
  (`claude auth login`, abre el navegador de esta maquina) y cerrarla.
- Flow: activar/desactivar, abrir el Chrome para iniciar sesion y cerrarlo.
- Opciones: solo las claves de AJUSTABLES, con su tipo y valores validos.

Los cambios se escriben en config.toml linea a linea (se conservan los comentarios)
y se aplican en memoria al momento: no hace falta reiniciar el backend.
"""
import json
import os
import re
import subprocess
import threading
import time

import toml
from loguru import logger

from app.config import config
from app.services import claude_cli
from app.services.estudio import flow_gen

SIN_VENTANA = claude_cli.SIN_VENTANA

# clave -> (tipo, valores validos o (min, max))
AJUSTABLES = {
    "claude_cli_model": ("opcion", claude_cli.MODELOS),
    "claude_cli_effort": ("opcion", claude_cli.ESFUERZOS),
    "claude_cli_timeout": ("entero", (0, claude_cli.TIEMPO_MAXIMO_S)),
    "estudio_flow_habilitado": ("bool", None),
    "estudio_flow_modelo": ("opcion", flow_gen.MODELOS),
    "estudio_flow_pasadas_extra": ("entero", (0, 5)),
    "estudio_carpetas_permitidas": ("lista", None),
}
POR_DEFECTO = {
    "claude_cli_model": "sonnet", "claude_cli_effort": "low", "claude_cli_timeout": 0,
    "estudio_flow_habilitado": False, "estudio_flow_modelo": "2", "estudio_flow_pasadas_extra": 2,
    "estudio_carpetas_permitidas": [],
}

_login = {"proceso": None, "salida": [], "url": None, "inicio": 0.0}
_candado = threading.Lock()


class AjusteInvalido(ValueError):
    pass


# ------------------------------------------------------------------ opciones

def opciones():
    return {k: config.app.get(k, POR_DEFECTO[k]) for k in AJUSTABLES}


def _validar(clave, valor):
    if clave not in AJUSTABLES:
        raise AjusteInvalido(f"'{clave}' no se puede cambiar desde aqui")
    tipo, regla = AJUSTABLES[clave]
    if tipo == "bool":
        if not isinstance(valor, bool):
            raise AjusteInvalido(f"{clave}: tiene que ser si/no")
        return valor
    if tipo == "opcion":
        valor = str(valor)
        if valor not in regla:
            raise AjusteInvalido(f"{clave}: valores validos {', '.join(regla)}")
        return valor
    if tipo == "entero":
        try:
            valor = int(valor)
        except (TypeError, ValueError):
            raise AjusteInvalido(f"{clave}: tiene que ser un numero")
        if not regla[0] <= valor <= regla[1]:
            raise AjusteInvalido(f"{clave}: entre {regla[0]} y {regla[1]}")
        return valor
    if not isinstance(valor, list):
        raise AjusteInvalido(f"{clave}: tiene que ser una lista")
    return [str(x).strip() for x in valor if str(x).strip()]


def _escribir_toml(cambios):
    """Cambia solo las lineas de esas claves en [app]; si faltan, las pone al inicio de [app]."""
    ruta = config.config_file
    with open(ruta, encoding="utf-8") as f:
        lineas = f.read().splitlines()
    seccion, inicio_app, hechas = None, None, set()
    for i, linea in enumerate(lineas):
        m = re.match(r"^\s*\[([^\]]+)\]\s*$", linea)
        if m:
            seccion = m.group(1).strip()
            if seccion == "app" and inicio_app is None:
                inicio_app = i
            continue
        if seccion != "app":
            continue
        m = re.match(r"^(\s*)([A-Za-z0-9_]+)\s*=", linea)
        if m and m.group(2) in cambios:
            clave = m.group(2)
            comentario = ""
            c = re.search(r"\s+#[^\"'\]]*$", linea)
            if c:
                comentario = "  " + c.group(0).strip()
            lineas[i] = m.group(1) + toml.dumps({clave: cambios[clave]}).strip() + comentario
            hechas.add(clave)
    faltan = [toml.dumps({k: v}).strip() for k, v in cambios.items() if k not in hechas]
    if faltan:
        if inicio_app is None:
            lineas = ["[app]", *faltan, ""] + lineas
        else:
            lineas[inicio_app + 1:inicio_app + 1] = faltan
    texto = "\n".join(lineas) + "\n"
    toml.loads(texto)  # no dejar un config.toml roto
    tmp = ruta + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(texto)
    os.replace(tmp, ruta)


def guardar(cambios: dict):
    limpios = {k: _validar(k, v) for k, v in (cambios or {}).items()}
    if not limpios:
        return opciones()
    if limpios.get("estudio_flow_habilitado") is False and flow_gen.corriendo():
        raise AjusteInvalido("Flow esta generando: detén la generacion antes de desactivarlo")
    _escribir_toml(limpios)
    config.app.update(limpios)
    logger.info(f"configuracion cambiada desde el Estudio: {sorted(limpios)}")
    return opciones()


# ------------------------------------------------------------------ Claude

def _claude(*args, timeout=20):
    r = subprocess.run([claude_cli.localizar(), *args], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=timeout,
                       env=claude_cli._entorno(), **SIN_VENTANA)
    return r.returncode, (r.stdout or "").strip(), (r.stderr or "").strip()


def _login_vivo():
    p = _login["proceso"]
    return p is not None and p.poll() is None


def claude_estado():
    salida = {"instalado": False, "version": None, "sesion": False, "email": None,
              "plan": None, "metodo": None, "iniciando": False, "url_login": None, "motivo": None}
    try:
        claude_cli.localizar()
    except RuntimeError as e:
        salida["motivo"] = str(e)
        return salida
    salida["instalado"] = True
    try:
        _, version, _ = _claude("--version", timeout=15)
        salida["version"] = version.split()[0] if version else None
        _, texto, err = _claude("auth", "status", "--json")
        datos = json.loads(texto) if texto.startswith("{") else {}
        salida.update({
            "sesion": bool(datos.get("loggedIn")), "email": datos.get("email"),
            "plan": datos.get("subscriptionType"), "metodo": datos.get("authMethod"),
        })
        if not datos and err:
            salida["motivo"] = err[-300:]
    except Exception as e:  # noqa: BLE001
        salida["motivo"] = str(e)
    with _candado:
        if _login_vivo():
            salida["iniciando"] = True
            salida["url_login"] = _login["url"]
    return salida


def _leer_login(proceso):
    for linea in proceso.stdout:
        linea = linea.rstrip()
        with _candado:
            _login["salida"] = (_login["salida"] + [linea])[-40:]
            if not _login["url"]:
                m = re.search(r"https://\S+", linea)
                if m:
                    _login["url"] = m.group(0)


def claude_conectar():
    """Lanza `claude auth login` (abre el navegador de ESTA maquina). Se sigue con claude_estado()."""
    with _candado:
        if _login_vivo():
            return {"ok": True, "iniciando": True, "url_login": _login["url"]}
        proceso = subprocess.Popen(
            [claude_cli.localizar(), "auth", "login", "--claudeai"], stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8",
            errors="replace", env=claude_cli._entorno(), **SIN_VENTANA)
        _login.update({"proceso": proceso, "salida": [], "url": None, "inicio": time.time()})
    threading.Thread(target=_leer_login, args=(proceso,), daemon=True).start()
    # Esperar un poco a que salga el enlace (por si el navegador no se abre solo).
    for _ in range(16):
        time.sleep(0.25)
        with _candado:
            if _login["url"] or proceso.poll() is not None:
                break
    with _candado:
        return {"ok": True, "iniciando": proceso.poll() is None, "url_login": _login["url"],
                "salida": _login["salida"][-5:]}


def claude_cancelar_login():
    with _candado:
        p = _login["proceso"]
        if p is not None and p.poll() is None:
            claude_cli._matar_arbol(p)
    return {"ok": True}


def claude_desconectar():
    claude_cancelar_login()
    codigo, texto, err = _claude("auth", "logout")
    if codigo != 0:
        raise RuntimeError((err or texto or "no se pudo cerrar la sesion de Claude")[-300:])
    return {"ok": True}


# ------------------------------------------------------------------ Flow

def flow_estado(comprobar=True):
    salida = {"habilitado": flow_gen.habilitado(), "corriendo": False, "chrome": None,
              "sesion": None, "motivo": None}
    if not salida["habilitado"]:
        return salida
    salida["corriendo"] = flow_gen.corriendo()
    if comprobar:
        try:
            d = flow_gen.sesion()
            salida.update({"chrome": d.get("chrome"), "sesion": d.get("sesion"), "motivo": d.get("motivo")})
        except Exception as e:  # noqa: BLE001
            salida["motivo"] = str(e)
    return salida


def flow_conectar():
    if not flow_gen.habilitado():
        guardar({"estudio_flow_habilitado": True})
    return flow_gen.conectar()


def flow_desconectar():
    return flow_gen.cerrar()
