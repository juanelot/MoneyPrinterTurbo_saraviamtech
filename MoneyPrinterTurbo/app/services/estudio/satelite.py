"""
Fondo de satelite de los mapas de la Fabrica: Sentinel-2 cloudless 2016 de EOX (CC BY 4.0, se puede usar en
videos comerciales con el credito; las versiones de 2018 en adelante son solo no comerciales).

El motor no descarga nada mientras renderiza: aqui se baja (con cache) lo que la camara va a ver y se arma
por escena un pequeno juego de mosaicos ya recortados, del mas lejano al mas cercano:
  - el mundo entero a poca resolucion (que nunca se vea un hueco),
  - la zona de toda la escena a la resolucion de su toma mas lejana (los vuelos y alejamientos),
  - cada toma cercana a su resolucion.
mapa.js pinta cada mosaico en su sitio (coordenadas Mercator 0..1) y encima los paises.

La geometria (zona libre, encuadre, tamano del mundo) es la misma que nucleo.js y mapa.js: si cambia alli,
hay que cambiarla aqui.
"""
import hashlib
import io
import math
import os
import urllib.request
from concurrent.futures import ThreadPoolExecutor

from PIL import Image

from app.services.estudio import almacen

TESELA = "https://tiles.maps.eox.at/wmts/1.0.0/s2cloudless_3857/default/g/{z}/{y}/{x}.jpg"
CREDITO = ("Imagenes de satelite: Sentinel-2 cloudless - https://s2maps.eu by EOX IT Services GmbH "
           "(Contains modified Copernicus Sentinel data 2016), CC BY 4.0.")
Z_MAX = 13          # mas alla EOX ya no tiene detalle (10 m por pixel)
Z_MUNDO = 3
LADO_MAX = 4096     # lado maximo de un mosaico (memoria del navegador)
UA = "SaraviaMtech-Studio/1.0 (fabrica de videos)"


# ------------------------------------------------------------------ geometria (igual que nucleo.js / mapa.js)

def mx(lon):
    return (lon + 180) / 360


def my(lat):
    s = math.sin(max(-85.0, min(85.0, lat)) * math.pi / 180)
    return 0.5 - math.log((1 + s) / (1 - s)) / (4 * math.pi)


def zona(w, h, tipo="normal"):
    vertical, cuadrado = h / w > 1.3, w / h < 1.3 and not h / w > 1.3
    if vertical:
        z = {"x": w * 0.07, "y": h * 0.13, "w": w * 0.8, "h": h * 0.54}
    elif cuadrado:
        z = {"x": w * 0.07, "y": h * 0.08, "w": w * 0.86, "h": h * 0.62}
    else:
        z = {"x": w * 0.06, "y": h * 0.08, "w": w * 0.88, "h": h * 0.64}
    if tipo == "rotulo":
        z = {**z, "y": z["y"] + z["h"] * 0.24, "h": z["h"] * 0.76}
    elif tipo == "portada":
        z = {**z, "y": z["y"] + z["h"] * 0.46, "h": z["h"] * 0.54} if vertical else \
            {"x": z["x"] + z["w"] * 0.5, "w": z["w"] * 0.5, "y": z["y"] + z["h"] * 0.12, "h": z["h"] * 0.88}
    return z


def encuadre(toma, w, h, zl):
    s = min(w, h) * 0.9
    if toma.get("bbox"):
        o, sur, e, n = toma["bbox"]
        bx0, bx1, by0, by1 = mx(o), mx(e), my(n), my(sur)
        aire = toma.get("aire", 0.78)
        z = math.log2(min(zl["w"] * aire / (max(bx1 - bx0, 1e-4) * s), zl["h"] * aire / (max(by1 - by0, 1e-4) * s)))
        z = max(0.2, min(toma.get("zmax", 7.5), z))
        k = s * 2 ** z
        return {"x": (bx0 + bx1) / 2 - (zl["x"] + zl["w"] / 2 - w / 2) / k,
                "y": (by0 + by1) / 2 - (zl["y"] + zl["h"] / 2 - h / 2) / k, "z": z}
    return {"x": mx(toma["lon"]), "y": my(toma["lat"]), "z": toma.get("z", 3)}


def _vista(m, w, h, margen=1.2):
    """Rectangulo Mercator [x0, y0, x1, y1] que se ve con la camara m (con margen)."""
    k = min(w, h) * 0.9 * 2 ** m["z"]
    hw, hh = w / 2 / k * margen, h / 2 / k * margen
    return [m["x"] - hw, m["y"] - hh, m["x"] + hw, m["y"] + hh]


def _z_tesela(z_camara, w, h):
    """Nivel de teselas que da 1 pixel de imagen por pixel de pantalla a ese zoom de camara."""
    return max(1, min(Z_MAX, math.ceil(z_camara + math.log2(min(w, h) * 0.9 / 256))))


# ------------------------------------------------------------------ teselas y mosaicos

def _tesela(z, x, y):
    ruta = os.path.join(almacen.dir_catalogo("teselas"), str(z), f"{x}_{y}.jpg")
    if os.path.isfile(ruta):
        return ruta
    os.makedirs(os.path.dirname(ruta), exist_ok=True)
    req = urllib.request.Request(TESELA.format(z=z, x=x, y=y), headers={"User-Agent": UA})
    ultimo = None
    for _ in range(3):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                datos = r.read()
            Image.open(io.BytesIO(datos)).verify()
            with open(ruta + ".part", "wb") as f:
                f.write(datos)
            os.replace(ruta + ".part", ruta)
            return ruta
        except Exception as e:  # noqa: BLE001 -- se reintenta y al final se avisa
            ultimo = e
    raise RuntimeError(f"no se pudo bajar la imagen de satelite {z}/{x}/{y}: {ultimo}")


def _mosaico(caja, z, destino_dir):
    """Recorta [x0, y0, x1, y1] (Mercator) al nivel z. Devuelve {src, x0, y0, x1, y1} con la caja exacta."""
    n = 2 ** z
    x0, y0 = max(0.0, caja[0]), max(0.0, caja[1])
    x1, y1 = min(1.0, caja[2]), min(1.0, caja[3])
    # se baja de nivel hasta que el mosaico quepa
    while z > 1 and max((x1 - x0), (y1 - y0)) * 256 * n > LADO_MAX:
        z -= 1
        n = 2 ** z
    px0, py0, px1, py1 = int(x0 * 256 * n), int(y0 * 256 * n), math.ceil(x1 * 256 * n), math.ceil(y1 * 256 * n)
    nombre = "sat_" + hashlib.sha1(f"{z}/{px0}/{py0}/{px1}/{py1}".encode()).hexdigest()[:14] + ".jpg"
    salida = {"src": nombre, "x0": px0 / (256 * n), "y0": py0 / (256 * n), "x1": px1 / (256 * n), "y1": py1 / (256 * n)}
    ruta = os.path.join(destino_dir, nombre)
    if os.path.isfile(ruta):
        return salida, ruta
    tx0, ty0, tx1, ty1 = px0 // 256, py0 // 256, (px1 - 1) // 256, (py1 - 1) // 256
    pedidos = [(z, tx, ty) for ty in range(ty0, ty1 + 1) for tx in range(tx0, tx1 + 1)]
    with ThreadPoolExecutor(max_workers=6) as pool:
        archivos = list(pool.map(lambda p: _tesela(*p), pedidos))
    lienzo = Image.new("RGB", (px1 - px0, py1 - py0))
    for (_, tx, ty), archivo in zip(pedidos, archivos):
        with Image.open(archivo) as t:
            lienzo.paste(t.convert("RGBA").convert("RGB"), (tx * 256 - px0, ty * 256 - py0))
    os.makedirs(destino_dir, exist_ok=True)
    lienzo.save(ruta + ".part.jpg", "JPEG", quality=86)
    os.replace(ruta + ".part.jpg", ruta)
    return salida, ruta


def para_escena(camaras, w, h, destino_dir):
    """Mosaicos para una escena cuya camara pasa por `camaras` ([{x, y, z}], la inicial y las de cada toma).
    Devuelve (lista para ESCENA.satelite, {nombre: ruta} para copiar junto a la pagina)."""
    lista, archivos = [], {}

    def poner(caja, z):
        m, ruta = _mosaico(caja, z, destino_dir)
        if m["src"] not in archivos:
            lista.append(m)
            archivos[m["src"]] = ruta

    poner([0, my(85), 1, my(-85)], Z_MUNDO)
    # toda la escena, a la resolucion de lo mas lejano (los vuelos se alejan hasta ~1 nivel mas)
    z_lejos = min(c["z"] for c in camaras) - 1
    vistas = [_vista(c, w, h) for c in camaras]
    caja = [min(v[0] for v in vistas), min(v[1] for v in vistas), max(v[2] for v in vistas), max(v[3] for v in vistas)]
    lejos = _vista({"x": (caja[0] + caja[2]) / 2, "y": (caja[1] + caja[3]) / 2, "z": z_lejos}, w, h, 1.0)
    caja = [min(caja[0], lejos[0]), min(caja[1], lejos[1]), max(caja[2], lejos[2]), max(caja[3], lejos[3])]
    z_toda = _z_tesela(z_lejos, w, h)
    if z_toda > Z_MUNDO:
        poner(caja, z_toda)
    # cada toma cercana a su resolucion (al llegar sigue acercandose un poco: +0.3), con escalones cada 2
    # niveles hacia atras para que un acercamiento grande (pais -> ciudad) no se vea borroso por el camino
    escalones = []
    for c in camaras:
        z = c["z"] - 2
        while z > z_lejos + 1:
            escalones.append({**c, "z": z})
            z -= 2
    for c in sorted(camaras + escalones, key=lambda c: c["z"]):
        z = _z_tesela(c["z"] + 0.3, w, h)
        if z > z_toda:
            poner(_vista(c, w, h, 1.25), z)
    return lista, archivos
