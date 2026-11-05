"""Blender: planos 3D (munecos de barro, plastico, vinilo o peluche) para las escenas 'barro' de la Fabrica.

El kit (motion/blender/kit.py) monta un plano desde un JSON (personaje, escenario, camara, gesto, cara, boca y
objetos) y Blender lo renderiza sin ventana, una pose de cada dos fotogramas (animado en doses, como el stop-motion).
Aqui se cachea por contenido y se pasa a un clip de video de la Fabrica; encima van los subtitulos y los textos
(escena dibujada sobre verde croma, como los clips subidos).

Solo donde hay Blender instalado (este PC); sin tarjeta grafica un plano de 3 s tarda unos 4 min en borrador.
"""
import glob
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import threading

from loguru import logger

from app.config import config
from app.services.estudio import graficos, medios, modelos3d

DIR_KIT = os.path.join(graficos.DIR_MOTION, "blender")
FPS_KIT = 24                     # Blender anima a 24 fps y dibuja una pose de cada dos (12 poses/s)
_ocupado = threading.Lock()      # un Blender cada vez (usa toda la CPU)

FORMAS = {"huevo": "Huevo", "cubo": "Cubo", "gota": "Gota", "gato": "Gato", "perro": "Perro", "oso": "Oso",
          "conejo": "Conejo", "robot": "Robot", "taza": "Taza con cara", "moneda": "Moneda con cara",
          "bombilla": "Bombilla con cara"}
MATERIALES = {"barro": "Barro (stop-motion)", "plastico": "Plastico brillante", "vinilo": "Vinilo de juguete", "peluche": "Peluche"}
ACCESORIOS = {"": "Ninguno", "gorro": "Gorro", "gafas": "Gafas", "pajarita": "Pajarita", "corona": "Corona"}
ESCENARIOS = {"mesa": "Mesa de trabajo", "cuarto": "Cuarto", "exterior": "Exterior"}
CAMARAS = ("general", "medio", "primer", "contrapicado")
GESTOS = {"habla": "habla moviendo las manos (lo normal)", "saluda": "saluda con la mano", "salta": "da un salto",
          "senala": "senala a un lado (hacia un objeto)", "piensa": "se lleva la mano a la cara, pensando",
          "sorprendido": "salta hacia atras de sorpresa", "triste": "se encoge, triste", "baila": "baila de alegria",
          "camina": "entra caminando", "celebra": "salta dos veces con los brazos arriba"}
CARAS = ("normal", "feliz", "triste", "enojado", "sorprendido", "mareado", "guino", "pensando", "dormido")
OBJETOS = ("cartel", "libro", "caja", "moneda", "planta", "taza", "grafico")
FISICAS = {"lluvia": "caen muchos y se amontonan (dinero que entra, cosas que sobran)",
           "derrumbe": "una torre de bloques que se viene abajo (algo que se rompe o se acaba)",
           "domino": "fichas que caen en cadena (un efecto que arrastra al siguiente)",
           "llenar": "bolas que llenan un vaso hasta un nivel (un porcentaje, algo que se llena)"}
PIEZAS = ("moneda", "billete", "cubo", "bola", "ladrillo")
CALIDADES = {"borrador": (0.5, 16), "final": (1.0, 32)}   # escala de la resolucion y muestras de EEVEE

PERSONAJE_DEFECTO = {"forma": "huevo", "color": "#f2b33d", "material": "barro", "accesorio": ""}


def ejecutable():
    """Ruta de blender.exe (config estudio_blender_exe, el PATH o la carpeta de instalacion normal) o None."""
    propio = str(config.app.get("estudio_blender_exe") or "")
    if propio and os.path.isfile(propio):
        return propio
    en_path = shutil.which("blender")
    if en_path:
        return en_path
    for patron in (r"C:\Program Files\Blender Foundation\Blender *\blender.exe", "/usr/bin/blender", "/opt/blender*/blender"):
        hallados = sorted(glob.glob(patron), reverse=True)
        if hallados:
            return hallados[0]
    return None


def disponible():
    """'' si se puede usar; si no, el motivo (para la interfaz)."""
    if not ejecutable():
        return "Blender no esta instalado en esta maquina (las escenas 3D solo se hacen en el PC local)"
    return ""


def personaje(p):
    """Personaje limpio (forma, color, material, accesorio)."""
    p = p if isinstance(p, dict) else {}
    color = str(p.get("color") or "")
    return {"forma": p.get("forma") if p.get("forma") in FORMAS else PERSONAJE_DEFECTO["forma"],
            "color": color if len(color) == 7 and color.startswith("#") else PERSONAJE_DEFECTO["color"],
            "material": p.get("material") if p.get("material") in MATERIALES else PERSONAJE_DEFECTO["material"],
            "accesorio": p.get("accesorio") if p.get("accesorio") in ACCESORIOS else ""}


def catalogo():
    return {"disponible": not disponible(), "falta": disponible(),
            "formas": [{"id": k, "nombre": v} for k, v in FORMAS.items()],
            "materiales": [{"id": k, "nombre": v} for k, v in MATERIALES.items()],
            "accesorios": [{"id": k, "nombre": v} for k, v in ACCESORIOS.items()],
            "escenarios": [{"id": k, "nombre": v} for k, v in ESCENARIOS.items()],
            "calidades": [{"id": "borrador", "nombre": "Borrador (rapido)"}, {"id": "final", "nombre": "Final (lento)"}],
            "personaje": PERSONAJE_DEFECTO}


def _huella_kit():
    h = hashlib.sha1()
    for nombre in sorted(os.listdir(DIR_KIT)):
        if nombre.endswith(".py"):
            with open(os.path.join(DIR_KIT, nombre), "rb") as f:
                h.update(nombre.encode() + f.read())
    return h.hexdigest()[:10]


def _boca24(boca30, duracion):
    """La boca de la Fabrica (30 fps) pasada a los fotogramas del kit (24 fps)."""
    if not boca30:
        return ""
    n = max(2, round(duracion * FPS_KIT))
    return "".join(boca30[min(len(boca30) - 1, round(k * 30 / FPS_KIT))] for k in range(n))


def plano(datos, duracion, ancho, alto, destino_dir, opciones, fps_salida=30, avisar=lambda m: None):
    """Clip mp4 (sin audio, ancho x alto, fps_salida) de un plano. datos = lo que plan() deja en escena['datos']['barro']
    (el muneco, kit.py) o en ['tres_d'] con "script" (otra escena 3D: tamanos.py...)."""
    exe = ejecutable()
    if not exe:
        raise RuntimeError(disponible())
    escala, muestras = CALIDADES.get(opciones.get("calidad") or "borrador", CALIDADES["borrador"])
    # Blender renderiza a la escala de la calidad (multiplo de 2) y ffmpeg lo lleva al tamano del video
    w, h = int(ancho * escala) // 2 * 2, int(alto * escala) // 2 * 2
    script = datos.get("script") or "kit"
    if script == "tamanos":
        # los modelos de Poly Haven se bajan ahora (la primera vez) y Blender los lee del disco
        p = {"objetos": [{**o, "ruta": modelos3d.ruta(o["modelo"])} for o in datos["objetos"]],
             "duracion": round(duracion, 3), "ancho": w, "alto": h, "fps": FPS_KIT, "paso": 1,
             "muestras": max(8, muestras // 2), "semilla": int(datos.get("semilla") or 7)}
        return _render(exe, "tamanos.py", p, duracion, ancho, alto, destino_dir, fps_salida, avisar)
    if script == "datos3d":
        p = {"modo": datos.get("modo") or "columnas", "datos": datos["datos"], "duracion": round(duracion, 3), "ancho": w,
             "alto": h, "fps": FPS_KIT, "paso": 1, "muestras": max(8, muestras // 2)}
        return _render(exe, "datos3d.py", p, duracion, ancho, alto, destino_dir, fps_salida, avisar)
    if script == "globo":
        paradas = datos["paradas"]
        p = {"paradas": paradas, "textura": _textura_globo([x["iso"] for x in paradas]), "duracion": round(duracion, 3),
             "ancho": w, "alto": h, "fps": FPS_KIT, "paso": 1, "muestras": max(8, muestras // 2),
             "semilla": int(datos.get("semilla") or 7)}
        return _render(exe, "globo.py", p, duracion, ancho, alto, destino_dir, fps_salida, avisar)
    if script == "objeto":
        p = {k: datos.get(k) for k in ("texto", "ambiente", "color", "a")}
        p.update(ruta=modelos3d.ruta(datos["modelo"]), duracion=round(duracion, 3), ancho=w, alto=h, fps=FPS_KIT, paso=1,
                 muestras=max(8, muestras // 2))
        return _render(exe, "objeto.py", p, duracion, ancho, alto, destino_dir, fps_salida, avisar)
    if script == "diorama":
        p = {k: datos.get(k) for k in ("tema", "hora", "texto", "a", "bucle")}
        p.update(duracion=round(duracion, 3), ancho=w, alto=h, fps=FPS_KIT, paso=1, muestras=max(8, muestras // 2),
                 semilla=int(datos.get("semilla") or 7))
        return _render(exe, "diorama.py", p, duracion, ancho, alto, destino_dir, fps_salida, avisar)
    if script == "titulo3d":
        p = {"texto": datos.get("texto") or "", "ambiente": datos.get("ambiente") or "claro", "a": datos.get("a") or 0,
             "duracion": round(duracion, 3), "ancho": w, "alto": h, "fps": FPS_KIT, "paso": 1, "muestras": max(8, muestras // 2)}
        return _render(exe, "titulo3d.py", p, duracion, ancho, alto, destino_dir, fps_salida, avisar)
    if script == "fisicas":
        p = {k: datos.get(k) for k in ("tipo", "objeto", "cantidad", "nivel", "texto", "a")}
        p.update(duracion=round(duracion, 3), ancho=w, alto=h, fps=FPS_KIT, paso=1, muestras=max(8, muestras // 2),
                 semilla=int(datos.get("semilla") or 7))
        return _render(exe, "fisicas.py", p, duracion, ancho, alto, destino_dir, fps_salida, avisar)
    p = {"personaje": personaje(opciones.get("personaje")), "escenario": opciones.get("escenario") if opciones.get("escenario") in ESCENARIOS else "mesa",
         "camara": datos.get("camara") if datos.get("camara") in CAMARAS else "medio",
         "gesto": datos.get("gesto") if datos.get("gesto") in GESTOS else "habla",
         "cara": datos.get("cara") if datos.get("cara") in CARAS else "normal",
         "objetos": [o for o in (datos.get("objetos") or [])[:2] if isinstance(o, dict) and o.get("tipo") in OBJETOS],
         "boca": _boca24(datos.get("boca") or "", duracion), "duracion": round(duracion, 3),
         "ancho": w, "alto": h, "fps": FPS_KIT, "muestras": muestras, "semilla": int(datos.get("semilla") or 7), "paso": 2}
    return _render(exe, "kit.py", p, duracion, ancho, alto, destino_dir, fps_salida, avisar)


COLORES_GLOBO = {"mar": (42, 111, 201), "tierra": (124, 192, 106), "borde": (79, 138, 69),
                 "destacados": [((242, 179, 61), (184, 128, 26)), ((232, 53, 43), (150, 30, 25)),
                                ((155, 89, 214), (100, 50, 150)), ((255, 255, 255), (150, 150, 150))]}


def _textura_globo(destacados):
    """PNG equirectangular (4096x2048) con los paises de Natural Earth; los de las paradas, cada uno de su color.
    El alfa es 255 en el mar (globo.py lo usa para que el agua brille y la tierra sea mate). Cacheado."""
    from PIL import Image, ImageDraw

    clave = hashlib.sha1(json.dumps([destacados, COLORES_GLOBO]).encode()).hexdigest()[:12]
    dir_tex = os.path.join(modelos3d.DIR, "_globo")
    os.makedirs(dir_tex, exist_ok=True)
    ruta = os.path.join(dir_tex, f"tierra_{clave}.png")
    if os.path.isfile(ruta):
        return ruta
    if not hasattr(_textura_globo, "paises"):
        with open(os.path.join(graficos.DIR_MOTION, "fabrica", "datos", "paises.js"), encoding="utf-8") as f:
            crudo = f.read()
        _textura_globo.paises = json.loads(crudo[crudo.index("{"):crudo.rindex("}") + 1])
    W, H = 8192, 4096   # se pinta al doble y se reduce (bordes suaves)
    color = Image.new("RGB", (W, H), COLORES_GLOBO["mar"])
    alfa = Image.new("L", (W, H), 255)
    dc, da = ImageDraw.Draw(color), ImageDraw.Draw(alfa)
    xy = lambda anillo: [((lon + 180) / 360 * W, (90 - lat) / 180 * H) for lon, lat in anillo]
    tonos = {iso: COLORES_GLOBO["destacados"][k % 4] for k, iso in enumerate(dict.fromkeys(destacados))}
    # los resaltados al final: que no los pise el borde de un vecino
    for iso, pais in sorted(_textura_globo.paises.items(), key=lambda kv: kv[0] in tonos):
        relleno, borde = tonos.get(iso, (COLORES_GLOBO["tierra"], COLORES_GLOBO["borde"]))
        for anillo in pais["r"]:
            if len(anillo) >= 3:
                dc.polygon(xy(anillo), fill=relleno, outline=borde, width=5 if iso in tonos else 3)
                da.polygon(xy(anillo), fill=0)
    # se reducen por separado (con el alfa junto PIL premultiplica y la tierra, alfa 0, saldria negra)
    color = color.resize((W // 2, H // 2), Image.LANCZOS)
    color.putalpha(alfa.resize((W // 2, H // 2), Image.LANCZOS))
    color.save(ruta + ".tmp.png")
    os.replace(ruta + ".tmp.png", ruta)
    return ruta


def _render(exe, script, p, duracion, ancho, alto, destino_dir, fps_salida, avisar):
    """Corre un guion de Blender (motion/blender/<script>) con su JSON y junta sus PNG en un clip (cacheado)."""
    paso = int(p.get("paso", 2))
    huella = hashlib.sha1(json.dumps([_huella_kit(), script, p, ancho, alto, fps_salida], sort_keys=True).encode()).hexdigest()[:16]
    os.makedirs(destino_dir, exist_ok=True)
    final = os.path.join(destino_dir, f"{huella}.mp4")
    if os.path.isfile(final):
        return final
    with _ocupado:
        if os.path.isfile(final):
            return final
        tmp = tempfile.mkdtemp(prefix="plano_", dir=destino_dir)
        try:
            p["salida"] = os.path.join(tmp, "poses")
            ruta_json = os.path.join(tmp, "plano.json")
            with open(ruta_json, "w", encoding="utf-8") as f:
                json.dump(p, f, ensure_ascii=False)
            poses = max(1, (round(duracion * FPS_KIT) + paso - 1) // paso)
            proc = subprocess.Popen([exe, "-b", "--factory-startup", "-P", os.path.join(DIR_KIT, script), "--", ruta_json],
                                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace")
            cola, listo = [], False
            for linea in proc.stdout:
                cola = (cola + [linea])[-40:]
                listo = listo or linea.startswith("LISTO")
                if linea.startswith("POSE"):
                    hechas = len([n for n in os.listdir(p["salida"]) if n.endswith(".png")]) if os.path.isdir(p["salida"]) else 0
                    avisar(f"pose {hechas} de {poses}")
            proc.wait(timeout=7200)
            pngs = sorted(glob.glob(os.path.join(p["salida"], "f_*.png")))
            # vale si dijo LISTO aunque luego se cayera al cerrarse (las poses ya estan guardadas)
            if not pngs or (proc.returncode != 0 and not listo):
                raise RuntimeError("Blender no pudo renderizar el plano: " + "".join(cola)[-600:])
            # numeradas seguidas para ffmpeg (en doses Blender deja solo los fotogramas impares)
            for k, ruta in enumerate(pngs):
                os.replace(ruta, os.path.join(p["salida"], f"s_{k:05d}.png"))
            salida = os.path.join(tmp, "plano.mp4")
            r = medios.correr([medios.ffmpeg(), "-hide_banner", "-loglevel", "error", "-y", "-framerate", str(FPS_KIT / paso),
                               "-i", os.path.join(p["salida"], "s_%05d.png"),
                               "-vf", f"scale={ancho}:{alto}:flags=lanczos,fps={fps_salida},format=yuv420p",
                               "-t", str(duracion), "-c:v", "libx264", "-preset", "veryfast", "-crf", "17", salida], timeout=900)
            if r.returncode != 0 or not os.path.isfile(salida):
                raise RuntimeError(f"no se pudo juntar el plano: {r.stderr[-300:]}")
            os.replace(salida, final)
            logger.info(f"blender: {script} {huella} ({poses} poses, {p['ancho']}x{p['alto']})")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
    return final
