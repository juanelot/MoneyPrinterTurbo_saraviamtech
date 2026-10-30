"""
Graficos animados (motion graphics) para el editor: plantillas PROPIAS en HTML+GSAP
(MoneyPrinterTurbo/motion/plantillas) que HyperFrames (Apache-2.0, npm) convierte
en un WebM CON TRANSPARENCIA del tamano del video. En el editor son una capa de
video mas (render.capas: tipo "video" con `archivo` = graficos/<huella>.webm y
`grafico` = {plantilla, valores, color, posicion} para volver a editarlo).

Cada plantilla lee sus textos con window.__hyperframes.getVariables(); aqui se
ponen el tamano (__ANCHO__, __ALTO__, __TAM__) y la duracion. El resultado se
cachea por contenido: el mismo grafico no se vuelve a renderizar. Uno a la vez
(cada render abre un Chrome). Requiere Node >= 22 y `npm install` en motion/.
"""
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import threading
import time

from app.models.schema import VideoAspect
from app.services.estudio import almacen, grafo
from app.utils import utils

VERSION = 1
DIR_MOTION = os.path.join(utils.root_dir(), "motion")
CLI = os.path.join(DIR_MOTION, "node_modules", "hyperframes", "bin", "hyperframes.mjs")
GSAP = os.path.join(DIR_MOTION, "node_modules", "gsap", "dist", "gsap.min.js")
DUR_MIN, DUR_MAX = 1.5, 12.0
POSICIONES = ("arriba", "centro", "abajo")
_candado = threading.Lock()

# tam: tamano de letra base, en fraccion del lado corto del video.
PLANTILLAS = {
    "titulo": {
        "nombre": "Titulo de impacto", "dur": 3.0, "tam": 0.105, "posicion": "centro",
        "descripcion": "Las palabras entran una a una; las que van entre *asteriscos* salen en color.",
        "campos": [{"id": "texto", "etiqueta": "Texto", "defecto": "Esto lo *cambia* todo"}],
    },
    "cifra": {
        "nombre": "Cifra que cuenta", "dur": 3.5, "tam": 0.13, "posicion": "centro",
        "descripcion": "Un numero que cuenta desde 0, con su etiqueta debajo.",
        "campos": [{"id": "numero", "etiqueta": "Numero", "defecto": "1000000"},
                   {"id": "prefijo", "etiqueta": "Antes (p. ej. $)", "defecto": ""},
                   {"id": "sufijo", "etiqueta": "Despues (p. ej. %)", "defecto": ""},
                   {"id": "etiqueta", "etiqueta": "Etiqueta", "defecto": "personas"}],
    },
    "rotulo": {
        "nombre": "Rotulo inferior", "dur": 4.0, "tam": 0.07, "posicion": "abajo",
        "descripcion": "Nombre y cargo (o un dato) con una barra de color, abajo a la izquierda.",
        "campos": [{"id": "titulo", "etiqueta": "Titulo", "defecto": "Ana Garcia"},
                   {"id": "subtitulo", "etiqueta": "Subtitulo", "defecto": "Economista"}],
    },
    "suscribete": {
        "nombre": "Suscribete", "dur": 3.5, "tam": 0.065, "posicion": "abajo", "color": "#FF1E3C",
        "descripcion": "Boton con campana: entra un cursor, hace clic y pasa a Suscrito.",
        "campos": [{"id": "texto", "etiqueta": "Texto", "defecto": "Suscribete"},
                   {"id": "hecho", "etiqueta": "Tras el clic", "defecto": "Suscrito"}],
    },
    # Desde aqui, ideas sacadas de videos hechos con Opus 5.5 (awesome-opus5-5-videos), escritas desde cero.
    "frase": {
        "nombre": "Frase cinetica", "dur": 3.5, "tam": 0.16, "posicion": "centro",
        "descripcion": "Una palabra cada vez, enorme y con golpes; con / agrupas palabras y con *asteriscos* van en color.",
        "campos": [{"id": "texto", "etiqueta": "Frase", "defecto": "Nadie / te lo va / a *contar*"}],
    },
    "barras": {
        "nombre": "Comparar en barras", "dur": 5.0, "tam": 0.055, "posicion": "centro",
        "descripcion": "Barras que crecen y cuentan; la mayor sale en color. Una fila por renglon: «Etiqueta: valor».",
        "campos": [{"id": "titulo", "etiqueta": "Titulo (opcional)", "defecto": "Horas al dia en el movil"},
                   {"id": "datos", "etiqueta": "Datos (Etiqueta: valor)", "defecto": "España: 3,8\nMéxico: 5,2\nArgentina: 5", "lineas": True},
                   {"id": "sufijo", "etiqueta": "Despues del numero", "defecto": " h"}],
    },
    "porcentaje": {
        "nombre": "Anillo de porcentaje", "dur": 3.5, "tam": 0.075, "posicion": "centro", "color": "#3DD6F5",
        "descripcion": "Un anillo se llena hasta el % mientras el numero cuenta.",
        "campos": [{"id": "porcentaje", "etiqueta": "Porcentaje", "defecto": "73"},
                   {"id": "etiqueta", "etiqueta": "Etiqueta", "defecto": "de los jóvenes no ahorra"}],
    },
    "linea_tiempo": {
        "nombre": "Linea de tiempo", "dur": 6.0, "tam": 0.055, "posicion": "centro",
        "descripcion": "La linea se dibuja y cada hito aparece al llegar. Uno por renglon: «Fecha: hecho».",
        "campos": [{"id": "datos", "etiqueta": "Hitos (Fecha: hecho)", "defecto": "1969: Llegada a la Luna\n1989: Nace la web\n2007: El primer iPhone", "lineas": True}],
    },
    "lista": {
        "nombre": "Lista con checks", "dur": 5.0, "tam": 0.06, "posicion": "centro", "color": "#34D27B",
        "descripcion": "Cada punto se marca con un check dibujado, uno tras otro. Un punto por renglon.",
        "campos": [{"id": "titulo", "etiqueta": "Titulo (opcional)", "defecto": "Lo que necesitas"},
                   {"id": "datos", "etiqueta": "Puntos", "defecto": "Un objetivo claro\nUna hora al día\nPaciencia", "lineas": True}],
    },
    "versus": {
        "nombre": "A contra B", "dur": 4.5, "tam": 0.075, "posicion": "centro", "color": "#FF4D5E",
        "descripcion": "Dos lados entran por los costados y un VS cae en medio con un golpe.",
        "campos": [{"id": "izquierda", "etiqueta": "Lado A", "defecto": "Alquilar"},
                   {"id": "dato_izq", "etiqueta": "Dato A", "defecto": "900 al mes"},
                   {"id": "derecha", "etiqueta": "Lado B", "defecto": "Comprar"},
                   {"id": "dato_der", "etiqueta": "Dato B", "defecto": "1.200 al mes"}],
    },
    "cita": {
        "nombre": "Cita", "dur": 5.0, "tam": 0.07, "posicion": "centro",
        "descripcion": "Comillas grandes, la frase sube palabra a palabra y las *marcadas* se subrayan con rotulador.",
        "campos": [{"id": "texto", "etiqueta": "Cita", "defecto": "El dinero es un *buen sirviente* pero un mal amo"},
                   {"id": "autor", "etiqueta": "Autor", "defecto": "Francis Bacon"}],
    },
    "sello": {
        "nombre": "Sello", "dur": 2.5, "tam": 0.14, "posicion": "centro", "color": "#E8283C",
        "descripcion": "Una palabra cae como un sello de tinta (FALSO, VERDAD, MITO...).",
        "campos": [{"id": "texto", "etiqueta": "Palabra", "defecto": "Falso"},
                   {"id": "detalle", "etiqueta": "Debajo (opcional)", "defecto": ""}],
    },
    "notificacion": {
        "nombre": "Notificacion del movil", "dur": 4.0, "tam": 0.05, "posicion": "arriba", "color": "#34C759",
        "descripcion": "Un aviso como el del movil baja, vibra y se va.",
        "campos": [{"id": "app", "etiqueta": "App", "defecto": "Banco"},
                   {"id": "titulo", "etiqueta": "Titulo", "defecto": "Pago recibido"},
                   {"id": "mensaje", "etiqueta": "Mensaje", "defecto": "Has recibido 2.500 $ de Cliente"},
                   {"id": "hora", "etiqueta": "Hora", "defecto": "ahora"}],
    },
}


def catalogo():
    return [{"id": k, **{c: v for c, v in x.items() if c != "tam"}} for k, x in PLANTILLAS.items()]


def disponible():
    """'' si se puede renderizar; si no, que falta."""
    if not shutil.which("node"):
        return "falta Node.js 22 o mas nuevo"
    if not os.path.isfile(CLI) or not os.path.isfile(GSAP):
        return "falta instalar HyperFrames (npm install en MoneyPrinterTurbo/motion)"
    return ""


def renderizar(pid, plantilla, valores=None, color=None, posicion=None, duracion=None):
    """{'archivo': 'graficos/<huella>.webm', 'duracion', 'ancho', 'alto'} (en caché si ya estaba)."""
    if plantilla not in PLANTILLAS:
        raise ValueError("plantilla desconocida")
    falta = disponible()
    if falta:
        raise RuntimeError(f"graficos animados: {falta}")
    pl = PLANTILLAS[plantilla]
    proyecto = almacen.cargar(pid)
    w, h = VideoAspect(grafo.params_efectivos(proyecto, "render").get("aspecto") or "9:16").to_resolution()
    dur = round(min(DUR_MAX, max(DUR_MIN, float(duracion or pl["dur"]))), 2)
    variables = {c["id"]: str((valores or {}).get(c["id"], c["defecto"]))[:400 if c.get("lineas") else 200] for c in pl["campos"]}
    variables["color"] = color if isinstance(color, str) and color.startswith("#") and len(color) in (4, 7) else pl.get("color", "#FFD447")
    variables["posicion"] = posicion if posicion in POSICIONES else pl["posicion"]
    with open(os.path.join(DIR_MOTION, "plantillas", f"{plantilla}.html"), encoding="utf-8") as f:
        html = (f.read().replace("__ANCHO__", str(w)).replace("__ALTO__", str(h))
                .replace("__DURACION__", f"{dur:g}").replace("__TAM__", str(round(min(w, h) * pl["tam"]))))
    huella = hashlib.sha1(json.dumps([VERSION, html, variables], sort_keys=True).encode()).hexdigest()[:16]
    carpeta = almacen.dir_proyecto(pid, "graficos", crear=True)
    final = os.path.join(carpeta, f"{huella}.webm")
    salida = {"archivo": f"graficos/{huella}.webm", "duracion": dur, "ancho": w, "alto": h}
    if os.path.isfile(final):
        return salida
    with _candado:
        if os.path.isfile(final):
            return salida
        tmp = tempfile.mkdtemp(prefix="grafico_", dir=carpeta)
        try:
            with open(os.path.join(tmp, "index.html"), "w", encoding="utf-8") as f:
                f.write(html)
            shutil.copyfile(GSAP, os.path.join(tmp, "gsap.min.js"))
            with open(os.path.join(tmp, "variables.json"), "w", encoding="utf-8") as f:
                json.dump(variables, f, ensure_ascii=False)
            salida_tmp = os.path.join(tmp, "grafico.webm")
            env = {**os.environ, "HYPERFRAMES_NO_TELEMETRY": "1", "DO_NOT_TRACK": "1", "HYPERFRAMES_NO_UPDATE_CHECK": "1"}
            # HyperFrames da solo 5 s a "ffmpeg -version": con el equipo cargado falla aunque ffmpeg este bien
            for intento in range(3):
                r = subprocess.run([shutil.which("node"), CLI, "render", tmp, "-o", salida_tmp, "--format", "webm", "-w", "1",
                                    "--quiet", "--variables-file", os.path.join(tmp, "variables.json")],
                                   cwd=DIR_MOTION, env=env, capture_output=True, text=True, encoding="utf-8",
                                   errors="replace", timeout=900)
                if r.returncode == 0 or "FFmpeg cannot start" not in (r.stderr or "") + (r.stdout or ""):
                    break
                time.sleep(2)
            if r.returncode != 0 or not os.path.isfile(salida_tmp):
                raise RuntimeError(f"HyperFrames no pudo renderizar el grafico: {(r.stderr or r.stdout)[-500:]}")
            os.replace(salida_tmp, final)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
    return salida


def _ruta_ideas(pid):
    return almacen.dir_proyecto(pid, "graficos", "ideas.json")


def ideas_guardadas(pid):
    return almacen.leer_json(_ruta_ideas(pid), {}) or {}


def proponer(pid, cuantos=6, pedido=""):
    """Claude lee lo que se dice (en tiempo del video) y propone graficos: plantilla, textos y en que frase van.
    No renderiza nada: la persona elige cuales poner. {'ideas': [...]} (tambien en graficos/ideas.json)."""
    from app.services import claude_cli
    from app.services.estudio import publicar

    lineas = publicar.subtitulos_del_video(pid)
    if not lineas:
        raise ValueError("no hay frases en el video")
    cuantos = max(1, min(15, int(cuantos or 6)))
    dur = lineas[-1][1]
    proyecto = almacen.cargar(pid)
    filas = "; varias filas separadas por \\n"
    catalogo_txt = "\n".join(
        f"- {k}: {pl['descripcion']} Campos: "
        + ", ".join(f"{c['id']} ({c['etiqueta']}{filas if c.get('lineas') else ''})" for c in pl["campos"])
        for k, pl in PLANTILLAS.items())
    numeradas = "\n".join(f"[{n}] {a:.1f}s {t}" for n, (a, _b, t) in enumerate(lineas))
    prompt = (
        f"Eres motion designer de videos para redes. Este video dura {dur:.0f} s. Propon hasta {cuantos} graficos animados "
        "que se pondran ENCIMA del video, cada uno en el momento de una frase.\n"
        f"Plantillas disponibles:\n{catalogo_txt}\n\n"
        "Reglas:\n"
        "- Solo donde aporte: cifras y porcentajes (cifra, porcentaje, barras), comparaciones (versus, barras), "
        "enumeraciones (lista), fechas (linea_tiempo), una frase fuerte (frase, titulo), una cita (cita), "
        "un mito o un dato falso (sello), algo que llega al movil (notificacion), una persona que se presenta (rotulo).\n"
        "- Usa SOLO datos que se dicen en el video; no inventes numeros, fechas ni nombres.\n"
        "- Textos muy cortos (que se lean en 2 s), en el mismo idioma del video. Varia las plantillas.\n"
        "- Repartelos por todo el video, separados al menos 4 s; 'suscribete' como mucho uno, cerca del final.\n"
        + (f"- Lo que pide la persona: {str(pedido).strip()[:300]}\n" if str(pedido or "").strip() else "")
        + f"Titulo: {proyecto.get('titulo', '')}\nFrases (numero, segundo, texto):\n{numeradas[:12000]}\n"
        'Responde SOLO con una lista JSON: [{"frase": 3, "plantilla": "cifra", "valores": {"numero": "...", ...}, '
        '"motivo": "por que ayuda aqui, en pocas palabras"}]'
    )
    lista = claude_cli.extraer_json(claude_cli.ejecutar(prompt, modelo="sonnet", esfuerzo="low", tiempo_max_s=240))
    ideas, fin_anterior = [], -1.0
    candidatas = []
    for x in lista if isinstance(lista, list) else []:
        try:
            n, pl = int(x.get("frase")), PLANTILLAS.get(str(x.get("plantilla")))
        except (TypeError, ValueError, AttributeError):
            continue
        if not pl or not 0 <= n < len(lineas):
            continue
        dados = x.get("valores") if isinstance(x.get("valores"), dict) else {}
        valores = {c["id"]: str(dados.get(c["id"], "")).replace("\\n", "\n").strip()
                   for c in pl["campos"]}
        candidatas.append((lineas[n][0], str(x["plantilla"]), valores, str(x.get("motivo") or "").strip()[:200], lineas[n][2]))
    for inicio, plantilla, valores, motivo, frase in sorted(candidatas):
        pl = PLANTILLAS[plantilla]
        if inicio < fin_anterior + 0.5:
            continue  # se pisaria con el anterior
        duracion = min(pl["dur"], max(DUR_MIN, dur - inicio))
        fin_anterior = inicio + duracion
        ideas.append({"id": hashlib.sha1(f"{inicio}{plantilla}{valores}".encode()).hexdigest()[:10], "plantilla": plantilla,
                      "nombre": pl["nombre"], "valores": valores, "inicio": round(inicio, 2), "duracion": duracion,
                      "posicion": pl["posicion"], "color": pl.get("color", "#FFD447"), "motivo": motivo, "frase": frase})
        if len(ideas) >= cuantos:
            break
    if not ideas:
        raise RuntimeError("Claude no propuso graficos validos (prueba otra vez o di que buscar)")
    almacen.dir_proyecto(pid, "graficos", crear=True)
    almacen.escribir_json(_ruta_ideas(pid), {"ideas": ideas, "pedido": str(pedido or "")})
    return {"ideas": ideas}


def ruta(pid, archivo):
    """Ruta en disco de un grafico ya renderizado (o None)."""
    if not str(archivo or "").startswith("graficos/"):
        return None
    try:
        r = almacen.dentro_de(almacen.dir_proyecto(pid, "graficos"), archivo[len("graficos/"):])
    except ValueError:
        return None
    return r if os.path.isfile(r) else None
