"""
Biblioteca de dibujos de la Fabrica: pegatinas (personajes y objetos de juguete sobre fondo transparente,
se ponen encima del mapa) e ilustraciones (escenas verticales a pantalla completa).

  - BASE: vienen con el motor (motion/fabrica/pegatinas, motion/fabrica/ilustraciones y datos/catalogo.json),
    hechas con Nano Banana por motion/fabrica/datos/hacer_pegatinas.py.
  - PROPIAS: las que crea la persona (con Nano Banana en Flow, solo en el PC local) o sube ella misma.
    storage/estudio/fabrica_biblioteca/<tipo>/<id>.webp y catalogo.json. Una propia con el mismo id que
    una base la sustituye.

Las pegatinas se piden a Nano Banana sobre verde croma y aqui se quita el fondo (recortar).
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
import unicodedata

import numpy as np
from PIL import Image

from app.services.estudio import almacen, flow_gen, graficos

DIR_BASE = os.path.join(graficos.DIR_MOTION, "fabrica")
TIPOS = ("pegatinas", "ilustraciones")
ALTO_PEGATINA = 640
_candado = threading.Lock()

# Prompts (en ingles: Nano Banana sigue mejor el estilo). {} = lo que hay que dibujar.
FIGURA = ("A cute collectible wooden toy figurine of {}, rounded peg-doll body, glossy painted wood, "
          "soft studio lighting, 3D render, full body, centered")
OBJETO = "A cute miniature toy of {}, stylized, 3D render, soft studio lighting, centered"
FONDO = ", isolated on a perfectly flat solid pure green #00FF00 chroma key background, no shadow on background"
ESCENA = ("Miniature diorama photo of {}, all people are cute wooden peg-doll toy figurines with round heads, "
          "cinematic warm lighting, shallow depth of field, highly detailed, vertical composition")

# Familias de dibujo: los mismos ids que la base (munecos de madera) dibujados de otra forma, para los estilos
# que no pegan con la madera (ESTILOS de fabrica.py dice cual usa cada uno). motion/fabrica/familias/<familia>/<tipo>/,
# hechas con motion/fabrica/datos/hacer_estilos.py. Lo que una familia no tenga sale de la base.
FAMILIAS = {
    "plano": {
        "pegatina": "A flat vector sticker illustration of {}, bold clean shapes, minimal shading, vibrant colors, "
                    "thick white sticker outline, modern editorial style, full figure, centered",
        "escena": "Flat vector illustration of {}, clean geometric shapes, bold limited color palette, modern editorial "
                  "style, subtle grain, highly detailed, vertical composition",
    },
    "grabado": {
        "pegatina": "A vintage hand-colored engraving illustration of {}, fine crosshatch ink lines, muted faded colors, "
                    "19th century encyclopedia plate style, full figure, centered, no paper background",
        "escena": "Vintage 19th century hand-colored engraving of {}, fine crosshatch ink lines, aged paper tones, "
                  "old newspaper illustration style, highly detailed, vertical composition",
    },
    # Las de abajo no vienen hechas: cada video genera lo que use y le falte (version_familia) y se guarda.
    "foto": {
        "pegatina": "A photorealistic photo of {}, real materials and textures, professional studio product photography, "
                    "sharp focus, natural colors, full figure, centered",
        "escena": "Photorealistic documentary photograph of {}, real people and places, natural cinematic lighting, "
                  "shot on 35mm, highly detailed, realistic textures, vertical composition",
    },
    "acuarela": {
        "pegatina": "A watercolor painting of {}, soft wet edges, delicate pigment blooms, hand-painted, light pencil lines, "
                    "full figure, centered",
        "escena": "Watercolor painting of {}, soft washes of color, visible paper texture, delicate hand-painted details, "
                  "storybook illustration, vertical composition",
    },
    "comic": {
        "pegatina": "A comic book illustration of {}, bold black ink outlines, flat cel shading, halftone dots, "
                    "dynamic pose, full figure, centered",
        "escena": "Comic book panel of {}, bold black ink outlines, cel shading, halftone dot texture, dramatic angle, "
                  "vibrant colors, vertical composition",
    },
    "recortes": {
        "pegatina": "A layered paper cutout craft of {}, cut colored cardstock layers with soft shadows between them, "
                    "handmade papercraft, full figure, centered",
        "escena": "Layered paper cutout diorama of {}, cut colored cardstock layers with depth and soft shadows, handmade "
                  "papercraft art, vertical composition",
    },
    # palitos de animacion 2.5D: toda persona sale como stickman (cabeza redonda, sin cara ni ropa)
    "stickman": {
        "pegatina": "A 3D rendered stick figure of {}, every person drawn as a simple white stickman with a round head, "
                    "thin cylindrical limbs, no face details and no clothes, expressive pose, only the key props, "
                    "soft studio lighting, clean minimal 3D animation style, full figure, centered",
        "escena": "Minimal 3D animation scene of {}, every person drawn as a simple white stickman with a round head and "
                  "thin cylindrical limbs, no face details and no clothes, simple low-detail environment with soft "
                  "shadows, cinematic lighting, muted colors, 2.5D explainer animation style, vertical composition",
    },
}
# nombre para la pantalla de cada familia (madera es la base)
NOMBRES_FAMILIA = {"madera": "Munecos de madera", "plano": "Ilustracion plana", "grabado": "Grabado antiguo",
                   "foto": "Realista (foto)", "acuarela": "Acuarela", "comic": "Comic", "recortes": "Recortes de papel",
                   "stickman": "Stickman (palitos)"}
DIR_FAMILIAS = os.path.join(DIR_BASE, "familias")

# Grupos para ordenar la biblioteca en pantalla (lo que no este aqui va a "otros"; las propias, a "propias").
GRUPOS = {
    "historia": ("Historia y guerra", "rey reina emperador_romano legionario faraon vikingo caballero samurai conquistador "
                 "explorador pirata napoleon soldado_1914 soldado_1944 soldado_moderno corona canon espadas escudo bomba "
                 "tanque avion_guerra buque_guerra castillo muralla piramide pergamino mapa_antiguo bandera_blanca "
                 "trono rey_enfermo tratado batalla_naval batalla asedio desembarco exploradores"),
    "personas": ("Personas y oficios", "marinero presidente diplomatico monje campesino mercader jeque vaquero inuit "
                 "cientifico astronauta turista minero pescador nino abuela obrero banquero hombre_negocios inversor "
                 "trabajadora votacion parlamento protesta aula"),
    "dinero": ("Dinero y finanzas", "dinero monedas lingotes grafico_sube grafico_baja oro diamante hucha tarjeta_credito "
               "bitcoin cartera factura carrito calculadora maletin banco_edificio bolsa_dinero billete_quemado "
               "etiqueta_precio casa_venta toro_bolsa oso_bolsa trofeo urna bolsa banco facturas inversor_pantallas "
               "cajero supermercado tienda_barrio oficina mercado"),
    "lugares": ("Lugares y transporte", "barco_vela barco_carga avion tren_vapor coche camion cohete fabrica casa "
                "rascacielos puente presa tienda_campana petroleo puerto caravana construccion frontera muro "
                "ciudad_moderna atasco hospital cocina"),
    "naturaleza": ("Naturaleza y animales", "mono camello oso_polar pinguino elefante canguro leon dinosaurio gato perro "
                   "tiburon pulpo abeja hormiga montana volcan palmera arbol iceberg gota fuego sol nube_lluvia rayo "
                   "trigo granja rio_nilo hielo_polar fondo_mar dinosaurios"),
    "ciencia": ("Ciencia y curiosidades", "bombilla cerebro corazon adn microscopio telescopio planeta luna robot movil "
                "ordenador brujula globo_terraqueo lupa reloj_arena calendario libro candado llave pizza hamburguesa "
                "cafe chocolate medicina interrogacion exclamacion regalo reloj medalla laboratorio espacio"),
}
_GRUPO_DE = {k: g for g, (_n, ids) in GRUPOS.items() for k in ids.split()}
# que grupos se ven primero con cada nicho de la Fabrica
NICHO_GRUPOS = {
    "mapas": ["historia", "lugares", "personas", "naturaleza"],
    "datos": ["dinero", "lugares", "ciencia", "personas"],
    "curiosidades": ["ciencia", "naturaleza", "personas", "historia"],
    "finanzas": ["dinero", "personas", "lugares"],
    "historia": ["historia", "personas", "lugares"],
    "ciencia": ["ciencia", "naturaleza", "personas", "lugares"],
    "animales": ["naturaleza", "personas", "lugares"],
    "tecnologia": ["ciencia", "dinero", "personas", "lugares"],
    "misterios": ["historia", "personas", "lugares", "naturaleza", "ciencia"],
}


def prompt(tipo, que, clase="personaje", familia=None):
    """Prompt de Nano Banana para una pegatina (clase personaje u objeto) o una ilustracion, en la familia de
    dibujo pedida (sin familia, munecos de madera)."""
    if familia in FAMILIAS:
        f = FAMILIAS[familia]
        return f["escena"].format(que) if tipo == "ilustraciones" else f["pegatina"].format(que) + FONDO
    if tipo == "ilustraciones":
        return ESCENA.format(que)
    return (FIGURA if clase == "personaje" else OBJETO).format(que) + FONDO


def recortar(img, destino):
    """Quita el fondo verde croma: alfa segun lo verde que es cada pixel y fuera el reflejo verde del borde."""
    rgb = np.asarray(img.convert("RGB")).astype(np.float32)
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    verdor = g - np.maximum(r, b)
    alfa = 1 - np.clip((verdor - 40) / (110 - 40), 0, 1)
    g2 = np.where(verdor > 0, np.maximum(r, b) + np.clip(verdor, 0, None) * 0.15, g)
    rgba = np.dstack([r, np.minimum(g, g2), b, alfa * 255]).clip(0, 255).astype(np.uint8)
    _guardar_pegatina(Image.fromarray(rgba, "RGBA"), destino)


def _guardar_pegatina(pic, destino):
    caja = pic.getchannel("A").point(lambda a: 255 if a > 12 else 0).getbbox()
    if caja:
        pic = pic.crop(caja)
    if pic.height > ALTO_PEGATINA:
        pic = pic.resize((round(pic.width * ALTO_PEGATINA / pic.height), ALTO_PEGATINA), Image.LANCZOS)
    pic.save(destino, "WEBP", quality=88, method=6)


def _guardar_ilustracion(img, destino):
    img = img.convert("RGB")
    if img.height > 1600:
        img = img.resize((round(img.width * 1600 / img.height), 1600), Image.LANCZOS)
    img.save(destino, "WEBP", quality=82, method=6)


# ------------------------------------------------------------------ catalogo

def _dir_propias(*partes):
    return almacen.raiz("fabrica_biblioteca", *partes)


def _leer_propias():
    return almacen.leer_json(_dir_propias("catalogo.json"), {}) or {}


def _leer_base():
    ruta = os.path.join(DIR_BASE, "datos", "catalogo.json")
    if not os.path.isfile(ruta):
        return {}
    with open(ruta, encoding="utf-8") as f:
        return json.load(f)


def listar():
    """{"pegatinas": [{id, descripcion, origen}], "ilustraciones": [...], "crear": bool (Flow en esta maquina)}"""
    base, propias = _leer_base(), _leer_propias()
    salida = {}
    for tipo in TIPOS:
        filas = {k: {"id": k, "descripcion": d, "origen": "base", "grupo": _GRUPO_DE.get(k, "otros")}
                 for k, d in (base.get(tipo) or {}).items() if os.path.isfile(os.path.join(DIR_BASE, tipo, f"{k}.webp"))}
        for k, info in (propias.get(tipo) or {}).items():
            if os.path.isfile(_dir_propias(tipo, f"{k}.webp")):
                filas[k] = {"id": k, "descripcion": info.get("descripcion", ""), "origen": "propia",
                            "creado": info.get("creado"), "grupo": "propias"}
        salida[tipo] = sorted(filas.values(), key=lambda f: (f["origen"] != "propia", f["id"]))
    salida["crear"] = flow_gen.habilitado()
    salida["grupos"] = [{"id": g, "nombre": n} for g, (n, _ids) in GRUPOS.items()] + \
        [{"id": "otros", "nombre": "Otros"}, {"id": "propias", "nombre": "Propias"}]
    salida["nichos"] = NICHO_GRUPOS
    salida["familias"] = ["madera", *FAMILIAS]
    return salida


def _version(tipo, clave, familia):
    """La version de un dibujo en una familia, si existe: la generada por un video (storage) o la del motor."""
    for r in (_dir_propias("familias", familia, tipo, f"{clave}.webp"), os.path.join(DIR_FAMILIAS, familia, tipo, f"{clave}.webp")):
        if os.path.isfile(r):
            return r
    return None


def ruta(tipo, clave, familia=None):
    """Archivo de una pegatina o ilustracion, o None. Sin familia: la propia gana a la base. Con familia: su version
    en esa familia gana (si no, la propia y luego la base, sea del aspecto que sea)."""
    if tipo not in TIPOS or not re.fullmatch(r"[a-z0-9_]{1,40}", clave or ""):
        return None
    if familia in FAMILIAS and (v := _version(tipo, clave, familia)):
        return v
    for r in (_dir_propias(tipo, f"{clave}.webp"), os.path.join(DIR_BASE, tipo, f"{clave}.webp")):
        if os.path.isfile(r):
            return r
    return None


def tiene_version(tipo, clave, familia):
    """Si el dibujo ya se ve en esa familia (madera = la base o una propia hecha en madera)."""
    return familia not in FAMILIAS or bool(_version(tipo, clave, familia)) or _familia_propia(tipo, clave) == familia


def _familia_propia(tipo, clave):
    info = (_leer_propias().get(tipo) or {}).get(clave)
    return (info or {}).get("familia") if info else None


def version_familia(tipo, clave, familia):
    """Genera con Nano Banana la version de un dibujo en otra familia (misma descripcion) y la guarda para los
    siguientes videos. Solo local (Flow)."""
    if familia not in FAMILIAS:
        raise ValueError("familia no valida")
    base, propias = _leer_base(), _leer_propias()
    info = (propias.get(tipo) or {}).get(clave)
    descripcion = (info or {}).get("descripcion") or (base.get(tipo) or {}).get(clave)
    if not descripcion:
        raise FileNotFoundError(f"no hay descripcion de {clave}")
    clase = (info or {}).get("clase") or ("objeto" if _GRUPO_DE.get(clave) in ("dinero", "lugares", "ciencia") else "personaje")
    destino = _dir_propias("familias", familia, tipo, f"{clave}.webp")
    _generar(tipo, prompt(tipo, sin_estilo(descripcion), clase, familia), destino)
    return destino


# palabras de estilo que algunas descripciones viejas traen ("a wooden toy octopus"): al pasar a otra familia
# se quitan, si no Nano Banana fotografia un juguete en vez del animal
_ESTILO = re.compile(r"\b(cute|collectible|wooden|wood|toy|toys|figurines?|peg[- ]?dolls?|miniature|diorama|cartoon|"
                     r"stickers?|3d render|stylized|plush|clay|lego)\b", re.I)


def sin_estilo(texto):
    # "a cute wooden toy figurine of a king" -> "a king"
    limpio = re.sub(r"^(an?\s+)?((cute|collectible|wooden|wood|toy|miniature|small|little)\s+)*"
                    r"(figurines?|figures?|toys?|models?|dolls?|peg[- ]?dolls?)\s+of\s+", "", str(texto or ""), flags=re.I)
    limpio = re.sub(r"\s{2,}", " ", _ESTILO.sub("", limpio)).strip(" ,.")
    limpio = re.sub(r"^(an?|the)\s+(?=an?\s|the\s)", "", limpio, flags=re.I)   # "a a octopus"
    return re.sub(r"^an?\s+(?=[aeiou])", "an ", re.sub(r"^an\s+(?=[^aeiou])", "a ", limpio, flags=re.I), flags=re.I) or texto


def para_claude(nicho=None):
    """Lo que Claude puede usar, en pocas lineas: 'id: descripcion'. Con nicho, solo los grupos de ese nicho y las
    propias (la biblioteca entera es lo que mas alarga el prompt del guion)."""
    datos = listar()
    grupos = set(NICHO_GRUPOS.get(nicho) or GRUPOS)
    sirve = lambda f: f.get("grupo") in grupos or f.get("grupo") not in GRUPOS   # noqa: E731 -- propias y sin grupo, siempre
    return {tipo: "; ".join(f"{f['id']} ({f['descripcion']})" for f in datos[tipo] if sirve(f)) for tipo in TIPOS}


def descripcion(tipo, clave):
    """Lo que es un dibujo (sin palabras de estilo), de las propias o de la base, o None."""
    info = (_leer_propias().get(tipo) or {}).get(clave)
    d = (info or {}).get("descripcion") or (_leer_base().get(tipo) or {}).get(clave)
    return sin_estilo(d) if d else None


def clave_de(texto):
    s = unicodedata.normalize("NFD", str(texto or "").lower())
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]+", "_", s).strip("_")[:40]


def _clave_libre(tipo, nombre):
    k = clave_de(nombre) or "dibujo"
    base, n = k, 2
    while ruta(tipo, k):
        k = f"{base[:36]}_{n}"
        n += 1
    return k


def _anotar(tipo, clave, descripcion, **extra):
    with _candado:
        cat = _leer_propias()
        cat.setdefault(tipo, {})[clave] = {"descripcion": descripcion[:120], "creado": time.time(), **extra}
        os.makedirs(_dir_propias(), exist_ok=True)
        almacen.escribir_json(_dir_propias("catalogo.json"), cat)


# ------------------------------------------------------------------ crear, subir, borrar

def crear(tipo, descripcion, nombre="", clase="personaje", reemplazar=False, familia=None):
    """Genera con Nano Banana (Flow, solo local) y la guarda como propia. Bloquea ~40-90 s (mas si Flow
    esta ocupado con otra cosa: espera su turno). Devuelve la fila del catalogo."""
    if tipo not in TIPOS:
        raise ValueError("tipo: pegatinas o ilustraciones")
    descripcion = str(descripcion or "").strip()
    if not descripcion:
        raise ValueError("describe lo que quieres dibujar")
    clave = clave_de(nombre or descripcion) if reemplazar else _clave_libre(tipo, nombre or descripcion)
    _generar(tipo, prompt(tipo, descripcion, clase, familia), _dir_propias(tipo, f"{clave}.webp"))
    _anotar(tipo, clave, descripcion, clase=clase, **({"familia": familia} if familia in FAMILIAS else {}))
    return {"id": clave, "descripcion": descripcion, "origen": "propia"}


def _generar(tipo, texto, destino):
    """Una imagen con Nano Banana (Flow) guardada en destino: pegatina recortada del verde o ilustracion vertical."""
    if not flow_gen.habilitado():
        raise flow_gen.NoHabilitado("crear con Nano Banana solo funciona en el PC con Flow (aqui puedes subir una imagen)")
    flow_gen._exigir()
    tmp = tempfile.mkdtemp(prefix="biblio_", dir=almacen.raiz())
    try:
        script = os.path.join(tmp, "script.json")
        with open(script, "w", encoding="utf-8") as f:
            json.dump({"scenes": [{"scene_number": 1, "image_prompt": texto}]}, f, ensure_ascii=False)
        r = subprocess.run([flow_gen._node(), os.path.join(flow_gen._dir_flow(), "lote.js"), "--script", script,
                            "--out", tmp, "--aspect", "9:16" if tipo == "ilustraciones" else "1:1", "--model", "2",
                            "--pasadas-extra", "1"], cwd=flow_gen._dir_flow(), capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=900, **flow_gen.SIN_VENTANA)
        hecha = next((os.path.join(tmp, n) for n in os.listdir(tmp) if n.startswith("scene_0001.") and not n.endswith(".part")), None)
        if not hecha:
            eventos = [json.loads(x) for x in (r.stdout or "").splitlines() if x.startswith("{")]
            motivo = next((e.get("motivo") for e in reversed(eventos) if e.get("motivo")), "") or (r.stderr or "")[-300:]
            if r.returncode == 3:
                motivo = "no hay sesion en Flow: conecta Flow en el Estudio (paso Contenido) e inicia sesion"
            raise RuntimeError(f"Nano Banana no pudo hacer el dibujo: {motivo or 'sin respuesta'}")
        os.makedirs(os.path.dirname(destino), exist_ok=True)
        with Image.open(hecha) as img:
            (recortar if tipo == "pegatinas" else _guardar_ilustracion)(img, destino)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def subir(tipo, datos, nombre, descripcion="", fondo_verde=False):
    """Una imagen propia. Pegatina: PNG/WebP con transparencia (o sobre verde croma: fondo_verde=True)."""
    if tipo not in TIPOS:
        raise ValueError("tipo: pegatinas o ilustraciones")
    if not str(nombre or "").strip():
        raise ValueError("ponle un nombre")
    try:
        img = Image.open(io.BytesIO(datos))
        img.load()
    except Exception as e:  # noqa: BLE001
        raise ValueError(f"no es una imagen valida: {e}") from e
    clave = _clave_libre(tipo, nombre)
    os.makedirs(_dir_propias(tipo), exist_ok=True)
    destino = _dir_propias(tipo, f"{clave}.webp")
    if tipo == "ilustraciones":
        _guardar_ilustracion(img, destino)
    elif fondo_verde:
        recortar(img, destino)
    else:
        _guardar_pegatina(img.convert("RGBA"), destino)
    _anotar(tipo, clave, str(descripcion or nombre).strip())
    return {"id": clave, "descripcion": str(descripcion or nombre).strip(), "origen": "propia"}


def borrar(tipo, clave):
    """Solo las propias (las base vienen con el motor)."""
    with _candado:
        cat = _leer_propias()
        if clave not in (cat.get(tipo) or {}):
            raise FileNotFoundError("solo se pueden borrar los dibujos propios")
        del cat[tipo][clave]
        almacen.escribir_json(_dir_propias("catalogo.json"), cat)
    try:
        os.remove(_dir_propias(tipo, f"{clave}.webp"))
    except FileNotFoundError:
        pass
