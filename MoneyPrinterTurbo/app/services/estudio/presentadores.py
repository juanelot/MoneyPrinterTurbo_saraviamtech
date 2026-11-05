"""Presentadores propios de la Fabrica: un personaje plano (busto, de frente) hecho con Nano Banana (Flow) desde una
descripcion, o subido ya hecho. motion/fabrica/presentador.js lo anima encima del video: boca que sigue la voz sobre
su boca, parpados del color de su piel, balanceo y cabeceo. Ojos y boca se ubican solos analizando la imagen
(se pueden corregir a mano).

Desde una FOTO (de alguien que lo permita): Flow la toma como referencia y dibuja 3 opciones (FOTO_ESTILOS) en
presentadores/_fotos/<oid>/; al elegir una se guarda como las demas y la carpeta (foto incluida) se borra.

storage/estudio/presentadores/<pid>/imagen.webp (recortada, fondo transparente) y ficha.json:
  {id, nombre, descripcion, creado, ojos: [[x, y], [x, y]], boca: [x, y], ancho_boca, piel: "#rrggbb"}
  (posiciones de 0 a 1 sobre la imagen recortada)
Crear necesita Flow (este PC); una vez hecho es solo una imagen y vale en cualquier sitio.
"""
import io
import json
import os
import re
import shutil
import subprocess
import tempfile
import threading
import time
import uuid
from collections import deque

import numpy as np
from loguru import logger
from PIL import Image

from app.services.estudio import almacen, biblioteca, flow_gen

DIR = almacen.raiz("presentadores")
ALTO = 1200   # alto maximo de la imagen guardada

PROMPT = ("Flat 2D cartoon illustration of {que}. Chest-up portrait, head and shoulders, facing the camera straight on, "
          "friendly relaxed expression, eyes open looking at the viewer, mouth CLOSED in a soft smile. Clean bold dark "
          "brown outlines, flat colors with no gradients, no shading, modern explainer-video style. Centered, the whole "
          "head and hair visible with a little space above, cropped at mid chest. Solid pure chroma green background "
          "(#00FF00) filling the whole image, no shadow on the background, no text, no logo.")

FOTO = ("of the person in the reference photo, keep their likeness: same face shape, hairstyle and hair color, facial "
        "hair, glasses if any, skin tone and clothes. Front view, facing camera, chest up, centered, both arms relaxed "
        "down, mouth closed, eyes open looking at camera, solid flat pure chroma green background (#00FF00), no green "
        "on the character, no text, no hands near the face")
FOTO_ESTILOS = [   # el orden es el de las opciones 1, 2 y 3
    "Flat 2D vector cartoon presenter, thick dark outlines, flat colors, simple clean shapes, explainer video style, ",
    "Friendly caricature cartoon presenter with slightly bigger head, expressive, bold outlines, soft cel shading, ",
    "Modern 2D animated series character, clean lineart, soft shading, warm colors, ",
]
DIR_FOTOS = os.path.join(DIR, "_fotos")


def _ficha(pid):
    return almacen.leer_json(os.path.join(DIR, pid, "ficha.json"))


def listar():
    if not os.path.isdir(DIR):
        return []
    fichas = [f for f in (_ficha(p) for p in os.listdir(DIR)) if f and os.path.isfile(os.path.join(DIR, f["id"], "imagen.webp"))]
    return sorted(fichas, key=lambda f: f.get("creado", 0), reverse=True)


def ruta_imagen(pid):
    ruta = os.path.join(DIR, str(pid), "imagen.webp")
    return ruta if re.fullmatch(r"[0-9a-f]{10}", str(pid)) and os.path.isfile(ruta) else None


def aspecto(pid):
    """Lo que necesita presentador.js (sin la imagen, que va como archivo) o None."""
    f = _ficha(pid) if re.fullmatch(r"[0-9a-f]{10}", str(pid)) else None
    if not f or not ruta_imagen(pid):
        return None
    with Image.open(ruta_imagen(pid)) as img:
        w, h = img.size
    return {"proporcion": round(w / h, 4), "ojos": f["ojos"], "boca": f["boca"], "ancho_boca": f["ancho_boca"], "piel": f["piel"],
            "ojo_tam": f.get("ojo_tam") or [0.07, 0.04]}


def _guardar(pid, img_rgba, nombre, descripcion, origen):
    carpeta = os.path.join(DIR, pid)
    os.makedirs(carpeta, exist_ok=True)
    caja = img_rgba.getchannel("A").point(lambda a: 255 if a > 12 else 0).getbbox()
    if caja:
        img_rgba = img_rgba.crop(caja)
    if img_rgba.height > ALTO:
        img_rgba = img_rgba.resize((round(img_rgba.width * ALTO / img_rgba.height), ALTO), Image.LANCZOS)
    ruta = os.path.join(carpeta, "imagen.webp")
    img_rgba.save(ruta, "WEBP", quality=90, method=6)
    sitio = _ubicar(ruta)
    ficha = {"id": pid, "nombre": nombre[:40] or "Presentador", "descripcion": descripcion[:300], "creado": time.time(),
             "origen": origen, **sitio, "piel": _piel(img_rgba, sitio)}
    almacen.escribir_json(os.path.join(carpeta, "ficha.json"), ficha)
    return ficha


def _componentes(m):
    """Grupos de pixeles conectados (4 vecinos) de una mascara pequena: lista de arrays (y, x)."""
    h, w = m.shape
    visto = np.zeros((h, w), bool)
    grupos = []
    for y, x in zip(*np.nonzero(m)):
        if visto[y, x]:
            continue
        visto[y, x] = True
        cola, pts = deque([(y, x)]), []
        while cola:
            cy, cx = cola.popleft()
            pts.append((cy, cx))
            for ny, nx in ((cy + 1, cx), (cy - 1, cx), (cy, cx + 1), (cy, cx - 1)):
                if 0 <= ny < h and 0 <= nx < w and m[ny, nx] and not visto[ny, nx]:
                    visto[ny, nx] = True
                    cola.append((ny, nx))
        grupos.append(np.array(pts))
    return grupos


def _ubicar(ruta):
    """Ojos y boca (0-1) de un busto de dibujo, sin modelos: la cara es la mancha de piel del centro; los ojos, el
    par de huecos simetricos con blanco dentro (las cejas no tienen); la boca, la primera fila ancha de trazo oscuro entre la
    nariz y la barbilla. Si algo falla, la posicion tipica de un busto."""
    defecto = {"ojos": [[0.4, 0.33], [0.6, 0.33]], "boca": [0.5, 0.5], "ancho_boca": 0.11, "ojo_tam": [0.07, 0.04]}
    try:
        with Image.open(ruta) as img:
            S = 200
            img = img.convert("RGBA").resize((S, max(1, round(img.height * S / img.width))))
        a = np.asarray(img).astype(np.float32)
        h, w = a.shape[:2]
        rgb, opaco = a[..., :3], a[..., 3] > 200
        piel = np.median(rgb[int(h * .4):int(h * .5), int(w * .42):int(w * .58)].reshape(-1, 3), axis=0)
        mascara = (np.linalg.norm(rgb - piel, axis=2) < 50) & opaco

        def mover(m, r, crece):   # dilatar (crece) o erosionar r pixeles
            o = m.copy()
            for dy in range(-r, r + 1):
                for dx in range(-r, r + 1):
                    d = np.roll(np.roll(m, dy, 0), dx, 1)
                    o = (o | d) if crece else (o & d)
            return o

        mascara = mover(mover(mascara, 2, True), 2, False)   # cierra lineas finas: monturas, contornos
        grupos = _componentes(mascara)
        cy0, cx0 = int(h * .45), int(w * .5)
        cara = next((g for g in grupos if ((g[:, 0] == cy0) & (g[:, 1] == cx0)).any()), max(grupos, key=len))
        y0, x0 = cara.min(0)
        y1, x1 = cara.max(0)
        caja = np.ones((y1 - y0 + 1, x1 - x0 + 1), bool)
        caja[cara[:, 0] - y0, cara[:, 1] - x0] = False   # lo que no es cara dentro de su caja
        # huecos = lo que no es cara y no se alcanza desde el borde de la caja
        fuera = np.zeros_like(caja)
        borde = [(y, x) for y in range(caja.shape[0]) for x in (0, caja.shape[1] - 1)] +                 [(y, x) for x in range(caja.shape[1]) for y in (0, caja.shape[0] - 1)]
        cola = deque(p for p in borde if caja[p])
        for p in cola:
            fuera[p] = True
        while cola:
            cy, cx = cola.popleft()
            for ny, nx in ((cy + 1, cx), (cy - 1, cx), (cy, cx + 1), (cy, cx - 1)):
                if 0 <= ny < caja.shape[0] and 0 <= nx < caja.shape[1] and caja[ny, nx] and not fuera[ny, nx]:
                    fuera[ny, nx] = True
                    cola.append((ny, nx))
        lum = rgb.mean(2)
        huecos = []
        for g in _componentes(caja & ~fuera):
            if len(g) < 8:
                continue
            yy, xx = g[:, 0] + y0, g[:, 1] + x0
            huecos.append({"x": xx.mean(), "y": yy.mean(), "w": xx.max() - xx.min() + 1, "h": yy.max() - yy.min() + 1,
                           "blanco": float((lum[yy, xx] > 200).mean())})
        mejor = None
        for k, p in enumerate(huecos):
            for q in huecos[k + 1:]:
                if abs(p["y"] - q["y"]) > 0.03 * h or (p["x"] - w / 2) * (q["x"] - w / 2) >= 0:
                    continue
                puntos = p["blanco"] + q["blanco"] + 0.3 * (1 - abs((p["x"] + q["x"]) / 2 - w / 2) / (w / 2))
                if not mejor or puntos > mejor[0]:
                    mejor = (puntos, sorted([p, q], key=lambda c: c["x"]))
        if not mejor:
            return defecto
        oi, od = mejor[1]
        sep, ey, cx = od["x"] - oi["x"], (oi["y"] + od["y"]) / 2, (oi["x"] + od["x"]) / 2
        oscuro = (lum < 110) & opaco
        filas = []
        for y in range(int(ey + 0.55 * sep), min(h, int(ey + 1.5 * sep))):
            xs = np.nonzero(oscuro[y, int(cx - 0.45 * sep):int(cx + 0.45 * sep)])[0]
            x0b = int(cx - 0.45 * sep)
            filas.append((len(xs), y, (xs.max() - xs.min() + 1) if len(xs) else 0,
                          (x0b + (xs.min() + xs.max()) / 2) if len(xs) else cx))
        # la boca es la PRIMERA linea ancha bajo la nariz: la barba (perilla) tambien es oscura y ancha, pero va debajo
        tope = max((f[2] for f in filas), default=0)
        # centrada en la propia linea de los labios (el punto medio de los ojos se desvia si uno se mide corrido)
        _n, my, ancho, mx = next((f for f in filas if tope and f[2] >= 0.6 * tope), (0, ey + sep, sep * 0.6, cx))
        r4 = lambda v: round(float(v), 4)
        return {"ojos": [[r4(oi["x"] / w), r4(oi["y"] / h)], [r4(od["x"] / w), r4(od["y"] / h)]],
                "boca": [r4(mx / w), r4(my / h)], "ancho_boca": r4(min(0.3, max(0.05, ancho / w))),
                "ojo_tam": [r4((oi["w"] + od["w"]) / 2 / w), r4((oi["h"] + od["h"]) / 2 / h)]}
    except Exception as e:  # noqa: BLE001
        logger.warning(f"presentadores: no se pudieron ubicar ojos y boca: {e}")
    return defecto


def _piel(img, sitio):
    """Color de la piel: la mediana de una franja entre los ojos y la boca (en las mejillas)."""
    rgb = np.asarray(img.convert("RGBA")).astype(np.float32)
    h, w = rgb.shape[:2]
    y = int(h * (sitio["ojos"][0][1] + sitio["boca"][1]) / 2)
    xs = [int(w * sitio["ojos"][0][0]), int(w * sitio["ojos"][1][0])]
    trozo = np.concatenate([rgb[max(0, y - 6):y + 6, max(0, x - 10):x + 10].reshape(-1, 4) for x in xs])
    trozo = trozo[trozo[:, 3] > 200][:, :3]
    if not len(trozo):
        return "#f1c7a3"
    r, g, b = np.median(trozo, axis=0)
    return "#%02x%02x%02x" % (int(r), int(g), int(b))


def crear(nombre, descripcion):
    """Un presentador nuevo dibujado por Nano Banana desde una descripcion (~45 s, solo en el PC con Flow)."""
    descripcion = str(descripcion or "").strip()
    if not descripcion:
        raise ValueError("describe como es el presentador")
    pid = uuid.uuid4().hex[:10]
    tmp = tempfile.mkdtemp(prefix="presentador_", dir=almacen.raiz())
    try:
        recorte = os.path.join(tmp, "recorte.webp")
        biblioteca._generar("pegatinas", PROMPT.format(que=biblioteca.sin_estilo(descripcion)), recorte, alto=ALTO)
        with Image.open(recorte) as img:
            return _guardar(pid, img.convert("RGBA"), str(nombre or "").strip(), descripcion, "flow")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def subir(datos, nombre, fondo_verde=False):
    """Un presentador ya hecho: PNG/WebP con transparencia (o sobre verde croma)."""
    tmp = tempfile.mkdtemp(prefix="presentador_", dir=almacen.raiz())
    try:
        entrada = os.path.join(tmp, "subida")
        with open(entrada, "wb") as f:
            f.write(datos)
        with Image.open(entrada) as img:
            if fondo_verde:
                recorte = os.path.join(tmp, "recorte.webp")
                biblioteca.recortar(img, recorte, ALTO)
                img2 = Image.open(recorte).convert("RGBA")
            else:
                img2 = img.convert("RGBA")
            return _guardar(uuid.uuid4().hex[:10], img2, str(nombre or "").strip(), "", "subido")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def corregir(pid, ojos=None, boca=None, ancho_boca=None, nombre=None):
    """Ajuste a mano de ojos y boca (0-1) o del nombre."""
    f = _ficha(pid)
    if not f:
        raise ValueError("ese presentador no existe")
    p = lambda v: [round(min(1, max(0, float(v[0]))), 4), round(min(1, max(0, float(v[1]))), 4)]
    if ojos and len(ojos) == 2:
        f["ojos"] = sorted([p(ojos[0]), p(ojos[1])])
    if boca:
        f["boca"] = p(boca)
    if ancho_boca:
        f["ancho_boca"] = round(min(0.4, max(0.04, float(ancho_boca))), 4)
    if nombre:
        f["nombre"] = str(nombre)[:40]
    with Image.open(ruta_imagen(pid)) as img:
        f["piel"] = _piel(img, f)
    almacen.escribir_json(os.path.join(DIR, pid, "ficha.json"), f)
    return f


def borrar(pid):
    if not re.fullmatch(r"[0-9a-f]{10}", str(pid)):
        raise ValueError("id no valido")
    shutil.rmtree(os.path.join(DIR, pid), ignore_errors=True)
    return {"ok": True}


def _carpeta_foto(oid):
    if not re.fullmatch(r"[0-9a-f]{10}", str(oid)):
        raise ValueError("id no valido")
    return os.path.join(DIR_FOTOS, oid)


def desde_foto(datos):
    """Empieza a dibujar 3 opciones de presentador con la foto como referencia (Nano Banana, ~3 min, solo en el PC
    con Flow) en segundo plano: devuelve {id, estado}; estado_foto(id) dice como va."""
    if not flow_gen.habilitado():
        raise flow_gen.NoHabilitado("crear desde foto solo funciona en el PC con Flow")
    flow_gen._exigir()
    try:
        img = Image.open(io.BytesIO(datos))
        img.load()
    except Exception as e:  # noqa: BLE001
        raise ValueError(f"no es una imagen valida: {e}") from e
    oid = uuid.uuid4().hex[:10]
    carpeta = _carpeta_foto(oid)
    os.makedirs(carpeta, exist_ok=True)
    img = img.convert("RGB")
    img.thumbnail((1600, 1600))
    img.save(os.path.join(carpeta, "foto.jpg"), "JPEG", quality=92)
    almacen.escribir_json(os.path.join(carpeta, "estado.json"), {"estado": "trabajando"})
    threading.Thread(target=_dibujar_foto, args=(oid,), daemon=True, name=f"presentador-{oid}").start()
    return estado_foto(oid)


def _dibujar_foto(oid):
    carpeta = _carpeta_foto(oid)
    estado = os.path.join(carpeta, "estado.json")
    try:
        foto = os.path.abspath(os.path.join(carpeta, "foto.jpg"))
        script = os.path.join(carpeta, "script.json")
        almacen.escribir_json(script, {"scenes": [{"scene_number": k + 1, "image_prompt": e + FOTO, "ref_images": [foto]}
                                                  for k, e in enumerate(FOTO_ESTILOS)]})
        r = subprocess.run([flow_gen._node(), os.path.join(flow_gen._dir_flow(), "lote.js"), "--script", script,
                            "--out", carpeta, "--aspect", "3:4", "--model", "2", "--pasadas-extra", "1"],
                           cwd=flow_gen._dir_flow(), capture_output=True, text=True, encoding="utf-8", errors="replace",
                           timeout=1500, **flow_gen.SIN_VENTANA)
        if not _opciones(oid):
            eventos = [json.loads(x) for x in (r.stdout or "").splitlines() if x.startswith("{")]
            motivo = next((e.get("motivo") for e in reversed(eventos) if e.get("motivo")), "") or (r.stderr or "")[-300:]
            if r.returncode == 3:
                motivo = "no hay sesion en Flow: conecta Flow en el Estudio e inicia sesion"
            raise RuntimeError(f"Nano Banana no pudo dibujar desde la foto: {motivo or 'sin respuesta'}")
        if os.path.isdir(carpeta):   # si se descarto mientras tanto no se recrea
            almacen.escribir_json(estado, {"estado": "listo"})
    except Exception as e:  # noqa: BLE001 -- se ve en la interfaz
        logger.exception(f"presentador desde foto {oid}")
        if os.path.isdir(carpeta):
            almacen.escribir_json(estado, {"estado": "error", "error": str(e)[:400]})


def _opciones(oid):
    carpeta = _carpeta_foto(oid)
    if not os.path.isdir(carpeta):
        return []
    return sorted(int(n[6:10]) for n in os.listdir(carpeta) if n.startswith("scene_") and not n.endswith(".part"))


def estado_foto(oid):
    """{id, estado: trabajando|listo|error, opciones: [n...] (las que ya salieron), error}."""
    e = almacen.leer_json(os.path.join(_carpeta_foto(oid), "estado.json"))
    if not e:
        raise FileNotFoundError("esa foto ya no existe: vuelve a subirla")
    return {"id": oid, **e, "opciones": _opciones(oid), "total": len(FOTO_ESTILOS)}


def ruta_opcion(oid, n):
    carpeta = _carpeta_foto(oid)
    if not os.path.isdir(carpeta):
        return None
    return next((os.path.join(carpeta, x) for x in os.listdir(carpeta)
                 if x.startswith(f"scene_{int(n):04d}.") and not x.endswith(".part")), None)


def elegir(oid, n, nombre):
    """Guarda la opcion n como presentador y borra la foto y las demas opciones."""
    ruta = ruta_opcion(oid, n)
    if not ruta:
        raise ValueError("esa opcion ya no existe: vuelve a subir la foto")
    tmp = tempfile.mkdtemp(prefix="presentador_", dir=almacen.raiz())
    try:
        recorte = os.path.join(tmp, "recorte.webp")
        with Image.open(ruta) as img:
            biblioteca.recortar(img, recorte, ALTO)
        with Image.open(recorte) as img:
            ficha = _guardar(uuid.uuid4().hex[:10], img.convert("RGBA"), str(nombre or "").strip(), "", "foto")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    shutil.rmtree(_carpeta_foto(oid), ignore_errors=True)
    return ficha


def descartar_foto(oid):
    shutil.rmtree(_carpeta_foto(oid), ignore_errors=True)
    return {"ok": True}
