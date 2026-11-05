"""Escena 3D DE CAPAS (2.5D): los dibujos de Flow (Nano Banana) como tarjetas recortadas a distinta profundidad, con
camara que se mueve (parallax), desenfoque, sombra suave de cada tarjeta y algo de vida (flotar, balanceo). Asi el 3D
tiene la calidad de dibujo de la Fabrica y Blender pone lo que el 2D no tiene: profundidad, luz y camara.

Uso (lo llama app/services/estudio/blender_gen.py):  blender -b --factory-startup -P capas.py -- plano.json
plano.json = {"salida", "ancho", "alto", "fps", "muestras", "duracion", "paso": 1,
              "fondo"?: ruta de una ilustracion (opaca) | "color_fondo"?: "#1d1b3a",
              "capas": [{"img": ruta png/webp con alfa, "x": centro (-0.5..0.5 = de borde a borde en vertical),
                         "z": base (0 = abajo del cuadro, 1 = arriba), "alto": alto (1 = todo el cuadro),
                         "prof": profundidad (0 = plano de foco, 0.6 = mas atras, -0.3 = delante),
                         "a": segundo en que aparece, "entrada": "pop"|"cae"|"sube"|"", "vida": "flota"|"balanceo"|"",
                         "sombra"?: true,
                         "ruta"?: [[segundo, x, z], ...] (recorrido; entre dos puntos da un salto de "salto" de alto),
                         "salto"?: 0.08, "niveles"?: "0379..." (volumen 0-9 por fotograma a "fps": habla = rebota),
                         "boca"?: {"x", "y" (centro, fraccion del dibujo desde su centro / su base), "ancho"} (boca
                                   de pixel negra que se abre con "niveles")}],
              "camara"?: "acercar"|"alejar"|"lateral"|"seguir" (sigue a la capa "foco"), "foco"?: indice, "apertura"?: f-stop}
Escala de maqueta: el cuadro mide 1 de alto a profundidad 0 (asi el desenfoque se nota como en una miniatura).
"""
import json
import math
import os
import sys

import bpy
from mathutils import Vector

P = json.load(open(sys.argv[sys.argv.index("--") + 1], encoding="utf-8"))
FPS = int(P.get("fps", 24))
FIN = max(2, round(P["duracion"] * FPS))
PASO = int(P.get("paso", 1))
os.makedirs(P["salida"], exist_ok=True)

bpy.ops.wm.read_factory_settings(use_empty=True)
escena = bpy.context.scene
escena.frame_start, escena.frame_end, escena.render.fps = 1, FIN, FPS
vertical = P["alto"] >= P["ancho"]
aspecto = P["ancho"] / P["alto"]
f = lambda s: max(1, min(FIN, round(1 + s * FPS)))


def hexa(h, a=1.0):
    h = h.lstrip("#")
    c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return [x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c] + [a]


def material_imagen(nombre, ruta, sombra=False, brillo=0.35):
    """Dibujo con su alfa. sombra=True: la misma silueta en negro y medio transparente (la sombra de la tarjeta)."""
    m = bpy.data.materials.new(nombre)
    m.use_nodes = True
    n, l = m.node_tree.nodes, m.node_tree.links
    p = n["Principled BSDF"]
    img = n.new("ShaderNodeTexImage")
    img.image = bpy.data.images.load(ruta, check_existing=True)
    img.interpolation = "Cubic"
    if sombra:
        p.inputs["Base Color"].default_value = (0, 0, 0, 1)
        mult = n.new("ShaderNodeMath")
        mult.operation, mult.inputs[1].default_value = "MULTIPLY", 0.45
        l.new(img.outputs["Alpha"], mult.inputs[0])
        l.new(mult.outputs["Value"], p.inputs["Alpha"])
    else:
        l.new(img.outputs["Color"], p.inputs["Base Color"])
        l.new(img.outputs["Alpha"], p.inputs["Alpha"])
        # algo de emision: el dibujo conserva sus colores aunque la luz no le de de lleno
        l.new(img.outputs["Color"], p.inputs["Emission Color"])
        p.inputs["Emission Strength"].default_value = brillo
    p.inputs["Roughness"].default_value = 0.75
    for attr, val in (("surface_render_method", "DITHERED"), ("blend_method", "HASHED"), ("use_transparent_shadow", True)):
        try:
            setattr(m, attr, val)
        except (AttributeError, TypeError):
            pass
    return m, img.image


def tarjeta(nombre, ruta, alto, sombra=False):
    """Plano con el dibujo, base en z = 0 y centrado en x (alto en unidades de mundo)."""
    m, im = material_imagen(nombre, ruta, sombra)
    w, h = im.size
    ancho = alto * w / max(1, h)
    bpy.ops.mesh.primitive_plane_add(size=1, location=(0, 0, 0), rotation=(math.radians(90), 0, 0))
    o = bpy.context.object
    o.name = nombre
    bpy.ops.transform.resize(value=(ancho, 1, alto))
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    for v in o.data.vertices:   # base abajo (el plano esta girado 90 grados: su Y local es el alto)
        v.co.y += alto / 2
    o.data.materials.append(m)
    return o, ancho


# ------------------------------------------------------------------ camara (de ella sale la escala de todo)
cam_d = bpy.data.cameras.new("cam")
cam_d.lens = 35
cam_d.sensor_fit = "VERTICAL" if vertical else "HORIZONTAL"
fov = 2 * math.atan((cam_d.sensor_height if vertical else cam_d.sensor_width) / 2 / cam_d.lens)
alto_fov = fov if vertical else 2 * math.atan(math.tan(fov / 2) / aspecto)
D = 0.5 / math.tan(alto_fov / 2)   # a esta distancia el cuadro mide 1 de alto
cam = bpy.data.objects.new("cam", cam_d)
escena.collection.objects.link(cam)
escena.camera = cam
diana = bpy.data.objects.new("diana", None)
escena.collection.objects.link(diana)
pista = cam.constraints.new("TRACK_TO")
pista.target, pista.track_axis, pista.up_axis = diana, "TRACK_NEGATIVE_Z", "UP_Y"
cam_d.clip_start, cam_d.clip_end = 0.01, 100


def escala(prof):
    """Lo que mide 1 a profundidad 0 mide esto a esa profundidad (para que el alto pedido sea el que se VE)."""
    return (D + prof) / D


# ------------------------------------------------------------------ fondo
FONDO_PROF = 2.2
mundo = bpy.data.worlds.new("mundo")
escena.world = mundo
mundo.use_nodes = True
mundo.node_tree.nodes["Background"].inputs["Color"].default_value = hexa(P.get("color_fondo", "#1d1b3a"))
mundo.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.6
if P.get("fondo"):
    k = escala(FONDO_PROF) * 1.35   # con margen: la camara se mueve
    fondo, ancho_f = tarjeta("fondo", P["fondo"], k)
    if ancho_f < k * aspecto:   # que cubra tambien de ancho
        fondo.scale = (k * aspecto / ancho_f,) * 3
    fondo.location = (0, FONDO_PROF, 0.5 - fondo.scale.z * k / 2)
    fondo.active_material.node_tree.nodes["Principled BSDF"].inputs["Emission Strength"].default_value = 0.9

# ------------------------------------------------------------------ capas
capas = []
for i, c in enumerate(P.get("capas") or []):
    prof = float(c.get("prof", 0))
    s = escala(prof)
    alto = float(c.get("alto", 0.4)) * s
    x = float(c.get("x", 0)) * s * aspecto   # x = fraccion del ancho visible
    z = 0.5 + (float(c.get("z", 0)) - 0.5) * s
    raiz = bpy.data.objects.new(f"capa{i}", None)
    escena.collection.objects.link(raiz)
    raiz.location = (x, prof, z)
    o, ancho = tarjeta(f"dibujo{i}", c["img"], alto)
    o.parent = raiz
    if c.get("sombra", True):
        so, _ = tarjeta(f"sombra{i}", c["img"], alto, sombra=True)
        so.parent = raiz
        so.location = (alto * 0.035, 0.015, -alto * 0.03)   # detras, un poco abajo a la derecha
    capas.append({"raiz": raiz, "alto": alto, "ancho": ancho, "prof": prof, "carta": o, "s": s, **c})

# entradas y vida
for c in capas:
    r = c["raiz"]
    a = max(0.0, float(c.get("a", 0)))
    base = r.location.copy()
    entrada = c.get("entrada", "pop")
    if entrada == "pop":
        r.scale = (0, 0, 0)
        r.keyframe_insert("scale", frame=1)
        if a > 0:
            r.keyframe_insert("scale", frame=f(a))
        for t, v in ((0.2, 1.12), (0.34, 0.96), (0.45, 1.0)):
            r.scale = (v, v, v)
            r.keyframe_insert("scale", frame=f(a + t))
    elif entrada in ("cae", "sube"):
        desde = base + Vector((0, 0, (1.4 if entrada == "cae" else -1.2) * escala(c["prof"])))
        r.location = desde
        r.keyframe_insert("location", frame=1)
        if a > 0:
            r.keyframe_insert("location", frame=f(a))
        rebote = c["alto"] * 0.06 * (1 if entrada == "cae" else -1)
        for t, dz in ((0.35, 0), (0.47, rebote), (0.6, 0)):
            r.location = base + Vector((0, 0, dz))
            r.keyframe_insert("location", frame=f(a + t))
    # vida: despues de entrar, flota arriba y abajo o se balancea (en curvas suaves cada 0,5 s)
    vida = c.get("vida", "flota")
    if vida == "flota" and c.get("ruta"):
        vida = ""   # el recorrido ya mueve la posicion
    if vida in ("flota", "balanceo"):
        fase = len(c.get("img", "")) % 7
        t = a + (0.6 if entrada else 0)
        while f(t) < FIN:
            t += 0.5
            k = math.sin(t * 2.1 + fase)
            if vida == "flota":
                r.location = base + Vector((0, 0, k * c["alto"] * 0.025))
                r.keyframe_insert("location", frame=f(t))
            else:
                r.rotation_euler = (0, math.radians(k * 3.5), 0)
                r.keyframe_insert("rotation_euler", frame=f(t))

def mundo_xz(c, x, z):
    """(x, z) de pantalla de una capa (como en "x"/"z") a coordenadas del mundo a su profundidad."""
    return x * c["s"] * aspecto, 0.5 + (z - 0.5) * c["s"]


mat_boca = bpy.data.materials.new("boca")
mat_boca.use_nodes = True
mat_boca.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.01, 0.01, 0.012, 1)
mat_boca.node_tree.nodes["Principled BSDF"].inputs["Roughness"].default_value = 0.6
for c in capas:
    r = c["raiz"]
    # recorrido con saltos: de punto a punto sube "salto" a mitad de camino y cae en el siguiente
    ruta = c.get("ruta") or []
    for k, (t, x, z) in enumerate(ruta):
        wx, wz = mundo_xz(c, x, z)
        r.location = (wx, c["prof"], wz)
        r.keyframe_insert("location", frame=f(t))
        if k + 1 < len(ruta):
            t2, x2, z2 = ruta[k + 1]
            mx, mz = mundo_xz(c, (x + x2) / 2, max(z, z2) + float(c.get("salto", 0.08)))
            r.location = (mx, c["prof"], mz)
            r.keyframe_insert("location", frame=f((t + t2) / 2))
    niveles = c.get("niveles") or ""
    carta = c["carta"]
    boca = None
    if c.get("boca") and niveles:
        b = c["boca"]
        bpy.ops.mesh.primitive_plane_add(size=1)
        boca = bpy.context.object
        boca.data.materials.append(mat_boca)
        boca.parent = carta   # en el plano de la carta: x = ancho, y = alto, z = hacia la camara
        boca.location = (float(b.get("x", 0)) * c["ancho"], float(b.get("y", 0.35)) * c["alto"], 0.002)
        c["boca_ancho"] = float(b.get("ancho", 0.18)) * c["ancho"]
    # habla: con el volumen de cada fotograma el cuerpo se estira un poco y la boca se abre
    for fr in range(1, FIN + 1, PASO):
        if not niveles:
            break
        lv = int(niveles[min(len(niveles) - 1, fr - 1)]) / 9
        carta.scale = (1 - 0.03 * lv, 1 + 0.06 * lv, 1)
        carta.keyframe_insert("scale", frame=fr)
        if boca:
            w = c["boca_ancho"]
            boca.scale = (w, w * (0.1 + 0.55 * lv), 1)
            boca.keyframe_insert("scale", frame=fr)

# ------------------------------------------------------------------ luz: clave calida, relleno frio
for nombre, pos, energia, col in (("clave", (-1.2, -1.6, 1.8), 120, "#fff1dc"), ("relleno", (1.4, -1.2, 0.6), 40, "#dde8ff")):
    d = bpy.data.lights.new(nombre, "AREA")
    d.energy, d.size, d.color = energia, 1.5, hexa(col)[:3]
    o = bpy.data.objects.new(nombre, d)
    escena.collection.objects.link(o)
    o.location = pos
    o.rotation_euler = (Vector((0, 0, 0.5)) - Vector(pos)).to_track_quat("-Z", "Y").to_euler()

# ------------------------------------------------------------------ movimiento de camara (parallax) y foco
foco = capas[int(P.get("foco", 0))] if capas and int(P.get("foco", 0)) < len(capas) else None
diana.location = (0, foco["prof"] if foco else 0, 0.5)
cam_d.dof.use_dof = True
cam_d.dof.focus_object = diana
cam_d.dof.aperture_fstop = float(P.get("apertura", 1.4))
mov = P.get("camara", "acercar")
if mov == "seguir" and foco and foco.get("ruta"):
    # va detras del personaje por su recorrido (un poco por detras: se le ve avanzar)
    for t, x, z in foco["ruta"]:
        wx, _ = mundo_xz(foco, x, z)
        cam.location = (wx * 0.75, -D * 1.02, 0.5)
        cam.keyframe_insert("location", frame=f(t))
        diana.location.x = wx * 0.75
        diana.keyframe_insert("location", frame=f(t))
    mov = "ninguno"
tramos = {"acercar": ((0.04, -D * 1.12, 0.52), (-0.04, -D * 0.94, 0.5)),
          "alejar": ((0.0, -D * 0.82, 0.5), (0.03, -D * 1.05, 0.52)),
          "lateral": ((-0.14, -D, 0.5), (0.14, -D, 0.5))}.get(mov, ((0.04, -D * 1.12, 0.52), (-0.04, -D * 0.94, 0.5)))
for fr, (x, y, z) in (() if mov == "ninguno" else ((1, tramos[0]), (FIN, tramos[1]))):
    cam.location = (x, y, z)
    cam.keyframe_insert("location", frame=fr)
    diana.location.x = x * 0.3
    diana.keyframe_insert("location", frame=fr)

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
# EEVEE saca a veces el segundo render de la sesion sin luz: dos de calentamiento que no se guardan
r.filepath = os.path.join(P["salida"], "_calentar.png")
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
