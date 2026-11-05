"""Escena 3D OBJETO PROTAGONISTA: un modelo de Poly Haven en un estudio de fotografia, como en un anuncio: entra de
golpe, gira sobre una peana, una luz le barre el brillo y detras sale una palabra enorme en 3D.

Uso:  blender -b --factory-startup -P objeto.py -- plano.json
plano.json = {"salida", "ancho", "alto", "fps", "muestras", "duracion", "paso": 1, "ruta": .gltf, "texto": "PALABRA",
              "ambiente": claro|oscuro|color, "color"?: "#hex" (el acento), "a": segundo en que entra, "semilla"?}
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
A = max(0.0, float(P.get("a", 0.2)))

AMBIENTES = {   # fondo, suelo de la peana, acento por defecto, fuerza de las luces
    "claro": ("#efe7da", "#ffffff", "#e8352b", 1.0),
    "oscuro": ("#15161b", "#26272e", "#f2b33d", 1.4),
    "color": ("#ffcf5a", "#fff3d6", "#2f5fd0", 1.0),
}
fondo, peana_c, acento, fuerza = AMBIENTES.get(P.get("ambiente"), AMBIENTES["claro"])
color = P.get("color") if isinstance(P.get("color"), str) and len(P["color"]) == 7 else None
acento = color or acento

bpy.ops.wm.read_factory_settings(use_empty=True)
escena = bpy.context.scene
escena.frame_start, escena.frame_end, escena.render.fps = 1, FIN, FPS


def hexa(h, a=1.0):
    h = h.lstrip("#")
    c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return [x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c] + [a]


def material(nombre, col, rugosidad=0.5, metal=0.0, emision=0.0):
    m = bpy.data.materials.new(nombre)
    m.use_nodes = True
    p = m.node_tree.nodes["Principled BSDF"]
    p.inputs["Base Color"].default_value = hexa(col)
    p.inputs["Roughness"].default_value = rugosidad
    p.inputs["Metallic"].default_value = metal
    if emision:
        p.inputs["Emission Color"].default_value = hexa(col)
        p.inputs["Emission Strength"].default_value = emision
    return m


# ------------------------------------------------------------------ el estudio: un ciclorama (suelo que sube en curva
# hasta la pared, sin esquina: el fondo infinito de las fotos de producto)
verts, caras = [], []
perfil = [(-12.0, 0.0), (0.0, 0.0)]
R = 2.5
for k in range(1, 13):
    t = k / 12 * math.pi / 2
    perfil.append((R * math.sin(t), R - R * math.cos(t)))
perfil.append((R, 14.0))
for x in (-20.0, 20.0):
    for y, z in perfil:
        verts.append((x, y + 1.6, z))
m = len(perfil)
for i in range(m - 1):
    caras.append((i, i + 1, m + i + 1, m + i))
malla = bpy.data.meshes.new("ciclorama")
malla.from_pydata(verts, [], caras)
cic = bpy.data.objects.new("ciclorama", malla)
escena.collection.objects.link(cic)
for pol in malla.polygons:
    pol.use_smooth = True
cic.data.materials.append(material("fondo", fondo, 0.9))

# peana redonda que gira
bpy.ops.mesh.primitive_cylinder_add(vertices=96, radius=0.75, depth=0.08, location=(0, 0, 0.04))
peana = bpy.context.object
b = peana.modifiers.new("b", "BEVEL")
b.width, b.segments = 0.02, 3
peana.data.materials.append(material("peana", peana_c, 0.35))
for pol in peana.data.polygons:
    pol.use_smooth = True
bpy.ops.mesh.primitive_cylinder_add(vertices=96, radius=0.758, depth=0.022, location=(0, 0, 0.04))   # franja del canto
aro = bpy.context.object
aro.data.materials.append(material("aro", acento, 0.3, emision=1.5))
aro.parent = peana


# ------------------------------------------------------------------ el modelo: el lado mayor mide 1, sobre la peana
def importar(ruta):
    antes = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=ruta)
    nuevos = [o for o in bpy.data.objects if o not in antes]
    g = bpy.data.objects.new("modelo", None)
    escena.collection.objects.link(g)
    for o in nuevos:
        if o.parent is None:
            o.parent = g
    return g


def caja(g):
    bpy.context.view_layer.update()
    pts = [o.matrix_world @ Vector(c) for o in g.children_recursive if o.type == "MESH" for c in o.bound_box]
    lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    return lo, hi


modelo = importar(P["ruta"])
lo, hi = caja(modelo)
s = 1.0 / max(1e-6, max(hi.x - lo.x, hi.y - lo.y, (hi.z - lo.z) * 0.9))
modelo.scale = (s, s, s)
lo, hi = caja(modelo)
modelo.location -= Vector(((lo.x + hi.x) / 2, (lo.y + hi.y) / 2, lo.z - 0.08))
lo, hi = caja(modelo)
ALTO = hi.z - lo.z
# todo lo que gira cuelga de un vacio: peana + modelo
giro = bpy.data.objects.new("giro", None)
escena.collection.objects.link(giro)
for o in (peana, modelo):
    o.parent = giro

# entra de golpe al decirse: cae desde arriba con rebote; gira entero en lo que dura el plano (nunca se para)
giro.rotation_euler = (0, 0, -0.9)
giro.keyframe_insert("rotation_euler", frame=1)
giro.rotation_euler = (0, 0, -0.9 + min(2 * math.pi, 0.9 * P["duracion"]))
giro.keyframe_insert("rotation_euler", frame=FIN)
for fc in getattr(giro.animation_data.action, "fcurves", []) or []:
    for kp in fc.keyframe_points:
        kp.interpolation = "LINEAR"
modelo.location.z += 2.2
modelo.keyframe_insert("location", frame=1)
if f(A) > 1:
    modelo.keyframe_insert("location", frame=f(A))
modelo.location.z -= 2.2
modelo.keyframe_insert("location", frame=f(A + 0.28))
modelo.location.z += 0.12
modelo.keyframe_insert("location", frame=f(A + 0.42))
modelo.location.z -= 0.12
modelo.keyframe_insert("location", frame=f(A + 0.56))
final = modelo.scale.copy()
modelo.scale = (final.x * 1.15, final.y * 1.15, final.z * 0.82)   # se aplasta un poco al tocar la peana
modelo.keyframe_insert("scale", frame=f(A + 0.3))
modelo.scale = final
modelo.keyframe_insert("scale", frame=f(A + 0.2))
modelo.keyframe_insert("scale", frame=f(A + 0.45))

# ------------------------------------------------------------------ la palabra enorme detras, en el color de acento
fuente = os.path.join(AQUI, "..", "fabrica", "fuentes", "Anton.ttf")
letra = bpy.data.fonts.load(fuente) if os.path.isfile(fuente) else None
vertical = P["alto"] > P["ancho"]
texto = str(P.get("texto") or "").strip().upper()[:18]
if texto:
    cu = bpy.data.curves.new("palabra", "FONT")
    cu.body, cu.extrude, cu.align_x, cu.align_y = texto, 0.06, "CENTER", "CENTER"
    if letra:
        cu.font = letra
    pal = bpy.data.objects.new("palabra", cu)
    escena.collection.objects.link(pal)
    pal.data.materials.append(material("palabra", acento, 0.35))
    pal.rotation_euler = (math.radians(90), 0, 0)
    pal.location = (0, 1.4, ALTO + 0.55)   # por encima del objeto: que no lo tape
    bpy.context.view_layer.update()
    cu.size = min((2.0 if vertical else 3.2) / max(0.1, pal.dimensions.x), 1.6)   # cabe de ancho detras del objeto
    pal.scale = (0, 0, 0)
    pal.keyframe_insert("scale", frame=1)
    pal.keyframe_insert("scale", frame=f(A + 0.25))
    pal.scale = (1.12, 1.12, 1.12)
    pal.keyframe_insert("scale", frame=f(A + 0.45))
    pal.scale = (1, 1, 1)
    pal.keyframe_insert("scale", frame=f(A + 0.65))

# ------------------------------------------------------------------ luces de anuncio
mundo = bpy.data.worlds.new("mundo")
escena.world = mundo
mundo.use_nodes = True
mundo.node_tree.nodes["Background"].inputs["Color"].default_value = hexa(fondo)
mundo.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.35
centro = Vector((0, 0, ALTO * 0.5 + 0.08))


def area(nombre, pos, energia, tam, col="#ffffff"):
    d = bpy.data.lights.new(nombre, "AREA")
    d.energy, d.size, d.color = energia * fuerza, tam, hexa(col)[:3]
    o = bpy.data.objects.new(nombre, d)
    escena.collection.objects.link(o)
    o.location = pos
    o.rotation_euler = (centro - Vector(pos)).to_track_quat("-Z", "Y").to_euler()
    return o


area("clave", (-2.2, -2.4, 3.0), 420, 2.5)
area("relleno", (2.6, -1.8, 1.4), 90, 3.0)
area("contra", (1.6, 2.2, 2.6), 380, 1.2, acento)   # el borde de color que lo despega del fondo
# barrido: una tira de luz estrecha que cruza por delante (el destello de anuncio al entrar)
barre = area("barrido", (-3.5, -1.6, 1.4), 0, 0.3)
barre.data.shape, barre.data.size, barre.data.size_y = "RECTANGLE", 0.15, 3.0
for fr, x, e in ((f(A + 0.4), -3.5, 0), (f(A + 0.55), -2.5, 900), (f(A + 1.4), 3.5, 900), (f(A + 1.55), 3.5, 0)):
    barre.location.x = x
    barre.data.energy = e * fuerza
    barre.keyframe_insert("location", frame=fr)
    barre.data.keyframe_insert("energy", frame=fr)

# ------------------------------------------------------------------ camara: contrapicado (heroico), se acerca despacio
cam_d = bpy.data.cameras.new("cam")
cam_d.lens = 50
cam_d.sensor_fit = "HORIZONTAL"
cam_d.dof.use_dof = True
cam_d.dof.aperture_fstop = 2.8
cam = bpy.data.objects.new("cam", cam_d)
escena.collection.objects.link(cam)
escena.camera = cam
diana = bpy.data.objects.new("diana", None)
escena.collection.objects.link(diana)
diana.location = centro
cam_d.dof.focus_object = diana
pista = cam.constraints.new("TRACK_TO")
pista.target, pista.track_axis, pista.up_axis = diana, "TRACK_NEGATIVE_Z", "UP_Y"
media = math.atan(cam_d.sensor_width / 2 / cam_d.lens)
d = (0.85 if vertical else 1.4) / math.tan(media)   # de ancho entra la peana (1,5) con aire
for fr, ang, dd, alto in ((1, -0.35, d * 1.18, 0.35), (FIN, -0.12, d * 0.96, 0.25)):
    cam.location = centro + Vector((math.sin(ang) * dd, -math.cos(ang) * dd, -centro.z + alto + ALTO * 0.3))
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
for fr in range(1, FIN + 1, PASO):
    escena.frame_set(fr)
    r.filepath = os.path.join(P["salida"], f"f_{fr:04d}.png")
    bpy.ops.render.render(write_still=True)
    print("POSE", fr, FIN, flush=True)
print("LISTO", flush=True)
sys.stdout.flush()
os._exit(0)
