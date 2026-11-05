"""Escena 3D DATOS: cifras que se tocan. Cada dato crece al nombrarlo, con su cifra encima y su etiqueta delante.
  columnas: bloques de plastico mate (como barras de un grafico, pero en una mesa)
  pilas:    torres de monedas de oro (para dinero: se apilan moneda a moneda)
Uso: blender -b --factory-startup -P datos3d.py -- plano.json
plano.json = {"salida", "ancho", "alto", "fps", "muestras", "duracion", "paso": 1, "modo": columnas|pilas,
              "datos": [{"etiqueta": "Japon", "valor": 255, "texto": "255 %", "color"?: "#hex", "a": segundo}],
              "fondo"?: "#hex", "semilla"?}
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
os.makedirs(P["salida"], exist_ok=True)
MODO = P.get("modo", "columnas")
DATOS = P["datos"][:6]

bpy.ops.wm.read_factory_settings(use_empty=True)
escena = bpy.context.scene
escena.frame_start, escena.frame_end, escena.render.fps = 1, FIN, FPS
f = lambda s: max(1, min(FIN, round(1 + s * FPS)))


def hexa(h, a=1.0):
    h = h.lstrip("#")
    c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return [x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c] + [a]


def material(nombre, color, rugosidad=0.45, metal=0.0):
    m = bpy.data.materials.new(nombre)
    m.use_nodes = True
    p = m.node_tree.nodes["Principled BSDF"]
    p.inputs["Base Color"].default_value = hexa(color)
    p.inputs["Roughness"].default_value = rugosidad
    p.inputs["Metallic"].default_value = metal
    return m


fuente = os.path.join(AQUI, "..", "fabrica", "fuentes", "Anton.ttf")
letra = bpy.data.fonts.load(fuente) if os.path.isfile(fuente) else None
tinta = material("tinta", "#1e1c1a", 0.6)


def texto(cuerpo, pos, tam, mat=tinta, alinear="CENTER"):
    cu = bpy.data.curves.new("t", "FONT")
    cu.body, cu.size, cu.extrude, cu.align_x, cu.align_y = cuerpo, tam, tam * 0.08, alinear, "BOTTOM"
    if letra:
        cu.font = letra
    t = bpy.data.objects.new("t", cu)
    escena.collection.objects.link(t)
    t.location, t.rotation_euler = pos, (math.radians(90), 0, 0)
    t.data.materials.append(mat)
    return t


COLORES = ["#4f8fcb", "#d7372c", "#e0a92e", "#3f7d4e", "#6a4f8a", "#e2775a"]
n = len(DATOS)
maximo = max(float(d["valor"]) for d in DATOS) or 1.0
ALTO_MAX = 1.6
ancho, hueco = 0.42, 0.22
x0 = -((n - 1) * (ancho + hueco)) / 2
oro = material("oro", "#e9b949", 0.25, 1.0)

for k, d in enumerate(DATOS):
    x = x0 + k * (ancho + hueco)
    alto = max(0.04, float(d["valor"]) / maximo * ALTO_MAX)
    a = max(0.0, float(d.get("a", 0.3 + k * 0.6)))
    crece = 1.1   # segundos que tarda en llegar a su altura
    if MODO == "pilas":
        # una torre de monedas: cada moneda aparece en su momento (de abajo arriba)
        grosor = 0.035
        monedas = max(1, round(alto / grosor))
        for j in range(monedas):
            bpy.ops.mesh.primitive_cylinder_add(vertices=32, radius=ancho * 0.45, depth=grosor * 0.9,
                                                location=(x + math.sin(j * 1.7) * 0.012, math.cos(j * 2.3) * 0.012, grosor * (j + 0.5)))
            m = bpy.context.object
            m.data.materials.append(oro)
            bev = m.modifiers.new("b", "BEVEL")
            bev.width, bev.segments = 0.006, 2
            t = a + crece * j / monedas
            m.scale = (0, 0, 0)
            m.keyframe_insert("scale", frame=1)
            m.keyframe_insert("scale", frame=max(1, f(t) - 1))
            m.scale = (1, 1, 1)
            m.keyframe_insert("scale", frame=f(t))
            for fc in getattr(m.animation_data.action, "fcurves", []) or []:
                for kp in fc.keyframe_points:
                    kp.interpolation = "CONSTANT"
    else:
        bpy.ops.mesh.primitive_cube_add(size=1, location=(x, 0, 0))
        c = bpy.context.object
        c.data.transform(__import__("mathutils").Matrix.Translation((0, 0, 0.5)))   # crece desde abajo
        bev = c.modifiers.new("b", "BEVEL")
        bev.width, bev.segments, bev.limit_method = 0.03, 4, "NONE"
        c.data.materials.append(material(f"c{k}", d.get("color") or COLORES[k % len(COLORES)], 0.35))
        c.scale = (0, 0, 0)   # no se ve hasta que se nombra (aplastado se veria como un cuadrado en la mesa)
        c.keyframe_insert("scale", frame=1)
        if f(a) > 2:
            c.keyframe_insert("scale", frame=f(a) - 1)
        c.scale = (ancho, ancho, 0.0001)
        c.keyframe_insert("scale", frame=f(a))
        c.scale = (ancho, ancho, alto * 1.06)
        c.keyframe_insert("scale", frame=f(a + crece * 0.8))
        c.scale = (ancho, ancho, alto)
        c.keyframe_insert("scale", frame=f(a + crece))
    # la cifra encima (sube con el dato) y la etiqueta delante, en el suelo
    cifra = texto(str(d.get("texto") or d["valor"]), (x, 0, alto + 0.06), 0.16)
    cifra.scale = (0, 0, 0)
    cifra.keyframe_insert("scale", frame=1)
    cifra.keyframe_insert("scale", frame=f(a + crece * 0.7))
    cifra.scale = (1, 1, 1)
    cifra.keyframe_insert("scale", frame=f(a + crece))
    etq = texto(str(d.get("etiqueta") or "")[:16].upper(), (x, -ancho * 0.8, 0.002), 0.13 if n <= 4 else 0.1)
    etq.rotation_euler = (0, 0, 0)   # tumbada en el suelo delante de su columna
    etq.scale = (0, 0, 0)
    etq.keyframe_insert("scale", frame=1)
    etq.keyframe_insert("scale", frame=f(a))
    etq.scale = (1, 1, 1)
    etq.keyframe_insert("scale", frame=f(a + 0.3))

# mesa, luz y camara (3/4, se acerca y gira despacio)
bpy.ops.mesh.primitive_plane_add(size=40, location=(0, 0, 0))
bpy.context.object.data.materials.append(material("mesa", P.get("suelo", "#d6cdbd"), 0.85))
mundo = bpy.data.worlds.new("mundo")
escena.world = mundo
mundo.use_nodes = True
mundo.node_tree.nodes["Background"].inputs["Color"].default_value = hexa(P.get("fondo", "#efe9df"))
mundo.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.5
centro = Vector((0, 0, ALTO_MAX * 0.45))
for nombre, pos, energia, tam in (("clave", (-3, -3.5, 4), 500, 4), ("relleno", (3.5, -2, 2), 120, 5), ("contra", (0, 4, 3.5), 250, 3)):
    dl = bpy.data.lights.new(nombre, "AREA")
    dl.energy, dl.size = energia, tam
    lo = bpy.data.objects.new(nombre, dl)
    escena.collection.objects.link(lo)
    lo.location = pos
    lo.rotation_euler = (centro - Vector(pos)).to_track_quat("-Z", "Y").to_euler()
cam_d = bpy.data.cameras.new("cam")
cam_d.lens = 40
cam_d.dof.use_dof = True
cam_d.dof.aperture_fstop = 4.0
cam = bpy.data.objects.new("cam", cam_d)
escena.collection.objects.link(cam)
escena.camera = cam
diana = bpy.data.objects.new("diana", None)
escena.collection.objects.link(diana)
diana.location = centro
cam_d.dof.focus_object = diana
pista = cam.constraints.new("TRACK_TO")
pista.target, pista.track_axis, pista.up_axis = diana, "TRACK_NEGATIVE_Z", "UP_Y"
vertical = P["alto"] > P["ancho"]
ancho_total = n * (ancho + hueco) + 0.4
d = max(ancho_total * (1.75 if vertical else 1.25), ALTO_MAX * (1.55 if vertical else 1.9))
for fr, ang, dd in ((1, -0.42, d * 1.08), (FIN, -0.18, d * 0.95)):
    cam.location = centro + Vector((math.sin(ang) * dd, -math.cos(ang) * dd, dd * 0.32))
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
for fr in range(1, FIN + 1, PASO):
    escena.frame_set(fr)
    r.filepath = os.path.join(P["salida"], f"f_{fr:04d}.png")
    bpy.ops.render.render(write_still=True)
    print("POSE", fr, FIN, flush=True)
print("LISTO", flush=True)
sys.stdout.flush()
os._exit(0)
