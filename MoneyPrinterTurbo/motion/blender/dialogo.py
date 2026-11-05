"""Dialogo en 3D: dos personajes low-poly (humano con gorro + bichito naranja) en una azotea de noche, con la ciudad
desenfocada detras, pantallas flotantes y un plano de camara por cada linea (plano y contraplano).

Uso: blender -b --factory-startup -P dialogo.py -- plano.json

plano.json = {
  "salida", "ancho", "alto", "fps": 24, "paso": 1|2 (2 = una pose cada dos fotogramas), "muestras", "duracion",
  "lineas": [{"quien": "h"|"c", "texto", "plano": general|medio|primer|primerisimo, "cara": ""|duda|susto|serio,
              "inicio": s, "dur": s, "boca": "0123..." (un digito por fotograma, volumen de la voz)}],
  "pantallas": [png, png] (tarjetas que flotan detras)
}
Todo se coloca a mano en cada fotograma (sin keyframes): una sola sesion de Blender para todos los planos.
"""
import json
import math
import os
import random
import sys

import bpy
from mathutils import Vector

P = json.load(open(sys.argv[sys.argv.index("--") + 1], encoding="utf-8"))
FPS, PASO = int(P.get("fps", 24)), int(P.get("paso", 2))
FIN = int(P["duracion"] * FPS)
os.makedirs(P["salida"], exist_ok=True)
azar = random.Random(P.get("semilla", 3))

bpy.ops.wm.read_factory_settings(use_empty=True)
escena = bpy.context.scene


def hexa(h, a=1.0):
    h = h.lstrip("#")
    c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return [x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c] + [a]


_mats = {}


def mat(color, rug=0.6, brillo=0.0):
    clave = (color, rug, brillo)
    if clave not in _mats:
        m = bpy.data.materials.new(color)
        m.use_nodes = True
        p = m.node_tree.nodes["Principled BSDF"]
        p.inputs["Base Color"].default_value = hexa(color)
        p.inputs["Roughness"].default_value = rug
        if brillo:
            p.inputs["Emission Color"].default_value = hexa(color)
            p.inputs["Emission Strength"].default_value = brillo
        _mats[clave] = m
    return _mats[clave]


def poner(o, m, padre=None, bisel=0.0, plano=True):
    o.data.materials.append(m)
    if bisel:
        b = o.modifiers.new("bisel", "BEVEL")
        b.width, b.segments = bisel, 2
    for pol in o.data.polygons:
        pol.use_smooth = not plano
    if padre:
        o.parent = padre
    return o


def caja(pos, tam, m, padre=None, bisel=0.012):
    bpy.ops.mesh.primitive_cube_add(size=1, location=pos)
    o = bpy.context.object
    o.scale = tam
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    return poner(o, m, padre, bisel)


def bola(pos, tam, m, padre=None, sub=2, plano=True):
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=sub, radius=1, location=pos)
    o = bpy.context.object
    o.scale = tam
    return poner(o, m, padre, plano=plano)


def quitar_bajo(o, z):
    """Borra los vertices por debajo de z (local, antes de escalar): deja un casquete abierto."""
    import bmesh
    bm = bmesh.new()
    bm.from_mesh(o.data)
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if v.co.z < z], context="VERTS")
    bm.to_mesh(o.data)
    bm.free()


def vacio(nombre, pos, padre=None):
    o = bpy.data.objects.new(nombre, None)
    escena.collection.objects.link(o)
    o.location = pos
    o.parent = padre
    return o


# ------------------------------------------------------------------ humano (low-poly, gorro rojo, sudadera)
PIEL, TINTA = mat("#b9794f", 0.65), mat("#0b0b0d", 0.18)
H = vacio("humano", (-0.52, 0, 0))
H.rotation_euler.z = math.radians(22)
cuerpo_h = vacio("cuerpo_h", (0, 0, 0), H)
for x in (-0.07, 0.07):
    caja((x, -0.01, 0.035), (0.1, 0.17, 0.07), mat("#eceae6", 0.5), cuerpo_h)            # zapatillas
    caja((x, 0, 0.22), (0.11, 0.12, 0.32), mat("#1d2742", 0.75), cuerpo_h)               # pantalon
caja((0, 0, 0.53), (0.32, 0.2, 0.34), mat("#25645f", 0.85), cuerpo_h, bisel=0.05)      # sudadera
caja((0, -0.101, 0.47), (0.2, 0.01, 0.09), mat("#1f5652", 0.85), cuerpo_h, bisel=0.005)  # bolsillo
for x in (-0.205, 0.205):
    caja((x, 0, 0.5), (0.085, 0.11, 0.3), mat("#25645f", 0.85), cuerpo_h, bisel=0.03)  # brazos
    bola((x, 0, 0.33), (0.045, 0.045, 0.05), PIEL, cuerpo_h, sub=1)                     # manos
bpy.ops.mesh.primitive_torus_add(major_radius=0.105, minor_radius=0.04, location=(0, 0.01, 0.71))
poner(bpy.context.object, mat("#1f5652", 0.85), cuerpo_h, plano=False)                  # capucha
for x in (-0.035, 0.035):
    caja((x, -0.105, 0.6), (0.012, 0.012, 0.12), mat("#eceae6", 0.5), cuerpo_h, bisel=0)  # cordones
cabeza = vacio("cabeza", (0, 0, 0.93), cuerpo_h)
bola((0, 0, 0), (0.2, 0.19, 0.21), PIEL, cabeza)
gorro = bola((0, 0, 0.07), (0.214, 0.208, 0.2), mat("#b8211c", 0.9), cabeza, sub=3)    # gorro (casquete)
quitar_bajo(gorro, -0.05)
bpy.ops.mesh.primitive_torus_add(major_radius=0.205, minor_radius=0.022, location=(0, 0, 0.06))
poner(bpy.context.object, mat("#a51d19", 0.9), cabeza, plano=False)                     # doblez del gorro
bola((0, -0.196, -0.06), (0.02, 0.02, 0.024), PIEL, cabeza, sub=2)                     # nariz
ojos_h = [bola((x, -0.183, -0.03), (0.026, 0.012, 0.036), TINTA, cabeza, sub=2, plano=False) for x in (-0.072, 0.072)]
cejas_h = [caja((x, -0.193, 0.014), (0.06, 0.012, 0.014), mat("#24160e", 0.9), cabeza, bisel=0.004)
           for x in (-0.072, 0.072)]
boca_h = bola((0, -0.186, -0.105), (0.034, 0.012, 0.02), TINTA, cabeza, sub=2, plano=False)
OJO_Z, CEJA_Z = ojos_h[0].location.z, cejas_h[0].location.z

# ------------------------------------------------------------------ bichito naranja (cubos)
NAR = mat("#c93d0a", 0.6, 0.1)
C = vacio("bicho", (0.5, 0.05, 0))
C.rotation_euler.z = math.radians(-22)
cuerpo_c = vacio("cuerpo_c", (0, 0, 0), C)
caja((0, 0, 0.3), (0.56, 0.34, 0.3), NAR, cuerpo_c, bisel=0.015)
for x in (-0.315, 0.315):
    caja((x, 0, 0.3), (0.07, 0.11, 0.1), NAR, cuerpo_c, bisel=0.008)                   # bracitos
for x in (-0.22, -0.13, 0.13, 0.22):
    for y in (-0.1, 0.1):
        caja((x, y, 0.075), (0.045, 0.045, 0.15), NAR, C, bisel=0.006)                 # patas (no rebotan)
ojos_c = [caja((x, -0.171, 0.33), (0.034, 0.008, 0.07), TINTA, cuerpo_c, bisel=0.003) for x in (-0.13, 0.13)]

# ------------------------------------------------------------------ azotea, ciudad, pantallas
suelo = bpy.data.materials.new("suelo")
suelo.use_nodes = True
n, l = suelo.node_tree.nodes, suelo.node_tree.links
p = n["Principled BSDF"]
p.inputs["Roughness"].default_value = 0.42
ladr = n.new("ShaderNodeTexBrick")
ladr.offset, ladr.squash_frequency = 0.0, 1
ladr.inputs["Scale"].default_value = 1.0
ladr.inputs["Brick Width"].default_value = 0.9
ladr.inputs["Row Height"].default_value = 0.9
ladr.inputs["Mortar Size"].default_value = 0.012
ladr.inputs["Color1"].default_value = hexa("#0c0d11")
ladr.inputs["Color2"].default_value = hexa("#101116")
ladr.inputs["Mortar"].default_value = hexa("#1f2330")
coord = n.new("ShaderNodeTexCoord")
l.new(coord.outputs["Object"], ladr.inputs["Vector"])
l.new(ladr.outputs["Color"], p.inputs["Base Color"])
bpy.ops.mesh.primitive_plane_add(size=1, location=(0, 2, 0))
o = bpy.context.object
o.scale = (14, 10, 1)
bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
o.data.materials.append(suelo)
caja((0, 7.05, -0.4), (14, 0.2, 0.8), mat("#0d0e12", 0.7), bisel=0)                    # borde de la azotea


def fachada(luz):
    m = bpy.data.materials.new("fachada")
    m.use_nodes = True
    n, l = m.node_tree.nodes, m.node_tree.links
    p = n["Principled BSDF"]
    p.inputs["Base Color"].default_value = hexa("#07080c")
    coord, ladr = n.new("ShaderNodeTexCoord"), n.new("ShaderNodeTexBrick")
    sep, junta, suma = n.new("ShaderNodeSeparateXYZ"), n.new("ShaderNodeCombineXYZ"), n.new("ShaderNodeMath")
    l.new(coord.outputs["Object"], sep.inputs[0])
    l.new(sep.outputs["X"], suma.inputs[0])
    l.new(sep.outputs["Y"], suma.inputs[1])
    l.new(suma.outputs[0], junta.inputs["X"])
    l.new(sep.outputs["Z"], junta.inputs["Y"])
    l.new(junta.outputs[0], ladr.inputs["Vector"])
    ladr.offset = 0.0
    ladr.inputs["Scale"].default_value = 1.0
    ladr.inputs["Brick Width"].default_value = 0.55
    ladr.inputs["Row Height"].default_value = 0.75
    ladr.inputs["Mortar Size"].default_value = 0.2
    ladr.inputs["Color1"].default_value = (0, 0, 0, 1)
    ladr.inputs["Color2"].default_value = (1, 1, 1, 1)
    ladr.inputs["Mortar"].default_value = (0, 0, 0, 1)
    corte = n.new("ShaderNodeValToRGB")                 # solo ~1 de cada 4 ventanas encendida
    corte.color_ramp.interpolation = "CONSTANT"
    corte.color_ramp.elements[1].position = 0.72
    l.new(ladr.outputs["Color"], corte.inputs["Fac"])
    tinte = n.new("ShaderNodeMix")
    tinte.data_type = "RGBA"
    tinte.blend_type = "MULTIPLY"
    tinte.inputs["Factor"].default_value = 1.0
    l.new(corte.outputs["Color"], tinte.inputs["A"])
    tinte.inputs["B"].default_value = hexa(luz)
    l.new(tinte.outputs["Result"], p.inputs["Emission Color"])
    p.inputs["Emission Strength"].default_value = 3.0
    return m


fachadas = [fachada(c) for c in ("#ffc970", "#ffe2b0", "#9fc2ff")]
for k in range(70):
    x, y = azar.uniform(-40, 40), azar.uniform(30, 90)
    ancho, alto = azar.uniform(3, 8), azar.uniform(4, 30)
    caja((x, y, (alto - 30) / 2), (ancho, azar.uniform(3, 8), alto + 30), azar.choice(fachadas), bisel=0)

pantallas = []
for k, (png, pos, giro) in enumerate(zip(P.get("pantallas", []), ((0.55, 1.1, 1.25), (-1.0, 1.7, 1.55)), (-8, 14))):
    m = bpy.data.materials.new(f"pantalla{k}")
    m.use_nodes = True
    n, l = m.node_tree.nodes, m.node_tree.links
    p = n["Principled BSDF"]
    img = n.new("ShaderNodeTexImage")
    img.image = bpy.data.images.load(png)
    l.new(img.outputs["Color"], p.inputs["Base Color"])
    l.new(img.outputs["Color"], p.inputs["Emission Color"])
    p.inputs["Emission Strength"].default_value = 0.9
    p.inputs["Roughness"].default_value = 0.3
    bpy.ops.mesh.primitive_plane_add(size=1, location=pos, rotation=(math.radians(90), 0, math.radians(giro)))
    o = bpy.context.object
    o.scale = (1.3, 1.3 * 560 / 900, 1)
    o.data.materials.append(m)
    pantallas.append((o, Vector(pos)))

mundo = bpy.data.worlds.new("mundo")
escena.world = mundo
mundo.use_nodes = True
mundo.node_tree.nodes["Background"].inputs["Color"].default_value = hexa("#070b1a")
mundo.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.6


def luz(tipo, pos, mira, color, energia, tam=1.0):
    d = bpy.data.lights.new(tipo, tipo)
    d.color, d.energy = hexa(color)[:3], energia
    if tipo == "AREA":
        d.size = tam
    o = bpy.data.objects.new(tipo, d)
    escena.collection.objects.link(o)
    o.location = pos
    o.rotation_euler = (Vector(mira) - Vector(pos)).to_track_quat("-Z", "Y").to_euler()
    return o


luz("AREA", (-1.6, -2.4, 2.4), (0, 0, 0.6), "#ffd2a6", 160, 1.6)    # principal calida
luz("AREA", (2.2, -1.6, 1.0), (0, 0, 0.6), "#7d93ff", 12, 2.0)      # relleno frio
luz("AREA", (0.3, 2.0, 1.6), (0, -0.2, 0.9), "#86a8ff", 70, 1.5)      # contraluz
luz("POINT", (0.5, -0.3, 0.18), (0, 0, 0), "#ff6a2a", 8)          # resplandor del bichito en el suelo

cam_d = bpy.data.cameras.new("cam")
cam_d.lens = 50
cam_d.dof.use_dof = True
cam = bpy.data.objects.new("cam", cam_d)
escena.collection.objects.link(cam)
escena.camera = cam

# ------------------------------------------------------------------ animacion por fotograma
LINEAS = P["lineas"]
parpadeos = {q: sorted(azar.uniform(0.5, P["duracion"]) for _ in range(int(P["duracion"] / 2.6))) for q in "hc"}


def linea_en(t):
    actual = LINEAS[0]
    for ln in LINEAS:
        if ln["inicio"] - 0.05 <= t:
            actual = ln
    return actual


def nivel_boca(t, quien):
    for ln in LINEAS:
        if ln["quien"] == quien and ln.get("boca") and ln["inicio"] <= t < ln["inicio"] + ln["dur"]:
            k = int((t - ln["inicio"]) * FPS)
            return int(ln["boca"][k]) / 9 if k < len(ln["boca"]) else 0.0
    return 0.0


def cerrado(t, quien):
    return any(0 <= t - b < 0.11 for b in parpadeos[quien])


def cara_h(t):
    cara = ""
    for ln in LINEAS:
        if ln["inicio"] - 0.05 <= t and ln["quien"] == "h":
            cara = ln["cara"]
    return cara


def pose(t):
    ln = linea_en(t)
    # humano: boca por volumen, cejas por expresion, cabeceo al hablar, respiracion
    b, cara = nivel_boca(t, "h"), cara_h(t)
    if cara == "susto":
        b = max(b, 0.45)
    boca_h.scale = (0.034 * (1 - 0.25 * b), 0.012, 0.006 + 0.03 * b)
    alto_ojo = 0.0 if cerrado(t, "h") else (1.3 if cara == "susto" else 1.0)
    for k, (o, c) in enumerate(zip(ojos_h, cejas_h)):
        o.scale.z = 0.036 * max(0.08, alto_ojo)
        lado = -1 if k == 0 else 1
        sube, giro = {"duda": (0.018 if k == 0 else 0.0, 14 * lado if k == 0 else -4 * lado),
                      "susto": (0.024, -8 * lado), "serio": (-0.008, 10 * lado)}.get(cara, (0.0, 0.0))
        c.location.z = CEJA_Z + sube
        c.rotation_euler.y = math.radians(giro)
    habla = ln["quien"] == "h" and b > 0.05
    cabeza.rotation_euler.x = math.radians(4 * b if habla else 0) + math.radians(1.2 * math.sin(t * 1.3))
    cabeza.rotation_euler.z = math.radians(5 * math.sin(t * 2.1) if habla else 2 * math.sin(t * 0.7))
    if cara == "susto":
        cabeza.location.z = 0.93 + 0.012
    else:
        cabeza.location.z = 0.93
    cuerpo_h.scale.z = 1 + 0.008 * math.sin(t * 2.4)
    # bichito: rebota un poco al hablar, ojos parpadean y se estiran
    bc = nivel_boca(t, "c")
    cuerpo_c.location.z = 0.012 * bc + 0.004 * math.sin(t * 3.0)
    cuerpo_c.rotation_euler.z = math.radians(3 * math.sin(t * 1.7) * (1 if bc else 0.3))
    for o in ojos_c:
        o.scale.z = 0.08 if cerrado(t, "c") else 1 + 0.15 * bc
    for k, (o, base) in enumerate(pantallas):
        o.location.z = base.z + 0.02 * math.sin(t * 0.9 + k)
    camara(ln, t)


def camara(ln, t):
    prog = min(1.0, max(0.0, (t - ln["inicio"]) / max(0.5, ln["dur"] + 0.3)))
    quien, plano = (H if ln["quien"] == "h" else C), ln["plano"]
    otro = 1 if ln["quien"] == "h" else -1
    if plano == "general":
        diana, dist, angulo, alto = Vector((0, 0.1, 0.5)), 3.3, 0.0, 0.22
    else:
        cabeza_z = 0.93 if ln["quien"] == "h" else 0.32
        diana = quien.matrix_world @ Vector((0, 0, {"medio": cabeza_z * 0.8, "primer": cabeza_z,
                                                     "primerisimo": cabeza_z}[plano]))
        dist = {"medio": 1.9, "primer": 1.15, "primerisimo": 0.95}[plano] * (1.15 if ln["quien"] == "c" else 1)
        angulo = quien.rotation_euler.z + math.radians(14 * otro)
        alto = 0.04
    dist *= 1.06 - 0.09 * prog                                             # acercamiento lento
    temblor = Vector((0.003 * math.sin(t * 1.9), 0, 0.002 * math.sin(t * 2.7 + 1)))
    cam.location = diana + Vector((math.sin(angulo) * dist, -math.cos(angulo) * dist, alto * dist)) + temblor
    cam.rotation_euler = (diana - cam.location).to_track_quat("-Z", "Y").to_euler()
    cam_d.dof.focus_distance = (diana - cam.location).length
    cam_d.dof.aperture_fstop = 2.8 if plano == "general" else 1.6
    cam_d.lens = 40 if plano == "general" else 50


# ------------------------------------------------------------------ render
r = escena.render
for motor in ("BLENDER_EEVEE", "BLENDER_EEVEE_NEXT"):
    try:
        r.engine = motor
        break
    except TypeError:
        pass
ee = escena.eevee
ee.taa_render_samples = int(P.get("muestras", 24))
for attr, val in (("use_raytracing", False), ("use_shadows", True)):
    if hasattr(ee, attr):
        setattr(ee, attr, val)
r.resolution_x, r.resolution_y, r.resolution_percentage = P["ancho"], P["alto"], 100
r.image_settings.file_format = "PNG"
escena.view_settings.view_transform = "AgX"
try:
    escena.view_settings.look = "AgX - Medium High Contrast"
except TypeError:
    pass
solo = P.get("solo")   # lista de segundos para probar fotos sueltas
r.filepath = os.path.join(P["salida"], "_calentar.png")
pose(0)
for _ in range(2):
    bpy.ops.render.render(write_still=False)
cuadros = [round(s * FPS) for s in solo] if solo else range(0, FIN, PASO)


def brillo(ruta):
    import numpy as np
    img = bpy.data.images.load(ruta)
    px = np.empty(len(img.pixels), dtype=np.float32)
    img.pixels.foreach_get(px)
    bpy.data.images.remove(img)
    return float(px.reshape(-1, 4)[:, :3].mean())


def render_bien(ruta, ref):
    """Renderiza y repite si sale a oscuras (EEVEE a veces suelta todas las luces). Devuelve el brillo."""
    mejor = -1.0
    for intento in range(5):
        r.filepath = ruta + (f".{intento}.png" if intento else "")
        bpy.ops.render.render(write_still=True)
        b = brillo(r.filepath)
        if b > mejor:
            if intento:
                os.replace(r.filepath, ruta)
            mejor = b
        elif intento:
            os.remove(r.filepath)
        if ref and mejor >= 0.8 * ref:
            break
        if not ref and intento >= 1:   # primer cuadro del plano: el mejor de dos
            break
        print("REPITE", ruta, round(b, 4), round(ref or 0, 4), flush=True)
    return mejor


antes, ref = None, 0.0
for fr in cuadros:
    pose(fr / FPS)
    if linea_en(fr / FPS) is not antes:
        antes, ref = linea_en(fr / FPS), 0.0
    b = render_bien(os.path.join(P["salida"], f"f_{fr:04d}.png"), ref)
    ref = max(ref * 0.97, b)           # el brillo de referencia sigue al plano (acercamiento lento)
    print("POSE", fr, FIN, flush=True)
print("LISTO", flush=True)
sys.stdout.flush()
os._exit(0)
