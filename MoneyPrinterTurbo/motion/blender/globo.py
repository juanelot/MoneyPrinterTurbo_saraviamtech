"""Escena 3D GLOBO: la Tierra en el espacio; gira y la camara vuela hasta cada pais al nombrarlo, se clava un pin y
sale su rotulo (el formato "vamos a ...": de un pais a otro, donde pasa algo).
La textura (paises de Natural Earth, los de las paradas resaltados) la pinta antes app/services/estudio/blender_gen.py.

Uso:  blender -b --factory-startup -P globo.py -- plano.json
plano.json = {"salida", "ancho", "alto", "fps", "muestras", "duracion", "paso": 1, "textura": png equirectangular,
              "paradas": [{"lon", "lat", "texto": "JAPON", "a": segundo}], "semilla"?}
"""
import json
import math
import os
import random
import sys

import bmesh
import bpy
from mathutils import Vector

AQUI = os.path.dirname(os.path.abspath(__file__))
P = json.load(open(sys.argv[sys.argv.index("--") + 1], encoding="utf-8"))
FPS = int(P.get("fps", 24))
FIN = max(2, round(P["duracion"] * FPS))
PASO = int(P.get("paso", 1))
os.makedirs(P["salida"], exist_ok=True)
azar = random.Random(P.get("semilla", 7))
PARADAS = P["paradas"][:4]

bpy.ops.wm.read_factory_settings(use_empty=True)
escena = bpy.context.scene
escena.frame_start, escena.frame_end, escena.render.fps = 1, FIN, FPS
f = lambda s: max(1, min(FIN, round(1 + s * FPS)))


def hexa(h, a=1.0):
    h = h.lstrip("#")
    c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return [x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c] + [a]


def plano_mat(nombre, color, rugosidad=0.5, emision=0.0):
    m = bpy.data.materials.new(nombre)
    m.use_nodes = True
    p = m.node_tree.nodes["Principled BSDF"]
    p.inputs["Base Color"].default_value = hexa(color)
    p.inputs["Roughness"].default_value = rugosidad
    if emision:
        p.inputs["Emission Color"].default_value = hexa(color)
        p.inputs["Emission Strength"].default_value = emision
    return m


# ------------------------------------------------------------------ la Tierra
# lon/lat salen de la direccion del punto (coordenadas del objeto): lon 0 en +X, lon 90 en +Y, el norte en +Z
# (asi se sabe exactamente hacia donde girarla, sin depender del UV de la esfera)
bpy.ops.mesh.primitive_uv_sphere_add(segments=128, ring_count=64, radius=1)
tierra = bpy.context.object
for pol in tierra.data.polygons:
    pol.use_smooth = True
m = bpy.data.materials.new("tierra")
m.use_nodes = True
n, l = m.node_tree.nodes, m.node_tree.links
coord = n.new("ShaderNodeTexCoord")
sep = n.new("ShaderNodeSeparateXYZ")
l.new(coord.outputs["Object"], sep.inputs["Vector"])
atan = n.new("ShaderNodeMath")
atan.operation = "ARCTAN2"
l.new(sep.outputs["Y"], atan.inputs[0])
l.new(sep.outputs["X"], atan.inputs[1])
u = n.new("ShaderNodeMath")
u.operation = "MULTIPLY_ADD"
u.inputs[1].default_value, u.inputs[2].default_value = 1 / (2 * math.pi), 0.5
l.new(atan.outputs[0], u.inputs[0])
largo = n.new("ShaderNodeVectorMath")
largo.operation = "NORMALIZE"
l.new(coord.outputs["Object"], largo.inputs[0])
sep2 = n.new("ShaderNodeSeparateXYZ")
l.new(largo.outputs["Vector"], sep2.inputs["Vector"])
asen = n.new("ShaderNodeMath")
asen.operation = "ARCSINE"
l.new(sep2.outputs["Z"], asen.inputs[0])
v = n.new("ShaderNodeMath")
v.operation = "MULTIPLY_ADD"
v.inputs[1].default_value, v.inputs[2].default_value = 1 / math.pi, 0.5
l.new(asen.outputs[0], v.inputs[0])
uv = n.new("ShaderNodeCombineXYZ")
l.new(u.outputs[0], uv.inputs["X"])
l.new(v.outputs[0], uv.inputs["Y"])
img = n.new("ShaderNodeTexImage")
img.image = bpy.data.images.load(P["textura"])
img.image.alpha_mode = "CHANNEL_PACKED"   # el alfa es un dato (mar/tierra), no transparencia
img.interpolation = "Cubic"
img.extension = "EXTEND"
l.new(uv.outputs["Vector"], img.inputs["Vector"])
pr = n["Principled BSDF"]
l.new(img.outputs["Color"], pr.inputs["Base Color"])
# el mar brilla un poco (alfa de la textura = 1 en el mar) y la tierra es mate
rug = n.new("ShaderNodeMapRange")
rug.inputs["To Min"].default_value, rug.inputs["To Max"].default_value = 0.85, 0.5
l.new(img.outputs["Alpha"], rug.inputs["Value"])
l.new(rug.outputs["Result"], pr.inputs["Roughness"])
tierra.data.materials.append(m)

# atmosfera: un halo azul en el borde (fresnel), transparente de frente
bpy.ops.mesh.primitive_uv_sphere_add(segments=96, ring_count=48, radius=1.045)
aire = bpy.context.object
for pol in aire.data.polygons:
    pol.use_smooth = True
ma = bpy.data.materials.new("atmosfera")
ma.use_nodes = True
try:
    ma.surface_render_method = "BLENDED"
except AttributeError:
    ma.blend_method = "BLEND"
n, l = ma.node_tree.nodes, ma.node_tree.links
n.remove(n["Principled BSDF"])
capa = n.new("ShaderNodeLayerWeight")
capa.inputs["Blend"].default_value = 0.35
pot = n.new("ShaderNodeMath")
pot.operation = "POWER"
pot.inputs[1].default_value = 2.2
l.new(capa.outputs["Facing"], pot.inputs[0])
emi = n.new("ShaderNodeEmission")
emi.inputs["Color"].default_value = hexa("#7fb8ff")
emi.inputs["Strength"].default_value = 2.2
trans = n.new("ShaderNodeBsdfTransparent")
mezcla = n.new("ShaderNodeMixShader")
l.new(pot.outputs[0], mezcla.inputs["Fac"])
l.new(trans.outputs[0], mezcla.inputs[1])
l.new(emi.outputs[0], mezcla.inputs[2])
l.new(mezcla.outputs[0], n["Material Output"].inputs["Surface"])
aire.data.materials.append(ma)

# el globo gira en Z (longitud) dentro de un vacio que lo inclina en X (latitud): asi el punto (lon, lat) queda
# justo de frente a la camara (direccion -Y)
inclina = bpy.data.objects.new("inclina", None)
escena.collection.objects.link(inclina)
tierra.parent = inclina


def giro(lon):
    return -math.pi / 2 - math.radians(lon)


def punto(lon, lat, r=1.0):
    lo, la = math.radians(lon), math.radians(lat)
    return Vector((math.cos(la) * math.cos(lo), math.cos(la) * math.sin(lo), math.sin(la))) * r


# ------------------------------------------------------------------ pines y rotulos (hijos del globo: giran con el)
fuente = os.path.join(AQUI, "..", "fabrica", "fuentes", "Anton.ttf")
letra = bpy.data.fonts.load(fuente) if os.path.isfile(fuente) else None
rojo = plano_mat("pin", "#e8352b", 0.3)
palo = plano_mat("palo", "#e9e9e9", 0.25)
blanco = plano_mat("placa", "#ffffff", 0.6)
tinta = plano_mat("tinta", "#1e1c1a", 0.6)
camara_obj = None   # se crea abajo; los rotulos miran a la camara


def pin(lon, lat):
    g = bpy.data.objects.new("pin", None)
    escena.collection.objects.link(g)
    g.parent = tierra
    g.location = punto(lon, lat)
    # inclinado hacia el norte: con la camara un poco arriba, clavado en la normal pareceria apuntar hacia abajo
    g.rotation_euler = (punto(lon, lat) + Vector((0, 0, 1.3))).normalized().to_track_quat("Z", "Y").to_euler()
    bpy.ops.mesh.primitive_cylinder_add(vertices=16, radius=0.006, depth=0.11, location=(0, 0, 0.055))
    a = bpy.context.object
    a.data.materials.append(palo)
    bpy.ops.mesh.primitive_uv_sphere_add(segments=24, ring_count=12, radius=0.024, location=(0, 0, 0.115))
    b = bpy.context.object
    b.data.materials.append(rojo)
    for pol in b.data.polygons:
        pol.use_smooth = True
    for o in (a, b):
        o.parent = g
    # la marca en el suelo: un disco rojo plano
    bpy.ops.mesh.primitive_cylinder_add(vertices=32, radius=0.018, depth=0.004, location=(0, 0, 0))
    c = bpy.context.object
    c.data.materials.append(rojo)
    c.parent = g
    return g


def rotulo(cuerpo):
    """Cartel blanco con el nombre, fijo en el mundo encima del pais de delante (solo se ve mientras esta ahi)."""
    cu = bpy.data.curves.new("t", "FONT")
    cu.body, cu.size, cu.extrude, cu.align_x, cu.align_y = cuerpo.upper(), 0.05, 0.004, "CENTER", "CENTER"
    if letra:
        cu.font = letra
    t = bpy.data.objects.new("rotulo", cu)
    escena.collection.objects.link(t)
    t.data.materials.append(tinta)
    t.location = (0, -1.12, 0.24)
    bpy.context.view_layer.update()
    ancho = max(0.08, t.dimensions.x + 0.04)
    bpy.ops.mesh.primitive_cube_add(size=1)
    placa = bpy.context.object
    placa.scale = (ancho, 0.08, 0.006)
    placa.location = (0, 0, -0.005)
    bisel = placa.modifiers.new("b", "BEVEL")
    bisel.width, bisel.segments, bisel.limit_method = 0.02, 4, "NONE"
    placa.data.materials.append(blanco)
    placa.parent = t
    for o in (t, placa):
        o.visible_shadow = False   # su sombra en el globo se veria como una mancha gris
    return t


pines = []
for k, p in enumerate(PARADAS):
    g = pin(p["lon"], p["lat"])
    t = rotulo(p["texto"]) if p.get("texto") else None
    pines.append((g, t))

# ------------------------------------------------------------------ espacio: fondo, estrellas y sol
mundo = bpy.data.worlds.new("mundo")
escena.world = mundo
mundo.use_nodes = True
mundo.node_tree.nodes["Background"].inputs["Color"].default_value = hexa("#0a1229")
mundo.node_tree.nodes["Background"].inputs["Strength"].default_value = 1.0
bm = bmesh.new()
for _ in range(700):
    d = Vector((azar.gauss(0, 1), azar.gauss(0, 1), azar.gauss(0, 1))).normalized()
    if d.y < -0.2:   # detras de la camara no hacen falta
        continue
    bmesh.ops.create_icosphere(bm, subdivisions=1, radius=azar.uniform(0.02, 0.06),
                               matrix=__import__("mathutils").Matrix.Translation(d * 40))
estrellas = bpy.data.meshes.new("estrellas")
bm.to_mesh(estrellas)
bm.free()
eo = bpy.data.objects.new("estrellas", estrellas)
escena.collection.objects.link(eo)
eo.data.materials.append(plano_mat("estrella", "#ffffff", 1.0, emision=3.0))
sol = bpy.data.lights.new("sol", "SUN")
sol.energy, sol.angle = 4.0, math.radians(3)
luz = bpy.data.objects.new("sol", sol)
escena.collection.objects.link(luz)
luz.rotation_euler = (math.radians(70), math.radians(-35), math.radians(-25))
relleno = bpy.data.lights.new("relleno", "SUN")
relleno.energy = 0.6
lr = bpy.data.objects.new("relleno", relleno)
escena.collection.objects.link(lr)
lr.rotation_euler = (math.radians(100), 0, math.radians(30))

# ------------------------------------------------------------------ camara y vuelo
vertical = P["alto"] > P["ancho"]
cam_d = bpy.data.cameras.new("cam")
cam_d.lens = 50
cam_d.sensor_fit = "HORIZONTAL"
cam_d.clip_start, cam_d.clip_end = 0.05, 200
cam = bpy.data.objects.new("cam", cam_d)
escena.collection.objects.link(cam)
escena.camera = cam
diana = bpy.data.objects.new("diana", None)
escena.collection.objects.link(diana)
pista = cam.constraints.new("TRACK_TO")
pista.target, pista.track_axis, pista.up_axis = diana, "TRACK_NEGATIVE_Z", "UP_Y"
for _, t in pines:
    if t:
        c = t.constraints.new("TRACK_TO")   # el rotulo siempre de cara a la camara y derecho
        c.target, c.track_axis, c.up_axis = cam, "TRACK_Z", "UP_Y"

# el globo entero cabe de ancho (con margen) lejos; cerca se ve la region del pais
media = math.atan(cam_d.sensor_width / 2 / cam_d.lens)
LEJOS = 1.25 / math.tan(media)
CERCA = (0.62 if vertical else 0.75) / math.tan(media)
ELEVA = math.radians(28)   # la camara mira un poco desde arriba: el pin se ve de pie


def colocar(fr, dist, cerca):
    """Camara a dist del centro, elevada; de cerca mira al punto de delante (el pais), de lejos al centro."""
    cam.location = Vector((0, -math.cos(ELEVA), math.sin(ELEVA))) * (dist - (1 if cerca else 0)) + (Vector((0, -1, 0)) if cerca else Vector())
    diana.location = Vector((0, -0.75, 0)) if cerca else Vector((0, 0, 0))
    cam.keyframe_insert("location", frame=fr)
    diana.keyframe_insert("location", frame=fr)


def orientar(fr, z, lat):
    tierra.rotation_euler = (0, 0, z)
    inclina.rotation_euler = (math.radians(lat), 0, 0)
    tierra.keyframe_insert("rotation_euler", frame=fr)
    inclina.keyframe_insert("rotation_euler", frame=fr)


def mostrar(ob, fr, si, rebote=True):
    final = (1, 1, 1)
    ob.scale = (0, 0, 0) if si else final
    ob.keyframe_insert("scale", frame=max(1, fr - 1))
    if si and rebote:
        ob.scale = (1.25, 1.25, 1.25)
        ob.keyframe_insert("scale", frame=min(FIN, fr + 4))
    ob.scale = final if si else (0, 0, 0)
    ob.keyframe_insert("scale", frame=min(FIN, fr + (8 if si else 5)))


for g, t in pines:
    for ob in [g] + ([t] if t else []):
        ob.scale = (0, 0, 0)
        ob.keyframe_insert("scale", frame=1)

# arranca lejos, girando hacia el primer pais desde 110 grados antes (ya se mueve en el primer fotograma)
z = giro(PARADAS[0]["lon"]) + math.radians(110)
lat = PARADAS[0]["lat"] * 0.3
orientar(1, z, lat)
colocar(1, LEJOS * 1.1, False)
llego = 0.0
for k, p in enumerate(PARADAS):
    a = max(0.0, float(p.get("a", 0.4 + k * 1.6)))
    sale = max(llego + 0.35, a - 0.7)
    llega = max(sale + 0.8, a + 0.45)
    if k:
        orientar(f(sale), z, lat)
        colocar(f(sale), CERCA, True)
        colocar(f((sale + llega) / 2), LEJOS * 0.85, False)   # entre pais y pais se aleja (se ve el viaje)
    elif f(sale) > 1:
        orientar(f(sale), z + math.radians(40) * min(1.0, sale / 2), lat)
        colocar(f(sale), LEJOS, False)
    destino = giro(p["lon"])
    destino += round((z - destino) / (2 * math.pi)) * 2 * math.pi   # por el camino corto
    z, lat = destino, p["lat"]
    orientar(f(llega), z, lat)
    colocar(f(llega), CERCA, True)
    g, t = pines[k]
    mostrar(g, f(llega - 0.1), True)
    if t:
        mostrar(t, f(llega + 0.1), True)
    if k:
        pg, pt = pines[k - 1]
        if pt:
            mostrar(pt, f(sale + 0.1), False, False)
    llego = llega
# al final se queda casi quieto: un giro muy lento y la camara se acerca un poco (nunca se para)
if FIN > f(llego) + 2:
    orientar(FIN, z + math.radians(6), lat)
    cam.location = cam.location + (diana.location - cam.location) * 0.08
    cam.keyframe_insert("location", frame=FIN)

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
