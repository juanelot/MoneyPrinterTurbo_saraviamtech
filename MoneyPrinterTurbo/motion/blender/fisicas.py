"""Escena 3D FISICAS: lo "oddly satisfying" con el simulador de cuerpos rigidos de Blender.
  lluvia:   N objetos (monedas, cubos, bolas, billetes) caen y se amontonan
  derrumbe: una torre de bloques que se viene abajo cuando algo la golpea
  domino:   una fila de fichas que caen en cadena
  llenar:   bolas que llenan un vaso de cristal hasta un nivel (un porcentaje)
Uso: blender -b --factory-startup -P fisicas.py -- plano.json
plano.json = {"salida", "ancho", "alto", "fps", "muestras", "duracion", "paso": 1, "tipo": lluvia|derrumbe|domino|llenar,
              "objeto": moneda|cubo|bola|billete|ladrillo, "cantidad": n, "nivel": 0-1 (llenar), "color"?: "#hex",
              "a": segundo en que empieza, "texto"?: rotulo 3D (una cifra corta), "fondo"?: "#hex", "semilla"?}
La simulacion avanza al pasar los fotogramas en orden (se renderizan todos del 1 al final).
"""
import json
import math
import os
import random
import sys

import bpy
from mathutils import Vector

AQUI = os.path.dirname(os.path.abspath(__file__))
P = json.load(open(sys.argv[sys.argv.index("--") + 1], encoding="utf-8"))
FPS = int(P.get("fps", 24))
FIN = max(2, round(P["duracion"] * FPS))
os.makedirs(P["salida"], exist_ok=True)
azar = random.Random(P.get("semilla", 7))
TIPO = P.get("tipo", "lluvia")
OBJETO = P.get("objeto", "moneda")
A = max(0.0, float(P.get("a", 0.3)))

bpy.ops.wm.read_factory_settings(use_empty=True)
escena = bpy.context.scene
escena.frame_start, escena.frame_end, escena.render.fps = 1, FIN, FPS


def hexa(h, a=1.0):
    h = h.lstrip("#")
    c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return [x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c] + [a]


def material(nombre, color, rugosidad=0.4, metal=0.0, cristal=False):
    m = bpy.data.materials.new(nombre)
    m.use_nodes = True
    p = m.node_tree.nodes["Principled BSDF"]
    p.inputs["Base Color"].default_value = hexa(color)
    p.inputs["Roughness"].default_value = rugosidad
    p.inputs["Metallic"].default_value = metal
    if cristal:
        p.inputs["Transmission Weight"].default_value = 1.0
        p.inputs["IOR"].default_value = 1.45
        p.inputs["Alpha"].default_value = 0.35
        m.surface_render_method = "BLENDED" if hasattr(m, "surface_render_method") else m.surface_render_method
    return m


COLORES = ["#d7372c", "#4f8fcb", "#e0a92e", "#3f7d4e", "#6a4f8a", "#e2775a"]
MATS = {}


def mat_objeto(k):
    if OBJETO == "moneda":
        clave = "oro"
        if clave not in MATS:
            MATS[clave] = material("oro", "#e9b949", rugosidad=0.25, metal=1.0)
    elif OBJETO == "billete":
        clave = "billete"
        if clave not in MATS:
            MATS[clave] = material("billete", "#7fb27a", rugosidad=0.7)
    else:
        color = P.get("color") or COLORES[k % len(COLORES)]
        clave = color
        if clave not in MATS:
            MATS[clave] = material(f"m{len(MATS)}", color, rugosidad=0.3)
    return MATS[clave]


def solido(o, tipo="ACTIVE", forma="CONVEX_HULL", masa=1.0, rebote=0.2, roce=0.6):
    bpy.context.view_layer.objects.active = o
    o.select_set(True)
    bpy.ops.rigidbody.object_add()
    rb = o.rigid_body
    rb.type, rb.collision_shape, rb.mass, rb.restitution, rb.friction = tipo, forma, masa, rebote, roce
    rb.collision_margin = 0.002
    rb.linear_damping, rb.angular_damping = 0.15, 0.3
    o.select_set(False)
    return rb


def pieza(pos, k, rot=None):
    """Un objeto del tipo pedido (tamano ~0.1-0.2 m)."""
    if OBJETO == "moneda":
        bpy.ops.mesh.primitive_cylinder_add(vertices=24, radius=0.05, depth=0.008, location=pos)
        forma = "CYLINDER"
    elif OBJETO == "billete":
        bpy.ops.mesh.primitive_cube_add(size=1, location=pos)
        bpy.context.object.scale = (0.156 / 1, 0.066 / 1, 0.002)
        forma = "BOX"
    elif OBJETO == "bola":
        bpy.ops.mesh.primitive_uv_sphere_add(segments=20, ring_count=10, radius=0.05, location=pos)
        forma = "SPHERE"
    elif OBJETO == "ladrillo":
        bpy.ops.mesh.primitive_cube_add(size=1, location=pos)
        bpy.context.object.scale = (0.2, 0.1, 0.06)
        forma = "BOX"
    else:
        bpy.ops.mesh.primitive_cube_add(size=1, location=pos)
        bpy.context.object.scale = (0.08, 0.08, 0.08)
        forma = "BOX"
    o = bpy.context.object
    o.rotation_euler = rot if rot is not None else (azar.uniform(0, 3.14), azar.uniform(0, 3.14), azar.uniform(0, 3.14))
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    if OBJETO in ("cubo", "ladrillo"):
        b = o.modifiers.new("bisel", "BEVEL")
        b.width, b.segments = 0.006, 2
    for pol in o.data.polygons:
        pol.use_smooth = OBJETO in ("bola", "moneda")
    o.data.materials.append(mat_objeto(k))
    return o, forma


def rejilla(k, lado, paso, z0):
    """Sitio de la pieza k en capas de lado x lado sin tocarse (si empiezan solapadas el simulador las dispara)."""
    i, capa = k % (lado * lado), k // (lado * lado)
    j = lambda: azar.uniform(-paso * 0.15, paso * 0.15)
    return ((i % lado - (lado - 1) / 2) * paso + j(), (i // lado - (lado - 1) / 2) * paso + j(), z0 + capa * paso)


# ------------------------------------------------------------------ mundo de fisicas y suelo
bpy.ops.rigidbody.world_add()
mundo_rb = escena.rigidbody_world
mundo_rb.substeps_per_frame, mundo_rb.solver_iterations = 20, 20
mundo_rb.point_cache.frame_start, mundo_rb.point_cache.frame_end = 1, FIN
# una losa con grosor (con un plano sin grosor las piezas lo atraviesan) con la cara de arriba en z = 0
bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, -0.1))
suelo = bpy.context.object
suelo.scale = (30, 30, 0.2)
bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
suelo.data.materials.append(material("suelo", P.get("suelo", "#d6cdbd"), rugosidad=0.85))
solido(suelo, "PASSIVE", "BOX")

n = max(3, min(int(P.get("cantidad") or 60), 220))
f_inicio = max(1, round(1 + A * FPS))
mira = Vector((0, 0, 0.25))
dist = 1.6

if TIPO == "lluvia":
    # caen de una nube invisible por tandas a partir de A: se van apilando en el centro
    for k in range(n):
        o, forma = pieza(rejilla(k, 4, 0.13, 0.6), k)
        solido(o, forma=forma, masa=0.1, rebote=0.02, roce=0.95)
        # quietos (animados) hasta su turno: asi empiezan a caer cuando se dice la palabra
        o.rigid_body.kinematic = True
        o.keyframe_insert("rigid_body.kinematic", frame=1)
        o.rigid_body.kinematic = False
        o.keyframe_insert("rigid_body.kinematic", frame=f_inicio + (k // 16) * 3)   # por capas
    mira, dist = Vector((0, 0, 0.18)), 1.25
elif TIPO == "derrumbe":
    pisos = max(4, min(n // 3, 18))
    for pi in range(pisos):
        for j in range(3):
            girar = pi % 2
            pos = (0 if girar else (j - 1) * 0.1, (j - 1) * 0.1 if girar else 0, 0.03 + pi * 0.061)
            bpy.ops.mesh.primitive_cube_add(size=1, location=pos)
            b = bpy.context.object
            b.scale = (0.1, 0.3, 0.06) if not girar else (0.3, 0.1, 0.06)
            bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
            b.data.materials.append(mat_objeto(pi))
            solido(b, forma="BOX", masa=0.3, roce=0.7)
    # la bola que la golpea, animada hasta tocarla y luego libre
    bpy.ops.mesh.primitive_uv_sphere_add(segments=24, ring_count=12, radius=0.12, location=(-1.2, 0, pisos * 0.03))
    bola = bpy.context.object
    bola.data.materials.append(material("bola", "#1e1c1a", rugosidad=0.2, metal=1.0))
    solido(bola, forma="SPHERE", masa=8)
    bola.rigid_body.kinematic = True
    bola.keyframe_insert("rigid_body.kinematic", frame=1)
    bola.keyframe_insert("location", frame=f_inicio)
    bola.location = (-0.05, 0, pisos * 0.03)
    bola.keyframe_insert("location", frame=f_inicio + 6)
    bola.keyframe_insert("rigid_body.kinematic", frame=f_inicio + 6)
    bola.rigid_body.kinematic = False
    bola.keyframe_insert("rigid_body.kinematic", frame=f_inicio + 7)
    mira, dist = Vector((0, 0, pisos * 0.03)), 1.0 + pisos * 0.08
elif TIPO == "domino":
    fichas = max(8, min(n, 60))
    radio = 0.9
    for k in range(fichas):
        ang = k / fichas * math.pi * 1.4 - math.pi * 0.7          # una curva: la cadena se ve mejor
        pos = (math.sin(ang) * radio, math.cos(ang) * radio * 0.6 - 0.3, 0.06)
        tx, ty = math.cos(ang), -math.sin(ang) * 0.6               # hacia donde sigue la cadena
        bpy.ops.mesh.primitive_cube_add(size=1, location=pos)
        d = bpy.context.object
        d.scale = (0.05, 0.012, 0.12)
        d.rotation_euler = (0, 0, math.atan2(ty, tx) - math.pi / 2)   # su cara (eje Y local) mira a la siguiente
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
        d.data.materials.append(mat_objeto(k))
        solido(d, forma="BOX", masa=0.05, roce=0.5)
        if k == 0:   # la primera recibe un empujon cuando toca
            d.rigid_body.kinematic = True
            d.keyframe_insert("rigid_body.kinematic", frame=1)
            d.keyframe_insert("rotation_euler", frame=f_inicio)
            d.rotation_euler.x -= 0.45   # se inclina hacia la siguiente
            d.keyframe_insert("rotation_euler", frame=f_inicio + 3)
            d.keyframe_insert("rigid_body.kinematic", frame=f_inicio + 3)
            d.rigid_body.kinematic = False
            d.keyframe_insert("rigid_body.kinematic", frame=f_inicio + 4)
    mira, dist = Vector((0, -0.1, 0.05)), 2.0
else:   # llenar: un vaso de cristal que se llena de bolas hasta el nivel pedido
    alto_v, radio_v = 0.5, 0.18
    bpy.ops.mesh.primitive_cylinder_add(vertices=32, radius=radio_v, depth=alto_v, location=(0, 0, alto_v / 2))
    vaso = bpy.context.object
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="DESELECT")
    bpy.ops.object.mode_set(mode="OBJECT")
    for pol in vaso.data.polygons:   # sin tapa de arriba
        pol.select = pol.normal.z > 0.9
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.delete(type="FACE")
    bpy.ops.object.mode_set(mode="OBJECT")
    vaso.modifiers.new("grosor", "SOLIDIFY").thickness = 0.008
    vaso.data.materials.append(material("cristal", "#dff1ff", rugosidad=0.05, cristal=True))
    solido(vaso, "PASSIVE", "MESH")
    nivel = max(0.05, min(1.0, float(P.get("nivel") or 0.7)))
    cabe = int(math.pi * (radio_v * 0.9) ** 2 * alto_v * nivel / (0.08 ** 3 * 0.55))   # bolas de 8 cm, empaquetado ~55 %
    for k in range(max(3, min(cabe, 200))):
        o, forma = pieza(rejilla(k, 2, 0.095, alto_v + 0.12), k)
        o.scale = (0.8, 0.8, 0.8)
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
        solido(o, forma="SPHERE" if OBJETO == "bola" else forma, masa=0.05, rebote=0.05, roce=0.4)
        o.rigid_body.kinematic = True
        o.keyframe_insert("rigid_body.kinematic", frame=1)
        o.rigid_body.kinematic = False
        o.keyframe_insert("rigid_body.kinematic", frame=f_inicio + (k // 4) * 2)
    mira, dist = Vector((0, 0, alto_v / 2)), 1.6

# rotulo 3D (una cifra) detras, grande
if P.get("texto"):
    cu = bpy.data.curves.new("rotulo", "FONT")
    cu.body, cu.size, cu.extrude, cu.align_x, cu.align_y = str(P["texto"]).upper()[:14], dist * 0.22, 0.02, "CENTER", "CENTER"
    fuente = os.path.join(AQUI, "..", "fabrica", "fuentes", "Anton.ttf")
    if os.path.isfile(fuente):
        cu.font = bpy.data.fonts.load(fuente)
    t = bpy.data.objects.new("rotulo", cu)
    escena.collection.objects.link(t)
    t.location = (0, dist * 0.9, mira.z + dist * 0.35)
    t.rotation_euler = (math.radians(90), 0, 0)
    t.data.materials.append(material("letra", "#1e1c1a", rugosidad=0.6))

# ------------------------------------------------------------------ luz y camara (orbita lenta)
mundo = bpy.data.worlds.new("mundo")
escena.world = mundo
mundo.use_nodes = True
mundo.node_tree.nodes["Background"].inputs["Color"].default_value = hexa(P.get("fondo", "#f1ece3"))
mundo.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.45
for nombre, pos, energia, tam in (("clave", (-2, -2.5, 3), 220, 3), ("relleno", (2.5, -1.5, 1.5), 60, 4), ("contra", (0, 3, 2.5), 120, 2)):
    dl = bpy.data.lights.new(nombre, "AREA")
    dl.energy, dl.size = energia, tam
    lo = bpy.data.objects.new(nombre, dl)
    escena.collection.objects.link(lo)
    lo.location = pos
    lo.rotation_euler = (mira - Vector(pos)).to_track_quat("-Z", "Y").to_euler()
cam_d = bpy.data.cameras.new("cam")
cam_d.lens = 45
cam_d.dof.use_dof = True
cam_d.dof.aperture_fstop = 2.8
cam = bpy.data.objects.new("cam", cam_d)
escena.collection.objects.link(cam)
escena.camera = cam
diana = bpy.data.objects.new("diana", None)
escena.collection.objects.link(diana)
diana.location = mira
cam_d.dof.focus_object = diana
pista = cam.constraints.new("TRACK_TO")
pista.target, pista.track_axis, pista.up_axis = diana, "TRACK_NEGATIVE_Z", "UP_Y"
vertical = P["alto"] > P["ancho"]
d = dist * (1.25 if vertical else 1.0)
alto_cam = 0.95 if TIPO == "lluvia" else 0.45   # la lluvia se ve mejor desde arriba: una alfombra de monedas
for fr, ang in ((1, -0.35), (FIN, 0.15)):
    cam.location = mira + Vector((math.sin(ang) * d, -math.cos(ang) * d, d * alto_cam))
    cam.keyframe_insert("location", frame=fr)

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
PASO = int(P.get("paso", 1))
for fr in range(1, FIN + 1):
    escena.frame_set(fr)          # todos en orden: la simulacion avanza fotograma a fotograma
    if (fr - 1) % PASO == 0:
        r.filepath = os.path.join(P["salida"], f"f_{fr:04d}.png")
        bpy.ops.render.render(write_still=True)
        print("POSE", fr, FIN, flush=True)
print("LISTO", flush=True)
sys.stdout.flush()
os._exit(0)
