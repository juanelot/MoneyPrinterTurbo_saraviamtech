"""Escena 3D DIORAMA: un mundo en miniatura sobre una isla redonda (ciudad, pueblo, bosque, nieve o desierto) que se
construye solo, pieza a pieza desde el centro, y gira despacio con desenfoque de maqueta (tilt-shift). Coches que dan
vueltas, nubes que pasan. Con "bucle" todo esta montado desde el principio y el giro es una vuelta entera: el ultimo
fotograma empalma con el primero.

Uso:  blender -b --factory-startup -P diorama.py -- plano.json
plano.json = {"salida", "ancho", "alto", "fps", "muestras", "duracion", "paso": 1, "tema": ciudad|pueblo|bosque|nieve|
              desierto, "hora": dia|noche, "texto"?: "PALABRA" (flota encima), "a"?: segundo en que se monta,
              "bucle"?: bool, "semilla"?}
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
PASO = int(P.get("paso", 1))
os.makedirs(P["salida"], exist_ok=True)
f = lambda s: max(1, min(FIN, round(1 + s * FPS)))
BUCLE = bool(P.get("bucle"))
A = 0.0 if BUCLE else max(0.0, float(P.get("a", 0.2)))
TEMA = P.get("tema") if P.get("tema") in ("ciudad", "pueblo", "bosque", "nieve", "desierto") else "pueblo"
NOCHE = P.get("hora") == "noche"
rnd = random.Random(int(P.get("semilla") or 7))

TEMAS = {   # suelo, cielo de dia, cielo de noche
    "ciudad": ("#8fbf6a", "#bfe3f2", "#141b33"),
    "pueblo": ("#8cc46a", "#cdeaf5", "#151b35"),
    "bosque": ("#6aa857", "#d3ecd8", "#101a26"),
    "nieve": ("#f4f7fb", "#dfe9f5", "#121a30"),
    "desierto": ("#e8c785", "#ffe3b5", "#1d1830"),
}
suelo_c, cielo_dia, cielo_noche = TEMAS[TEMA]
cielo = cielo_noche if NOCHE else cielo_dia

bpy.ops.wm.read_factory_settings(use_empty=True)
escena = bpy.context.scene
escena.frame_start, escena.frame_end, escena.render.fps = 1, FIN, FPS


def hexa(h, a=1.0):
    h = h.lstrip("#")
    c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return [x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c] + [a]


_mats = {}


def material(col, rugosidad=0.7, emision=0.0, metal=0.0):
    clave = (col, rugosidad, emision, metal)
    if clave in _mats:
        return _mats[clave]
    m = bpy.data.materials.new(col)
    m.use_nodes = True
    p = m.node_tree.nodes["Principled BSDF"]
    p.inputs["Base Color"].default_value = hexa(col)
    p.inputs["Roughness"].default_value = rugosidad
    p.inputs["Metallic"].default_value = metal
    if emision:
        p.inputs["Emission Color"].default_value = hexa(col)
        p.inputs["Emission Strength"].default_value = emision
    _mats[clave] = m
    return m


def ventanas(pared, vidrio):
    """Fachada con ventanas: textura de ladrillo en coordenadas del objeto (ladrillo = ventana, junta = pared).
    De noche las ventanas se encienden."""
    clave = ("ventanas", pared, NOCHE)
    if clave in _mats:
        return _mats[clave]
    m = bpy.data.materials.new("fachada")
    m.use_nodes = True
    n, l = m.node_tree.nodes, m.node_tree.links
    p = n["Principled BSDF"]
    p.inputs["Roughness"].default_value = 0.6
    coord, ladr = n.new("ShaderNodeTexCoord"), n.new("ShaderNodeTexBrick")
    # la textura es plana (x, y): se le da (x + y, z) para que las filas vayan por pisos en las cuatro fachadas
    sep, junta = n.new("ShaderNodeSeparateXYZ"), n.new("ShaderNodeCombineXYZ")
    suma = n.new("ShaderNodeMath")
    l.new(coord.outputs["Object"], sep.inputs[0])
    l.new(sep.outputs["X"], suma.inputs[0])
    l.new(sep.outputs["Y"], suma.inputs[1])
    l.new(suma.outputs[0], junta.inputs["X"])
    l.new(sep.outputs["Z"], junta.inputs["Y"])
    l.new(junta.outputs[0], ladr.inputs["Vector"])
    # en metros de la escena (el edificio lleva la escala aplicada): ventanas de 2 x 2,5 cm
    ladr.inputs["Scale"].default_value = 1.0
    ladr.inputs["Mortar Size"].default_value = 0.009
    ladr.inputs["Brick Width"].default_value = 0.028
    ladr.inputs["Row Height"].default_value = 0.034
    ladr.offset = 0.0
    ladr.inputs["Mortar"].default_value = hexa(pared)
    luz = "#ffd27a" if NOCHE else vidrio
    ladr.inputs["Color1"].default_value = hexa(luz)
    ladr.inputs["Color2"].default_value = hexa("#ffb84d" if NOCHE else vidrio)
    l.new(ladr.outputs["Color"], p.inputs["Base Color"])
    if NOCHE:
        # solo brillan las ventanas (el factor es 1 en la junta)
        inv = n.new("ShaderNodeMath")
        inv.operation = "SUBTRACT"
        inv.inputs[0].default_value = 1.0
        l.new(ladr.outputs["Fac"], inv.inputs[1])
        mult = n.new("ShaderNodeMath")
        mult.operation = "MULTIPLY"
        mult.inputs[1].default_value = 3.0
        l.new(inv.outputs[0], mult.inputs[0])
        l.new(ladr.outputs["Color"], p.inputs["Emission Color"])
        l.new(mult.outputs[0], p.inputs["Emission Strength"])
    _mats[clave] = m
    return m


def plano_liso(o):
    for pol in o.data.polygons:
        pol.use_smooth = False


def nuevo(o, mat, padre, bisel=0.0):
    o.data.materials.append(mat)
    if bisel:
        b = o.modifiers.new("b", "BEVEL")
        b.width, b.segments = bisel, 2
    o.parent = padre
    return o


def caja(pos, tam, mat, padre, bisel=0.006):
    bpy.ops.mesh.primitive_cube_add(size=1, location=pos)
    o = bpy.context.object
    o.scale = tam
    return nuevo(o, mat, padre, bisel)


def cilindro(pos, r, alto, mat, padre, lados=12):
    bpy.ops.mesh.primitive_cylinder_add(vertices=lados, radius=r, depth=alto, location=(pos[0], pos[1], pos[2] + alto / 2))
    return nuevo(bpy.context.object, mat, padre)


def cono(pos, r, alto, mat, padre, lados=8, giro=0.0):
    bpy.ops.mesh.primitive_cone_add(vertices=lados, radius1=r, depth=alto, location=(pos[0], pos[1], pos[2] + alto / 2),
                                    rotation=(0, 0, giro))
    return nuevo(bpy.context.object, mat, padre)


def bola(pos, tam, mat, padre, sub=1):
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=sub, radius=1, location=pos)
    o = bpy.context.object
    o.scale = tam
    return nuevo(o, mat, padre)


def grupo(x, y, giro=None):
    g = bpy.data.objects.new("pieza", None)
    escena.collection.objects.link(g)
    g.parent = isla
    g.location = (x, y, 0)
    g.rotation_euler.z = rnd.uniform(0, 2 * math.pi) if giro is None else giro
    return g


# ------------------------------------------------------------------ la isla: capa de suelo sobre un bloque de tierra
isla = bpy.data.objects.new("isla", None)
escena.collection.objects.link(isla)
tierra = "#c9b28a" if TEMA in ("desierto", "nieve") else "#8a5a3b"
if TEMA == "nieve":
    tierra = "#7b6a5c"
cilindro((0, 0, -0.42), 0.97, 0.36, material(tierra, 0.95), isla, lados=48)
cilindro((0, 0, -0.5), 0.9, 0.08, material("#5c3b28" if TEMA != "desierto" else "#b0905f", 0.95), isla, lados=48)
cilindro((0, 0, -0.07), 1.0, 0.07, material(suelo_c, 0.9), isla, lados=48)
for o in isla.children:
    b = o.modifiers.new("b", "BEVEL")
    b.width, b.segments = 0.02, 2

# ------------------------------------------------------------------ las piezas de cada tema
VERDES = ["#5f9e4a", "#4f8f43", "#77b155", "#3f7d3a"]
COLORES = ["#f2b33d", "#e8705a", "#6fa8dc", "#f4f1ec", "#e3a5c7", "#9fd0a8", "#f6d47a"]


def arbol(g, alto=None):
    alto = alto or rnd.uniform(0.11, 0.17)
    cilindro((0, 0, 0), 0.012, alto * 0.45, material("#7a4f30"), g, 6)
    bola((0, 0, alto * 0.62), (alto * 0.42,) * 3, material(rnd.choice(VERDES)), g)


def pino(g, nevado=False):
    alto = rnd.uniform(0.15, 0.24)
    cilindro((0, 0, 0), 0.012, alto * 0.25, material("#6b4428"), g, 6)
    verde = material(rnd.choice(VERDES[1:]))
    for k in range(3):
        r = alto * (0.34 - k * 0.08)
        cono((0, 0, alto * (0.18 + k * 0.22)), r, alto * 0.42, verde, g, 8)
        if nevado:
            cono((0, 0, alto * (0.18 + k * 0.22) + alto * 0.24), r * 0.45, alto * 0.18, material("#ffffff", 0.6), g, 8)


def casa(g, color=None):
    w, l, h = rnd.uniform(0.1, 0.14), rnd.uniform(0.12, 0.17), rnd.uniform(0.07, 0.1)
    caja((0, 0, h / 2), (w, l, h), material(color or rnd.choice(COLORES)), g)
    tejado = cono((0, 0, h), max(w, l) * 0.62, h * 0.8, material(rnd.choice(["#c4483a", "#8d3b33", "#5a5f73", "#b8613b"])), g, 4,
                  giro=math.pi / 4)
    tejado.scale = (w / max(w, l) * 1.15, l / max(w, l) * 1.15, 1)
    caja((0, -l / 2 - 0.002, 0.025), (0.025, 0.006, 0.05), material("#5b3a26"), g, 0)
    for x in (-w * 0.28, w * 0.28):
        caja((x, -l / 2 - 0.002, h * 0.62), (0.022, 0.006, 0.022), material("#ffd27a", 0.4, emision=4.0 if NOCHE else 0.0)
             if NOCHE else material("#9ec9e6", 0.2), g, 0)


def edificio(g, cerca):
    w = rnd.uniform(0.12, 0.17)
    h = rnd.uniform(0.35, 0.75) if cerca else rnd.uniform(0.18, 0.35)
    pared = rnd.choice(["#e9e4da", "#c9cfd6", "#d9b48f", "#a9b8c9", "#f0d9a8", "#8f9aa8"])
    o = caja((0, 0, h / 2), (w, w, h), ventanas(pared, "#5d86a8"), g, 0.004)
    bpy.ops.object.select_all(action="DESELECT")
    o.select_set(True)
    bpy.context.view_layer.objects.active = o
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    caja((0, 0, h + 0.008), (w * 1.04, w * 1.04, 0.016), material("#5a5f6a"), g, 0.003)
    if rnd.random() < 0.4:
        caja((w * 0.2, w * 0.15, h + 0.03), (w * 0.3, w * 0.3, 0.035), material("#7d838c"), g, 0.003)


def roca(g, escala=1.0):
    o = bola((0, 0, 0.015 * escala), (0.04 * escala, 0.032 * escala, 0.03 * escala), material("#8c8f93", 0.9), g, sub=1)
    o.rotation_euler = (rnd.uniform(0, 1), rnd.uniform(0, 1), rnd.uniform(0, 3))


def cactus(g):
    verde = material("#5d9a4e", 0.8)
    h = rnd.uniform(0.12, 0.2)
    cilindro((0, 0, 0), 0.022, h, verde, g, 10)
    for lado in (-1, 1):
        if rnd.random() < 0.8:
            alto = h * rnd.uniform(0.35, 0.6)
            caja((lado * 0.035, 0, alto), (0.04, 0.02, 0.016), verde, g, 0.006)
            cilindro((lado * 0.05, 0, alto - 0.005), 0.014, h * 0.3, verde, g, 8)


def piramide(g):
    o = cono((0, 0, 0), 0.24, 0.3, material("#c99a55", 0.95), g, 4, giro=math.pi / 4)
    plano_liso(o)


def cabana(g):
    w, l, h = 0.13, 0.16, 0.08
    caja((0, 0, h / 2), (w, l, h), material("#8a5a3b"), g)
    t = cono((0, 0, h), l * 0.62, h * 1.1, material("#ffffff", 0.6), g, 4, giro=math.pi / 4)
    t.scale = (w / l * 1.2, 1.2, 1)
    caja((0, -l / 2 - 0.002, h * 0.55), (0.024, 0.006, 0.024), material("#ffd27a", 0.4, emision=4.0) if NOCHE
         else material("#ffcf73", 0.4, emision=0.6), g, 0)


def colocar(cuantas, r_min, r_max, sep, hacer, ocupado):
    """Reparte piezas al azar en un anillo sin que se pisen; devuelve [(grupo, distancia al centro)]."""
    hechas = []
    for _ in range(cuantas * 30):
        if len(hechas) >= cuantas:
            break
        ang, r = rnd.uniform(0, 2 * math.pi), math.sqrt(rnd.uniform(r_min ** 2, r_max ** 2))
        x, y = r * math.cos(ang), r * math.sin(ang)
        if any((x - ox) ** 2 + (y - oy) ** 2 < (sep + os_) ** 2 for ox, oy, os_ in ocupado):
            continue
        ocupado.append((x, y, sep * 0.5))
        g = grupo(x, y)
        hacer(g, r)
        hechas.append((g, r))
    return hechas


piezas, ocupado, coches = [], [], []
CARRETERA = 0.6   # radio del anillo de carretera (ciudad y pueblo)
if TEMA in ("ciudad", "pueblo"):
    # carretera en anillo con su linea; nadie se pone encima
    bpy.ops.mesh.primitive_torus_add(major_radius=CARRETERA, minor_radius=0.065, major_segments=64, minor_segments=4,
                                     location=(0, 0, 0.0))
    via = nuevo(bpy.context.object, material("#4b4f57", 0.9), isla)
    via.scale.z = 0.08
    bpy.ops.mesh.primitive_torus_add(major_radius=CARRETERA, minor_radius=0.004, major_segments=64, minor_segments=4,
                                     location=(0, 0, 0.004))
    raya = nuevo(bpy.context.object, material("#f4f1ec", 0.6), isla)
    raya.scale.z = 0.5
    for k in range(64):
        ocupado.append((CARRETERA * math.cos(k / 64 * 2 * math.pi), CARRETERA * math.sin(k / 64 * 2 * math.pi), 0.05))
if TEMA == "ciudad":
    piezas += colocar(9, 0.0, 0.42, 0.13, lambda g, r: edificio(g, True), ocupado)
    piezas += colocar(9, 0.76, 0.9, 0.13, lambda g, r: edificio(g, False), ocupado)
    piezas += colocar(10, 0.7, 0.93, 0.05, lambda g, r: arbol(g), ocupado)
    piezas += colocar(4, 0.0, 0.45, 0.05, lambda g, r: arbol(g, 0.1), ocupado)
elif TEMA == "pueblo":
    piezas += colocar(5, 0.0, 0.4, 0.15, lambda g, r: casa(g), ocupado)
    piezas += colocar(7, 0.76, 0.9, 0.15, lambda g, r: casa(g), ocupado)
    piezas += colocar(18, 0.0, 0.94, 0.06, lambda g, r: arbol(g), ocupado)
elif TEMA == "bosque":
    lago = bola((0.25, 0.1, -0.003), (0.32, 0.22, 0.01), material("#4f9fd6", 0.08), isla, sub=3)
    lago.rotation_euler.z = 0.4
    ocupado.append((0.25, 0.1, 0.3))
    piezas += colocar(26, 0.0, 0.93, 0.07, lambda g, r: (pino if rnd.random() < 0.5 else arbol)(g), ocupado)
    piezas += colocar(6, 0.0, 0.93, 0.05, lambda g, r: roca(g, rnd.uniform(0.7, 1.4)), ocupado)
elif TEMA == "nieve":
    piezas += colocar(2, 0.0, 0.5, 0.18, lambda g, r: cabana(g), ocupado)
    piezas += colocar(24, 0.0, 0.93, 0.07, lambda g, r: pino(g, True), ocupado)
    piezas += colocar(5, 0.2, 0.93, 0.05, lambda g, r: roca(g, rnd.uniform(0.8, 1.5)), ocupado)
else:   # desierto
    piezas += colocar(1, 0.0, 0.15, 0.4, lambda g, r: piramide(g), ocupado)
    piezas += colocar(2, 0.45, 0.8, 0.3, lambda g, r: piramide(g), ocupado)
    for g, _ in piezas:
        g.scale = (0.6,) * 3 if math.hypot(*g.location[:2]) > 0.3 else (1, 1, 1)
    piezas += colocar(10, 0.0, 0.93, 0.07, lambda g, r: cactus(g), ocupado)
    piezas += colocar(5, 0.0, 0.93, 0.05, lambda g, r: roca(g, rnd.uniform(0.8, 1.5)), ocupado)

# coches dando vueltas por la carretera (vueltas enteras en el plano: en bucle empalman)
if TEMA in ("ciudad", "pueblo"):
    vueltas = max(1, round(P["duracion"] / 9))
    for k in range(4 if TEMA == "ciudad" else 2):
        eje = bpy.data.objects.new("eje", None)
        escena.collection.objects.link(eje)
        eje.parent = isla
        carril = CARRETERA + (0.03 if k % 2 else -0.03)
        g = bpy.data.objects.new("coche", None)
        escena.collection.objects.link(g)
        g.parent = eje
        g.location = (carril, 0, 0)
        col = material(rnd.choice(["#e8352b", "#2f5fd0", "#f2b33d", "#f4f1ec", "#2a2d33"]), 0.3)
        caja((0, 0, 0.012), (0.034, 0.06, 0.016), col, g, 0.004)
        caja((0, 0.004, 0.026), (0.028, 0.032, 0.014), material("#bcd7ea", 0.15), g, 0.004)
        if NOCHE:
            for x in (-0.01, 0.01):
                bola((x, -0.031 if k % 2 else 0.031, 0.012), (0.004,) * 3, material("#fff4c8", 0.3, emision=12.0), g, sub=1)
        sentido = 1 if k % 2 else -1
        g.rotation_euler.z = 0 if sentido > 0 else math.pi
        inicio = k / (4 if TEMA == "ciudad" else 2) * 2 * math.pi
        eje.rotation_euler.z = inicio
        eje.keyframe_insert("rotation_euler", frame=1)
        eje.rotation_euler.z = inicio + sentido * vueltas * 2 * math.pi
        eje.keyframe_insert("rotation_euler", frame=FIN + (1 if BUCLE else 0))
        for fc in eje.animation_data.action.fcurves if hasattr(eje.animation_data.action, "fcurves") else []:
            for kp in fc.keyframe_points:
                kp.interpolation = "LINEAR"
        coches.append(g)

# nubes que cruzan por encima
for k in range(3):
    eje = bpy.data.objects.new("viento", None)
    escena.collection.objects.link(eje)
    eje.parent = isla
    nube = bpy.data.objects.new("nube", None)
    escena.collection.objects.link(nube)
    nube.parent = eje
    nube.location = (rnd.uniform(0.75, 1.0), 0, rnd.uniform(0.45, 0.62))   # por debajo del texto: no lo tapan
    blanco = material("#ffffff" if not NOCHE else "#6d7896", 0.9)
    for j in range(4):
        bola((j * 0.07 - 0.1, rnd.uniform(-0.02, 0.02), rnd.uniform(0, 0.03)), (rnd.uniform(0.06, 0.09),) * 3, blanco, nube, sub=2)
    inicio = k * 2.1
    eje.rotation_euler.z = inicio
    eje.keyframe_insert("rotation_euler", frame=1)
    eje.rotation_euler.z = inicio + (2 * math.pi if BUCLE else 0.12 * P["duracion"])
    eje.keyframe_insert("rotation_euler", frame=FIN + (1 if BUCLE else 0))
    for fc in eje.animation_data.action.fcurves if hasattr(eje.animation_data.action, "fcurves") else []:
        for kp in fc.keyframe_points:
            kp.interpolation = "LINEAR"

# ------------------------------------------------------------------ se construye: la isla sale de abajo y luego cada
# pieza crece desde el suelo, del centro hacia fuera
if not BUCLE:
    isla.scale = (0.001,) * 3
    isla.keyframe_insert("scale", frame=1)
    isla.keyframe_insert("scale", frame=f(A))
    isla.scale = (1.06, 1.06, 1.06)
    isla.keyframe_insert("scale", frame=f(A + 0.3))
    isla.scale = (1, 1, 1)
    isla.keyframe_insert("scale", frame=f(A + 0.45))
    orden = sorted(piezas, key=lambda x: x[1])
    for k, (g, r) in enumerate(orden):
        t = A + 0.35 + k / max(1, len(orden)) * 1.3
        s = g.scale.copy()
        g.scale = (s.x * 0.001, s.y * 0.001, s.z * 0.001)
        g.keyframe_insert("scale", frame=1)
        g.keyframe_insert("scale", frame=f(t))
        g.scale = (s.x * 0.9, s.y * 0.9, s.z * 1.25)
        g.keyframe_insert("scale", frame=f(t + 0.12))
        g.scale = s
        g.keyframe_insert("scale", frame=f(t + 0.24))
    for g in coches:
        s = g.scale.copy()
        g.scale = (0.001,) * 3
        g.keyframe_insert("scale", frame=1)
        g.keyframe_insert("scale", frame=f(A + 1.5))
        g.scale = s
        g.keyframe_insert("scale", frame=f(A + 1.75))

# giro de la mesa: vuelta entera en bucle; si no, despacio
mesa = bpy.data.objects.new("mesa", None)
escena.collection.objects.link(mesa)
isla.parent = mesa
mesa.keyframe_insert("rotation_euler", frame=1)
# en bucle la vuelta se cierra en FIN + 1 (que es el fotograma 1 otra vez)
mesa.rotation_euler.z = 2 * math.pi if BUCLE else 0.22 * P["duracion"]
mesa.keyframe_insert("rotation_euler", frame=FIN + (1 if BUCLE else 0))
for fc in mesa.animation_data.action.fcurves if hasattr(mesa.animation_data.action, "fcurves") else []:
    for kp in fc.keyframe_points:
        kp.interpolation = "LINEAR"

# ------------------------------------------------------------------ la palabra que flota encima
fuente = os.path.join(AQUI, "..", "fabrica", "fuentes", "Anton.ttf")
letra = bpy.data.fonts.load(fuente) if os.path.isfile(fuente) else None
vertical = P["alto"] > P["ancho"]
texto = str(P.get("texto") or "").strip().upper()[:18]
if texto:
    cu = bpy.data.curves.new("palabra", "FONT")
    cu.body, cu.extrude, cu.align_x, cu.align_y = texto, 0.05, "CENTER", "CENTER"
    cu.bevel_depth = 0.008
    if letra:
        cu.font = letra
    pal = bpy.data.objects.new("palabra", cu)
    escena.collection.objects.link(pal)
    pal.data.materials.append(material("#f4f1ec" if NOCHE else "#1e1c1a", 0.4))
    bpy.context.view_layer.update()
    cu.size = min((1.7 if vertical else 2.4) / max(0.1, pal.dimensions.x), 0.6)
    # en el plano de foco (encima del centro, hacia arriba segun mira la camara): asi sale nitida
    pal.location = (0, 1.0 * math.sin(math.radians(36)), 0.12 + 1.0 * math.cos(math.radians(36)))
    seguir = pal.constraints.new("TRACK_TO")
    pal.scale = (0.001,) * 3
    pal.keyframe_insert("scale", frame=1)
    pal.keyframe_insert("scale", frame=f(A + 1.4))
    pal.scale = (1.12,) * 3
    pal.keyframe_insert("scale", frame=f(A + 1.6))
    pal.scale = (1,) * 3
    pal.keyframe_insert("scale", frame=f(A + 1.8))
    if BUCLE:
        pal.animation_data_clear()
        pal.scale = (1,) * 3

# ------------------------------------------------------------------ luz: sol calido y cielo liso detras
mundo = bpy.data.worlds.new("mundo")
escena.world = mundo
mundo.use_nodes = True
mundo.node_tree.nodes["Background"].inputs["Color"].default_value = hexa(cielo)
mundo.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.55 if NOCHE else 0.9
sol_d = bpy.data.lights.new("sol", "SUN")
sol_d.energy = 0.6 if NOCHE else 3.2
sol_d.color = hexa("#9fb3ff" if NOCHE else "#fff1d8")[:3]
sol_d.angle = math.radians(4)
sol = bpy.data.objects.new("sol", sol_d)
escena.collection.objects.link(sol)
sol.rotation_euler = (math.radians(55), math.radians(10), math.radians(-35))

# ------------------------------------------------------------------ camara de maqueta: desde arriba, tele y desenfoque
cam_d = bpy.data.cameras.new("cam")
cam_d.lens = 85
cam_d.sensor_fit = "HORIZONTAL"
cam_d.dof.use_dof = True
cam = bpy.data.objects.new("cam", cam_d)
escena.collection.objects.link(cam)
escena.camera = cam
diana = bpy.data.objects.new("diana", None)
escena.collection.objects.link(diana)
diana.location = (0, 0, 0.12)
cam_d.dof.focus_object = diana
pista = cam.constraints.new("TRACK_TO")
pista.target, pista.track_axis, pista.up_axis = diana, "TRACK_NEGATIVE_Z", "UP_Y"
if texto:
    seguir.target, seguir.track_axis, seguir.up_axis = cam, "TRACK_Z", "UP_Y"
media = math.atan(cam_d.sensor_width / 2 / cam_d.lens)
d = (1.08 if vertical else 1.75) / math.tan(media)
# poca profundidad de campo para que parezca una maqueta: lo cercano y lo lejano se emborronan
cam_d.dof.aperture_fstop = max(0.6, 0.1 * d)
ELEV = math.radians(36)
for fr, dd in ((1, d * 1.04), (FIN, d * (1.0 if BUCLE else 0.94))):
    cam.location = (0, -dd * math.cos(ELEV), dd * math.sin(ELEV) + 0.12)
    cam.keyframe_insert("location", frame=fr)
if BUCLE:
    cam.animation_data_clear()
    cam.location = (0, -d * math.cos(ELEV), d * math.sin(ELEV) + 0.12)

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
for _ in range(2):   # como en titulo3d: los primeros renders de EEVEE pueden salir sin luz
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
