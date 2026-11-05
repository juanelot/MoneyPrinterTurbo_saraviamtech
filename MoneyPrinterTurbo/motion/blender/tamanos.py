"""Escena 3D COMPARAR TAMANOS: objetos de menor a mayor en fila, cada uno aparece al decirse y la camara se aleja
para que entre todo (el formato "size comparison"). Medidas reales: un modelo de Poly Haven se escala a su alto y las
formas del kit (persona, edificio, planetas...) se dibujan con codigo.

Uso (lo llama app/services/estudio/blender_gen.py):  blender -b --factory-startup -P tamanos.py -- plano.json
plano.json = {"salida", "ancho", "alto", "fps", "muestras", "duracion", "paso": 1,
              "objetos": [{"nombre": "Torre Eiffel", "texto": "330 m", "modelo": id|forma, "ruta"?: .gltf,
                           "alto_m": 330, "a": segundo en que aparece}], "fondo"?: "#cfe6f5", "semilla"?}
Todo cabe a cualquier escala (de una hormiga al Sol): la camara recorta cerca y lejos segun lo que encuadra.
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
azar = random.Random(P.get("semilla", 7))

bpy.ops.wm.read_factory_settings(use_empty=True)
escena = bpy.context.scene
escena.frame_start, escena.frame_end, escena.render.fps = 1, FIN, FPS


def hexa(h, a=1.0):
    h = h.lstrip("#")
    c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return [x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c] + [a]


def material(nombre, color, rugosidad=0.6, emision=0.0, ruido=None):
    m = bpy.data.materials.new(nombre)
    m.use_nodes = True
    n, l = m.node_tree.nodes, m.node_tree.links
    p = n["Principled BSDF"]
    p.inputs["Roughness"].default_value = rugosidad
    if ruido:   # planetas y montanas: mezcla de dos colores con ruido
        coord = n.new("ShaderNodeTexCoord")
        r = n.new("ShaderNodeTexNoise")
        r.inputs["Scale"].default_value = ruido[2]
        r.inputs["Detail"].default_value = 8
        rampa = n.new("ShaderNodeValToRGB")
        rampa.color_ramp.elements[0].color = hexa(ruido[0])
        rampa.color_ramp.elements[1].color = hexa(ruido[1])
        rampa.color_ramp.elements[0].position, rampa.color_ramp.elements[1].position = 0.45, 0.55
        l.new(coord.outputs["Object"], r.inputs["Vector"])
        l.new(r.outputs["Fac"], rampa.inputs["Fac"])
        l.new(rampa.outputs["Color"], p.inputs["Base Color"])
        if emision:
            l.new(rampa.outputs["Color"], p.inputs["Emission Color"])
    else:
        p.inputs["Base Color"].default_value = hexa(color)
        if emision:
            p.inputs["Emission Color"].default_value = hexa(color)
    if emision:
        p.inputs["Emission Strength"].default_value = emision
    return m


def suave(o, nivel=2):
    o.modifiers.new("sub", "SUBSURF").levels = nivel
    o.modifiers["sub"].render_levels = nivel
    for pol in o.data.polygons:
        pol.use_smooth = True
    return o


def prim(tipo, pos, esc, mat, rot=(0, 0, 0), **kw):
    getattr(bpy.ops.mesh, f"primitive_{tipo}_add")(location=pos, rotation=rot, **kw)
    o = bpy.context.object
    o.scale = esc
    o.data.materials.append(mat)
    return o


def grupo(nombre, partes):
    g = bpy.data.objects.new(nombre, None)
    escena.collection.objects.link(g)
    for o in partes:
        o.parent = g
    return g


# ------------------------------------------------------------------ formas del kit (alto 1, base en z = 0)
def forma(tipo, color):
    c = lambda n, col, **kw: material(n, col, **kw)
    if tipo == "persona":
        piel, ropa, pant = c("piel", "#e9b48f"), c("ropa", color or "#2f5d8a"), c("pantalon", "#2b2b33")
        partes = [prim("cylinder", (x, 0, 0.24), (0.06, 0.06, 0.24), pant, vertices=16) for x in (-0.07, 0.07)]
        tronco = prim("cylinder", (0, 0, 0.64), (0.15, 0.09, 0.18), ropa, vertices=24)
        bisel = tronco.modifiers.new("bisel", "BEVEL")
        bisel.width, bisel.segments = 0.4, 4
        partes.append(tronco)
        partes += [prim("cylinder", (x, 0, 0.62), (0.042, 0.042, 0.19), ropa, rot=(0, r, 0), vertices=16)
                   for x, r in ((-0.185, -0.12), (0.185, 0.12))]
        partes += [prim("uv_sphere", (x, 0, 0.42), (0.045, 0.045, 0.045), piel) for x in (-0.205, 0.205)]
        partes.append(prim("uv_sphere", (0, 0, 0.9), (0.1, 0.1, 0.11), piel, segments=24, ring_count=12))
        return grupo("persona", partes)
    if tipo == "hormiga":
        negro = c("hormiga", "#2a1a12", rugosidad=0.3)
        partes = [prim("uv_sphere", (x, 0, 0.5), (s, s * 0.8, s * 0.8), negro) for x, s in ((-0.9, 0.45), (0, 0.3), (0.7, 0.35))]
        for x in (-0.3, 0, 0.3):
            for lado in (-1, 1):
                partes.append(prim("cylinder", (x, lado * 0.45, 0.25), (0.04, 0.04, 0.35), negro, rot=(lado * 0.9, 0, 0), vertices=8))
        g = grupo("hormiga", partes)
        return g
    if tipo == "coche":
        car = c("carroceria", color or "#d7372c", rugosidad=0.25)
        partes = [suave(prim("cube", (0, 0, 0.45), (1.4, 0.75, 0.28), car), 1), suave(prim("cube", (-0.1, 0, 0.82), (0.8, 0.65, 0.22), car), 1)]
        rueda = c("rueda", "#1b1b1b")
        partes += [prim("cylinder", (x, y, 0.3), (0.3, 0.3, 0.12), rueda, rot=(math.pi / 2, 0, 0), vertices=24)
                   for x in (-0.85, 0.85) for y in (-0.72, 0.72)]
        return grupo("coche", partes)
    if tipo in ("casa", "edificio", "rascacielos", "torre"):
        ancho = {"casa": 0.9, "edificio": 0.35, "rascacielos": 0.16, "torre": 0.2}[tipo]
        m = bpy.data.materials.new("fachada")
        m.use_nodes = True
        n, l = m.node_tree.nodes, m.node_tree.links
        ladrillo = n.new("ShaderNodeTexBrick")   # las ventanas: una rejilla de "ladrillos" claros sobre la fachada
        ladrillo.inputs["Color1"].default_value = hexa("#bcd6ea")
        ladrillo.inputs["Color2"].default_value = hexa("#a9c4da")
        ladrillo.inputs["Mortar"].default_value = hexa(color or "#8d97a5")
        ladrillo.inputs["Scale"].default_value = 18 if tipo != "casa" else 4
        ladrillo.inputs["Mortar Size"].default_value = 0.08
        ladrillo.offset = 0
        coord = n.new("ShaderNodeTexCoord")
        l.new(coord.outputs["Generated"], ladrillo.inputs["Vector"])
        l.new(ladrillo.outputs["Color"], n["Principled BSDF"].inputs["Base Color"])
        if tipo == "torre":
            partes = [prim("cone", (0, 0, 0.5), (0.5, 0.5, 0.5), c("metal", color or "#7a5c3e", rugosidad=0.4), vertices=4)]
        else:
            cuerpo = prim("cube", (0, 0, 0.5), (ancho, ancho, 0.5), m)
            partes = [cuerpo]
            if tipo == "casa":
                partes.append(prim("cone", (0, 0, 1.25), (0.95, 0.95, 0.3), c("tejado", "#b5523a"), vertices=4, rot=(0, 0, math.pi / 4)))
                partes[0].scale = (ancho, ancho, 0.5)
        return grupo(tipo, partes)
    if tipo == "arbol":
        partes = [prim("cylinder", (0, 0, 0.2), (0.05, 0.05, 0.2), c("tronco", "#7a5133"), vertices=12),
                  suave(prim("ico_sphere", (0, 0, 0.62), (0.3, 0.3, 0.38), c("copa", color or "#4f8a4b")), 1)]
        return grupo("arbol", partes)
    if tipo == "montana":
        mon = prim("cone", (0, 0, 0.5), (1.1, 1.1, 0.5), material("roca", "", ruido=("#6f6559", "#f4f4f6", 3.0)), vertices=64)
        mon.modifiers.new("sub", "SUBSURF").levels = 3
        tex = bpy.data.textures.new("relieve", "CLOUDS")
        tex.noise_scale = 0.25
        d = mon.modifiers.new("relieve", "DISPLACE")
        d.texture, d.strength = tex, 0.08
        return grupo("montana", [mon])
    if tipo == "nube":
        blanco = c("nube", "#ffffff", rugosidad=1.0)
        return grupo("nube", [suave(prim("uv_sphere", (x, 0, 0.5 + z), (s, s * 0.7, s * 0.6), blanco), 1)
                              for x, z, s in ((-0.5, 0, 0.45), (0, 0.15, 0.55), (0.5, 0, 0.4))])
    if tipo in ("luna", "tierra", "marte", "jupiter", "sol"):
        colores = {"luna": ("#77757a", "#c9c7c4", 6), "tierra": ("#1f5fb0", "#3f8a45", 2.2), "marte": ("#8e3b1f", "#d0754a", 4),
                   "jupiter": ("#b98e62", "#efdcc0", 1.4), "sol": ("#ff8a1c", "#ffd34d", 3)}[tipo]
        esfera = prim("uv_sphere", (0, 0, 0.5), (0.5, 0.5, 0.5), material(tipo, "", rugosidad=0.8, emision=4.0 if tipo == "sol" else 0,
                                                                          ruido=colores), segments=64, ring_count=32)
        for pol in esfera.data.polygons:
            pol.use_smooth = True
        return grupo(tipo, [esfera])
    if tipo == "estrella":   # Betelgeuse, Sirio...: brilla con su color (rojo-naranja si no se dice)
        e = prim("uv_sphere", (0, 0, 0.5), (0.5, 0.5, 0.5), material("estrella", "", rugosidad=0.8, emision=3.0,
                                                                     ruido=(color or "#e2412b", "#ffd9a0", 3)),
                 segments=64, ring_count=32)
        for pol in e.data.polygons:
            pol.use_smooth = True
        return grupo("estrella", [e])
    if tipo == "esfera":
        e = prim("uv_sphere", (0, 0, 0.5), (0.5, 0.5, 0.5), c("esfera", color or "#e0a92e", rugosidad=0.3), segments=48, ring_count=24)
        for pol in e.data.polygons:
            pol.use_smooth = True
        return grupo("esfera", [e])
    return grupo("cubo", [suave(prim("cube", (0, 0, 0.5), (0.5, 0.5, 0.5), c("cubo", color or "#4f8fcb", rugosidad=0.3)), 1)])


def importar(ruta):
    """Un modelo glTF de Poly Haven bajo un vacio, con la base en z = 0 y centrado."""
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
    """(min, max) del grupo en coordenadas del mundo."""
    bpy.context.view_layer.update()
    pts = [o.matrix_world @ Vector(c) for o in g.children_recursive if o.type == "MESH" for c in o.bound_box]
    lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    return lo, hi


# ------------------------------------------------------------------ montar la fila
objetos = []
for k, ob in enumerate(P["objetos"]):
    g = importar(ob["ruta"]) if ob.get("ruta") else forma(ob["modelo"], ob.get("color"))
    lo, hi = caja(g)
    alto = max(1e-6, hi.z - lo.z)
    s = float(ob["alto_m"]) / alto
    g.scale = (s, s, s)
    lo, hi = caja(g)
    g.location -= Vector(((lo.x + hi.x) / 2, (lo.y + hi.y) / 2, lo.z))   # centrado y apoyado en el suelo
    lo, hi = caja(g)
    objetos.append({"g": g, "ancho": hi.x - lo.x, "fondo": hi.y - lo.y, "alto": hi.z - lo.z, "s": s, **ob})
# de izquierda a derecha, con un hueco proporcional al mayor de cada pareja
x = 0.0
for k, o in enumerate(objetos):
    if k:
        prev = objetos[k - 1]
        x += prev["ancho"] / 2 + o["ancho"] / 2 + 0.35 * max(prev["ancho"], o["ancho"], 0.3 * o["alto"])
    o["x"] = x
    o["g"].location.x += x

# rotulo encima de cada uno: nombre y medida, a su escala
fuente = os.path.join(AQUI, "..", "fabrica", "fuentes", "Anton.ttf")
letra = bpy.data.fonts.load(fuente) if os.path.isfile(fuente) else None
mat_letra = material("letra", "#1e1c1a", rugosidad=0.8)
for o in objetos:
    tam = min(max(o["alto"], o["ancho"]), o["alto"] * 1.2) * 0.14
    o["tam_rotulo"] = tam
    for fila, txt in enumerate((o.get("nombre") or "", o.get("texto") or "")):
        if not txt:
            continue
        cu = bpy.data.curves.new("rotulo", "FONT")
        cu.body, cu.size, cu.align_x, cu.align_y = txt.upper(), tam * (1 if fila == 0 else 0.75), "CENTER", "BOTTOM"
        if letra:
            cu.font = letra
        t = bpy.data.objects.new("rotulo", cu)
        escena.collection.objects.link(t)
        t.location = (o["x"], -o["fondo"] / 2 - tam * 0.2, o["alto"] + tam * (1.05 if fila == 0 else 0.15))
        t.rotation_euler = (math.radians(90), 0, 0)
        t.data.materials.append(mat_letra)
        t.parent = o["g"]
        t.matrix_parent_inverse = o["g"].matrix_world.inverted()
        o.setdefault("rotulos", []).append(t)

# aparecen al decirse: escalan desde 0 con rebote
f = lambda s: max(1, min(FIN, round(1 + s * FPS)))
for o in objetos:
    a = max(0.0, float(o.get("a", 0)))
    g = o["g"]
    final = g.scale.copy()
    g.scale = (0, 0, 0)
    g.keyframe_insert("scale", frame=1)
    if a > 0:
        g.keyframe_insert("scale", frame=f(a))
    g.scale = final * 1.12
    g.keyframe_insert("scale", frame=f(a + 0.22))
    g.scale = final
    g.keyframe_insert("scale", frame=f(a + 0.4))

# suelo enorme, cielo y sol (la luz del sol no depende de la escala)
mayor = max(max(o["alto"], o["ancho"]) for o in objetos)
# el suelo sigue a la camara y crece con su distancia: un plano fijo de miles de km pierde precision de profundidad
# y "tapa" lo pequeno que esta cerca
bpy.ops.mesh.primitive_plane_add(size=1, location=(0, 0, 0))
suelo = bpy.context.object
suelo.data.materials.append(material("suelo", P.get("suelo", "#cfc6b4"), rugosidad=0.95))
mundo = bpy.data.worlds.new("mundo")
escena.world = mundo
mundo.use_nodes = True
mundo.node_tree.nodes["Background"].inputs["Color"].default_value = hexa(P.get("fondo", "#cfe6f5"))
mundo.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.9
sol = bpy.data.lights.new("sol", "SUN")
sol.energy, sol.angle = 2.4, math.radians(6)
luz = bpy.data.objects.new("sol", sol)
escena.collection.objects.link(luz)
luz.rotation_euler = (math.radians(50), math.radians(-25), math.radians(35))

# ------------------------------------------------------------------ camara: encuadra lo que ya ha salido
vertical = P["alto"] > P["ancho"]
cam_d = bpy.data.cameras.new("cam")
cam_d.lens = 35
cam_d.sensor_fit = "VERTICAL" if vertical else "HORIZONTAL"
cam = bpy.data.objects.new("cam", cam_d)
escena.collection.objects.link(cam)
escena.camera = cam
diana = bpy.data.objects.new("diana", None)
escena.collection.objects.link(diana)
pista = cam.constraints.new("TRACK_TO")
pista.target, pista.track_axis, pista.up_axis = diana, "TRACK_NEGATIVE_Z", "UP_Y"
fov = 2 * math.atan(cam_d.sensor_height / 2 / cam_d.lens) if vertical else 2 * math.atan(cam_d.sensor_width / 2 / cam_d.lens)
aspecto = P["ancho"] / P["alto"]


def toma(sel):
    """Posicion de camara y diana para que entren esos objetos (con sus rotulos)."""
    x0 = min(o["x"] - o["ancho"] / 2 for o in sel)
    x1 = max(o["x"] + o["ancho"] / 2 for o in sel)
    z1 = max(o["alto"] + o.get("tam_rotulo", 0) * 2.6 for o in sel)   # el rotulo va encima
    cx, cz = (x0 + x1) / 2, z1 / 2
    ancho, alto = (x1 - x0) * 1.15, z1 * 1.15
    # lo que manda es lo que menos cabe: el alto en vertical, el ancho en horizontal
    medio = max(alto / 2, ancho / 2 / aspecto) if vertical else max(ancho / 2, alto / 2 * aspecto)
    d = medio / math.tan(fov / 2)
    return Vector((cx, -d, cz + d * 0.12)), Vector((cx, 0, cz * 0.9)), d


# marcador: lo que queda diminuto al lado de algo enorme (la Tierra junto al Sol) se pierde, asi que lleva una flecha
# y su nombre a tamano de PANTALLA (no del objeto). Origen en lo alto del objeto; se escala por encuadre en clavar()
mat_flecha = material("flecha", "#e2412b", rugosidad=0.5)
for o in objetos:
    partes = [prim("cone", (0, 0, 0.9), (0.45, 0.45, 0.7), mat_flecha, rot=(math.pi, 0, 0), vertices=24)]
    for fila, txt in enumerate((o.get("nombre") or "", o.get("texto") or "")):
        if not txt:
            continue
        cu = bpy.data.curves.new("marca", "FONT")
        cu.body, cu.size, cu.align_x, cu.align_y = txt.upper(), 1.0 if fila == 0 else 0.7, "CENTER", "BOTTOM"
        if letra:
            cu.font = letra
        t = bpy.data.objects.new("marca", cu)
        escena.collection.objects.link(t)
        t.location, t.rotation_euler = (0, 0, 1.75 + (0.75 if fila == 0 else 0)), (math.radians(90), 0, 0)
        t.data.materials.append(mat_letra)
        partes.append(t)
    m = grupo("marcador", partes)
    m.location = (o["x"], -o["fondo"] / 2, o["alto"])
    m.scale = (0, 0, 0)
    m.keyframe_insert("scale", frame=1)
    o["marcador"] = m


def alto_visible(d):
    """Alto del mundo que entra en pantalla a esa distancia."""
    return 2 * d * math.tan(fov / 2) / (1 if vertical else aspecto)


def clavar(fr, sel):
    pos, mira, d = toma(sel)
    cam.location, diana.location = pos, mira
    cam_d.clip_start, cam_d.clip_end = d * 0.002, d * 500
    suelo.location, suelo.scale = (pos.x, d * 60, 0), (d * 400, d * 400, 1)
    for ob, prop in ((cam, "location"), (diana, "location"), (cam_d, "clip_start"), (cam_d, "clip_end"),
                     (suelo, "location"), (suelo, "scale")):
        ob.keyframe_insert(prop, frame=fr)
    pantalla = alto_visible(d)
    for o in objetos:
        diminuto = o in sel and o["alto"] < pantalla * 0.06
        u = pantalla * 0.035 if diminuto else 0
        o["marcador"].scale = (u, u, u)
        o["marcador"].keyframe_insert("scale", frame=fr)
    return pos, d


# en el orden en que SE NOMBRAN (no por tamano): al salir cada uno la camara sigue en el encuadre anterior y en 0,9 s
# se mueve hasta que entra todo lo que ya ha salido
orden = sorted(objetos, key=lambda o: float(o.get("a", 0)))
pos, d = clavar(1, orden[:1])
for k in range(1, len(orden)):
    a = max(0.0, float(orden[k].get("a", 0)))
    if f(a) > 1:
        clavar(f(a), orden[:k])
    pos, d = clavar(min(FIN, f(a + 0.9)), orden[:k + 1])
# deriva final: se sigue alejando despacio (nunca se para)
if FIN > f(float(orden[-1].get("a", 0)) + 0.9):
    cam.location = pos + Vector((0, -d * 0.08, d * 0.02))
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
