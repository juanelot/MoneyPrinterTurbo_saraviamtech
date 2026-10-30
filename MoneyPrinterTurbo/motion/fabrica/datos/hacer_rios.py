"""
Prepara los rios de la Fabrica desde Natural Earth 1:50m (dominio publico):

    python hacer_rios.py

  rios.js    window.RIOS = {clave: {n, l: [lineas [lon, lat]]}}   (lo dibuja el motor)
  rios.json  {clave: {n, bbox, nombres}}                        (lo usa Python: Claude elige por clave)

La clave es el nombre en minusculas sin acentos ("nilo", "amazonas", "danubio"). Un rio son todos los tramos
con el mismo nombre (Natural Earth lo parte en trozos; los afluentes con nombre propio son otro rio).
"""
import json
import os
import re
import unicodedata
import urllib.request

URL = "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/ne_50m_rivers_lake_centerlines.geojson"
AQUI = os.path.dirname(os.path.abspath(__file__))


def clave(nombre):
    s = unicodedata.normalize("NFD", nombre.lower())
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]+", "_", s).strip("_")


def main():
    with urllib.request.urlopen(URL, timeout=120) as r:
        datos = json.load(r)
    rios = {}
    for f in datos["features"]:
        p, g = f["properties"], f["geometry"]
        nombre_en = (p.get("name_en") or p.get("name") or "").strip()
        if not nombre_en or not g or (p.get("featurecla") or "").startswith("Lake"):
            continue
        nombre = (p.get("name_es") or nombre_en).strip()
        lineas = g["coordinates"] if g["type"] == "MultiLineString" else [g["coordinates"]]
        k = clave(nombre)
        r_ = rios.setdefault(k, {"n": nombre, "l": [], "nombres": set()})
        r_["nombres"].update({nombre, nombre_en})
        for linea in lineas:
            puntos = [[round(x, 2), round(y, 2)] for x, y in linea]
            limpio = [puntos[0]] + [b for a, b in zip(puntos, puntos[1:]) if b != a]
            if len(limpio) > 1:
                r_["l"].append(limpio)
    motor, meta = {}, {}
    for k, r_ in rios.items():
        xs = [x for l in r_["l"] for x, _ in l]
        ys = [y for l in r_["l"] for _, y in l]
        if not xs:
            continue
        motor[k] = {"n": r_["n"], "l": r_["l"]}
        meta[k] = {"n": r_["n"], "bbox": [min(xs), min(ys), max(xs), max(ys)], "nombres": sorted(r_["nombres"])}
    with open(os.path.join(AQUI, "rios.js"), "w", encoding="utf-8") as f:
        f.write("window.RIOS=" + json.dumps(motor, ensure_ascii=False, separators=(",", ":")) + ";")
    with open(os.path.join(AQUI, "rios.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, separators=(",", ":"))
    print(f"{len(motor)} rios")


if __name__ == "__main__":
    main()
