"""Escena 3D TITULO: el gancho en letras gruesas de 3D que caen una a una, rebotan y se quedan delante de un
fondo de estudio; la palabra clave (entre *asteriscos*) en el color de acento. Para abrir el video.

Uso:  blender -b --factory-startup -P titulo3d.py -- plano.json
plano.json = {"salida", "ancho", "alto", "fps", "muestras", "duracion", "paso": 1, "texto": "El *Everest* no es el mas alto",
              "ambiente": claro|oscuro|color, "color"?: "#hex" (acento), "a"?: segundo en que empiezan a caer}
"""
import json
import math
import os
import sys

import bpy
from mathutils import Vector

AQUI = os.path.dirname(os.path.abspath(__file__))
P = json.load(open(sys.argv[sys.argv.index("--") + 1], encoding="utf-8"))
FPS = int(P.get("fps", 24))
FIN = max(2, round(P["duracion"] * FPS))
PASO = int(P.get("paso", 1))
os.makedirs(P["salida"], exist_ok=True)
f = lambda s: max(1, min(FIN, round(1 + s * FPS)))
A = max(0.0, float(P.get("a", 0.0)))

AMBIENTES = {   # fondo, letras, acento
    "claro": ("#e3d8c6", "#1e1c1a", "#e8352b"),
    "oscuro": ("#15161b", "#f4f1ec", "#f2b33d"),
    "color": ("#ffcf5a", "#1e1c1a", "#2f5fd0"),
}
fondo, tinta, acento = AMBIENTES.get(P.get("ambiente"), AMBIENTES["claro"])
if isinstance(P.get("color"), str) and len(P["color"]) == 7:
    acento = P["color"]

bpy.ops.wm.read_factory_settings(use_empty=True)
escena = bpy.context.scene
escena.frame_start, escena.frame_end, escena.render.fps = 1, FIN, FPS


def hexa(h, a=1.0):
    h = h.lstrip("#")
    c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return [x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c] + [a]


def material(nombre, col, rugosidad=0.4, barniz=0.4):
    m = bpy.data.materials.new(nombre)
    m.use_nodes = True
    p = m.node_tree.nodes["Principled BSDF"]
    p.inputs["Base Color"].default_value = hexa(col)
    p.inputs["Roughness"].default_value = rugosidad
    p.inputs["Coat Weight"].default_value = barniz
    return m


# ------------------------------------------------------------------ fondo: pared con suelo en curva (sin esquina)
verts, caras = [], []
perfil = [(-8.0, 0.0), (0.0, 0.0)] + [(1.5 * math.sin(k / 10 * math.pi / 2), 1.5 - 1.5 * math.cos(k / 10 * math.pi / 2)) for k in range(1, 11)] + [(1.5, 12.0)]
for x in (-15.0, 15.0):
    for y, z in perfil:
        verts.append((x, y + 0.6, z - 1.6))
m = len(perfil)
caras = [(i, i + 1, m + i + 1, m + i) for i in range(m - 1)]
malla = bpy.data.meshes.new("fondo")
malla.from_pydata(verts, [], caras)
fo = bpy.data.objects.new("fondo", malla)
escena.collection.objects.link(fo)
for pol in malla.polygons:
    pol.use_smooth = True
fo.data.materials.append(material("fondo", fondo, 0.95, barniz=0))

# ------------------------------------------------------------------ las letras, una a una, en lineas
fuente = os.path.join(AQUI, "..", "fabrica", "fuentes", "Anton.ttf")
letra = bpy.data.fonts.load(fuente) if os.path.isfile(fuente) else None
mat_t, mat_a = material("tinta", tinta), material("acento", acento, 0.3)
vertical = P["alto"] > P["ancho"]
ANCHO_MAX = 2.85 if vertical else 4.6   # ancho de una linea (en metros de la escena)

# palabras con su marca de clave
palabras, clave = [], False
for trozo in str(P.get("texto") or "").replace("*", " * ").split():
    if trozo == "*":
        clave = not clave
        continue
    palabras.append((trozo.upper(), clave))


def hacer(ch, mat):
    cu = bpy.data.curves.new("l", "FONT")
    cu.body, cu.size, cu.extrude, cu.align_x, cu.align_y = ch, 1.0, 0.12, "LEFT", "BOTTOM_BASELINE"
    cu.bevel_depth, cu.bevel_resolution = 0.012, 2
    if letra:
        cu.font = letra
    o = bpy.data.objects.new("l", cu)
    escena.collection.objects.link(o)
    o.rotation_euler = (math.radians(90), 0, 0)
    o.data.materials.append(mat)
    return o


# cada palabra se monta con sus letras y se mide; luego se reparten en lineas y se escala todo para que quepa
ESPACIO, HUECO = 0.3, 0.075   # el bisel engorda cada letra: hace falta aire entre ellas
pals = []
for txt, es_clave in palabras[:12]:
    letras, x = [], 0.0
    for ch in txt:
        o = hacer(ch, mat_a if es_clave else mat_t)
        bpy.context.view_layer.update()
        letras.append((o, x))
        x += o.dimensions.x + HUECO
    pals.append({"letras": letras, "ancho": x - HUECO, "clave": es_clave})
lineas, actual, ancho = [], [], 0.0
for p in pals:
    if actual and ancho + ESPACIO + p["ancho"] > ANCHO_MAX * 1.6:
        lineas.append((actual, ancho))
        actual, ancho = [], 0.0
    ancho += (ESPACIO if actual else 0) + p["ancho"]
    actual.append(p)
if actual:
    lineas.append((actual, ancho))
escala = min(ANCHO_MAX / max(a for _, a in lineas), 0.9)
ALTO_L = 1.25 * escala
alto_total = ALTO_L * len(lineas)
orden = []
for k, (ps, ancho) in enumerate(lineas):
    x0 = -ancho * escala / 2
    z = alto_total / 2 - ALTO_L * (k + 0.8)
    for p in ps:
        for o, dx in p["letras"]:
            o.scale = (escala, escala, escala)
            o.location = (x0 + dx * escala, 0, z)
            orden.append((o, p["clave"]))
        x0 += (p["ancho"] + ESPACIO) * escala

# caen una a una desde arriba girando, rebotan y se asientan; la clave cae la ultima de su palabra y mas fuerte
ritmo = min(0.045, 0.7 / max(1, len(orden)))   # el gancho tiene que leerse enseguida
for k, (o, es_clave) in enumerate(orden):
    t = A + k * ritmo
    final_loc, final_rot, s = o.location.copy(), o.rotation_euler.copy(), o.scale.x
    o.location = final_loc + Vector((0, -0.4, 7.0))   # fuera del cuadro
    o.rotation_euler = (final_rot.x + 0.9, 0, 0.5 if k % 2 else -0.5)
    o.scale = (s, s, s)
    for prop in ("location", "rotation_euler", "scale"):
        o.keyframe_insert(prop, frame=1)
        o.keyframe_insert(prop, frame=f(t))
    o.location, o.rotation_euler = final_loc, final_rot
    o.scale = (s * 1.15, s * 1.15, s * 0.75)   # se aplasta al tocar
    for prop in ("location", "rotation_euler", "scale"):
        o.keyframe_insert(prop, frame=f(t + 0.22))
    o.location = final_loc + Vector((0, 0, 0.12 * (1.6 if es_clave else 1)))
    o.scale = (s * 0.95, s * 0.95, s * 1.08)
    o.keyframe_insert("location", frame=f(t + 0.34))
    o.keyframe_insert("scale", frame=f(t + 0.34))
    o.location, o.scale = final_loc, (s, s, s)
    o.keyframe_insert("location", frame=f(t + 0.46))
    o.keyframe_insert("scale", frame=f(t + 0.46))
fin_caida = A + len(orden) * ritmo + 0.5
# la clave late una vez cuando ya han caido todas
for o, es_clave in orden:
    if es_clave:
        s = o.scale.x
        o.keyframe_insert("scale", frame=f(fin_caida))
        o.scale = (s * 1.12, s * 1.12, s * 1.12)
        o.keyframe_insert("scale", frame=f(fin_caida + 0.15))
        o.scale = (s, s, s)
        o.keyframe_insert("scale", frame=f(fin_caida + 0.35))

# ------------------------------------------------------------------ luces y camara (se acerca despacio y gira un poco)
mundo = bpy.data.worlds.new("mundo")
escena.world = mundo
mundo.use_nodes = True
mundo.node_tree.nodes["Background"].inputs["Color"].default_value = hexa(fondo)
mundo.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.25
centro = Vector((0, 0, 0.0))


def area(nombre, pos, energia, tam):
    d = bpy.data.lights.new(nombre, "AREA")
    d.energy, d.size = energia, tam
    o = bpy.data.objects.new(nombre, d)
    escena.collection.objects.link(o)
    o.location = pos
    o.rotation_euler = (centro - Vector(pos)).to_track_quat("-Z", "Y").to_euler()


area("clave", (-3.0, -4.0, 4.0), 260, 3.0)
area("relleno", (3.5, -3.0, 0.5), 80, 4.0)
area("contra", (0.0, 1.5, 4.0), 150, 2.0)
cam_d = bpy.data.cameras.new("cam")
cam_d.lens = 50
cam_d.sensor_fit = "HORIZONTAL"
cam = bpy.data.objects.new("cam", cam_d)
escena.collection.objects.link(cam)
escena.camera = cam
diana = bpy.data.objects.new("diana", None)
escena.collection.objects.link(diana)
diana.location = (0, 0, 0.1)
pista = cam.constraints.new("TRACK_TO")
pista.target, pista.track_axis, pista.up_axis = diana, "TRACK_NEGATIVE_Z", "UP_Y"
media = math.atan(cam_d.sensor_width / 2 / cam_d.lens)
d = (ANCHO_MAX / 2 + 0.25) / math.tan(media)
for fr, x, dd in ((1, -0.5, d * 1.06), (FIN, 0.35, d * 0.97)):
    cam.location = (x, -dd, 0.5)
    cam.keyframe_insert("location", frame=fr)

# ------------------------------------------------------------------ render
r = escena.render
for motor in ("BLENDER_EEVEE", "BLENDER_EEVEE_NEXT"):
    try:
        r.engine = motor
        break
    except TypeError:
        pass
escena.eevee.taa_render_samples = int(P.get("muestras", 16))
r.resolution_x, r.resolution_y, r.resolution_percentage = P["ancho"], P["alto"], 100
r.image_settings.file_format = "PNG"
escena.view_settings.view_transform = "Standard"
# EEVEE saca el segundo render de la sesion sin luz (todo marron): dos renders de calentamiento que no se guardan
for _ in range(2):
    escena.frame_set(1)
    bpy.ops.render.render(write_still=False)
for fr in range(1, FIN + 1, PASO):
    escena.frame_set(fr)
    r.filepath = os.path.join(P["salida"], f"f_{fr:04d}.png")
    bpy.ops.render.render(write_still=True)
    print("POSE", fr, FIN, flush=True)
print("LISTO", flush=True)
sys.stdout.flush()
os._exit(0)
