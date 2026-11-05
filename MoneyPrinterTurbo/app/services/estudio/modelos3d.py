"""Modelos 3D para las escenas de Blender: el catalogo de Poly Haven (CC0, con medidas reales) y las formas que el kit
dibuja con codigo (persona, edificio, planetas...). Los de Poly Haven se bajan la primera vez que se usan (glTF con
texturas de 1K) y quedan en storage/estudio/modelos3d/<id>/.
"""
import json
import os
import re
import threading

import requests
from loguru import logger

from app.services.estudio import almacen, graficos

API = "https://api.polyhaven.com"
DIR = almacen.raiz("modelos3d")
CATALOGO = os.path.join(graficos.DIR_MOTION, "blender", "datos", "polyhaven.json")
_candado = threading.Lock()

# Formas del kit (motion/blender/tamanos.py) y su alto tipico en metros (Claude pone el real en cada video)
FORMAS = {
    "persona": 1.7, "hormiga": 0.005, "coche": 1.5, "casa": 8, "edificio": 100, "rascacielos": 400, "torre": 300,
    "arbol": 15, "montana": 3000, "nube": 1000, "esfera": 1, "cubo": 1, "estrella": 1,
    "luna": 3_474_800, "tierra": 12_742_000, "marte": 6_779_000, "jupiter": 139_820_000, "sol": 1_392_700_000,
}


def catalogo():
    """{id: {"alto": m, "ancho": m, "tags": [...], "cats": [...]}} de Poly Haven (se baja una vez y se guarda)."""
    if os.path.isfile(CATALOGO):
        with open(CATALOGO, encoding="utf-8") as f:
            return json.load(f)
    with _candado:
        if os.path.isfile(CATALOGO):
            return catalogo()
        lista = requests.get(f"{API}/assets?t=models", timeout=60).json()
        datos = {}
        for k, v in lista.items():
            dim = v.get("dimensions") or [0, 0, 0]
            if not dim or not dim[2]:
                continue
            datos[k] = {"alto": round(dim[2] / 1000, 3), "ancho": round(max(dim[0], dim[1]) / 1000, 3),
                        "tags": (v.get("tags") or [])[:6], "cats": [c for c in v.get("categories") or [] if not c.startswith("collection")]}
        os.makedirs(os.path.dirname(CATALOGO), exist_ok=True)
        with open(CATALOGO, "w", encoding="utf-8") as f:
            json.dump(datos, f, ensure_ascii=False, indent=0)
        logger.info(f"modelos3d: catalogo de Poly Haven con {len(datos)} modelos")
        return datos


def para_claude():
    """Texto corto con lo que hay: formas del kit y modelos de Poly Haven (id, alto en m, 2 etiquetas)."""
    cat = catalogo()
    formas = ", ".join(FORMAS)
    modelos = ", ".join(f"{k} {v['alto']:g}" for k, v in sorted(cat.items()))
    return f"Formas (se dibujan a cualquier tamano): {formas}.\nModelos reales de Poly Haven (id y alto en m): {modelos}"


def valido(modelo):
    return modelo in FORMAS or modelo in catalogo()


def ruta(modelo):
    """Ruta del .gltf de un modelo de Poly Haven (lo baja si falta) o None si es una forma del kit."""
    if modelo in FORMAS or modelo not in catalogo():
        return None
    carpeta = os.path.join(DIR, re.sub(r"[^\w-]", "_", modelo))
    gltf = os.path.join(carpeta, f"{modelo}.gltf")
    if os.path.isfile(gltf):
        return gltf
    with _candado:
        if os.path.isfile(gltf):
            return gltf
        archivos = requests.get(f"{API}/files/{modelo}", timeout=60).json()["gltf"]["1k"]["gltf"]
        os.makedirs(carpeta, exist_ok=True)
        for nombre, x in {**archivos.get("include", {}), f"{modelo}.gltf": {"url": archivos["url"]}}.items():
            destino = os.path.join(carpeta, *nombre.split("/"))
            os.makedirs(os.path.dirname(destino), exist_ok=True)
            r = requests.get(x["url"], timeout=120)
            r.raise_for_status()
            with open(destino + ".part", "wb") as f:
                f.write(r.content)
            os.replace(destino + ".part", destino)
        logger.info(f"modelos3d: {modelo} bajado de Poly Haven")
    return gltf
