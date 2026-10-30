"""
Prepara los paises de la Fabrica desde Natural Earth 1:50m (dominio publico):

    python hacer_paises.py

  paises.js    window.PAISES = {ISO3: {n, r: [anillos [lon, lat]], c: [lon, lat]}}  (lo dibuja el motor)
  paises.json  {ISO3: {n, c, bbox: [oeste, sur, este, norte], a2}}                (lo usa Python para encuadrar;
               a2 = codigo de 2 letras, el nombre de su bandera en country-flag-icons)

El bbox deja fuera los trozos lejanos (Guayana Francesa, Alaska, Hawai, Isla de Pascua...): se parte
del anillo mas cercano al punto del nombre y se le van sumando los que quedan a menos de SALTO grados
de alguno ya sumado (asi entran los archipielagos enteros, como Indonesia o Japon).
"""
import json
import os
import urllib.request

URL = "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/ne_50m_admin_0_countries.geojson"
AQUI = os.path.dirname(os.path.abspath(__file__))
SALTO = 6
# Encuadres fijos donde la cadena de islas no basta (EE. UU.: los 48 estados contiguos, sin Alaska).
CAJAS_FIJAS = {"USA": [-124.8, 24.5, -66.9, 49.4]}


def _caja(anillo):
    xs, ys = [x for x, _ in anillo], [y for _, y in anillo]
    return min(xs), min(ys), max(xs), max(ys)


def _encadenados(anillos, cx, cy):
    cajas = [_caja(a) for a in anillos]
    hueco = lambda c, d: max(c[0] - d[2], d[0] - c[2], 0) < SALTO and max(c[1] - d[3], d[1] - c[3], 0) < SALTO
    dentro = lambda c: max(c[0] - cx, cx - c[2], 0) + max(c[1] - cy, cy - c[3], 0)
    dentro_de = {min(range(len(cajas)), key=lambda i: dentro(cajas[i]))}
    nuevos = True
    while nuevos:
        nuevos = {i for i in range(len(cajas)) if i not in dentro_de and any(hueco(cajas[i], cajas[j]) for j in dentro_de)}
        dentro_de |= nuevos
    return [anillos[i] for i in sorted(dentro_de)]


def main():
    with urllib.request.urlopen(URL, timeout=120) as r:
        datos = json.load(r)
    motor, meta = {}, {}
    for f in datos["features"]:
        p, g = f["properties"], f["geometry"]
        iso = p.get("ADM0_A3")
        if not iso or not g:
            continue
        polis = g["coordinates"] if g["type"] == "MultiPolygon" else [g["coordinates"]]
        anillos = []
        for poli in polis:
            puntos = [[round(x, 2), round(y, 2)] for x, y in poli[0]]
            limpio = [puntos[0]] + [b for a, b in zip(puntos, puntos[1:]) if b != a]
            if len(limpio) > 3:
                anillos.append(limpio)
        if not anillos:
            continue
        cx, cy = float(p.get("LABEL_X") or anillos[0][0][0]), float(p.get("LABEL_Y") or anillos[0][0][1])
        cerca = _encadenados(anillos, cx, cy)
        xs = [x for a in cerca for x, _ in a]
        ys = [y for a in cerca for _, y in a]
        nombre = p.get("NAME_ES") or p.get("NAME")
        motor[iso] = {"n": nombre, "r": anillos, "c": [round(cx, 2), round(cy, 2)]}
        meta[iso] = {"n": nombre, "c": [round(cx, 2), round(cy, 2)], "bbox": CAJAS_FIJAS.get(iso) or [min(xs), min(ys), max(xs), max(ys)]}
        # ISO_A2 vale -99 en algunos (Francia, Noruega...): ISO_A2_EH si lo trae
        a2 = next((c for c in (p.get("ISO_A2"), p.get("ISO_A2_EH")) if c and c != "-99"), None)
        if a2:
            meta[iso]["a2"] = a2
    with open(os.path.join(AQUI, "paises.js"), "w", encoding="utf-8") as f:
        f.write("window.PAISES=" + json.dumps(motor, ensure_ascii=False, separators=(",", ":")) + ";")
    with open(os.path.join(AQUI, "paises.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, separators=(",", ":"))
    print(f"{len(motor)} paises")


if __name__ == "__main__":
    main()
