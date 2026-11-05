"""Kit de Blender: monta UN plano (personaje + escenario + objetos + camara) desde un JSON y renderiza sus poses.

Uso (lo llama app/services/estudio/blender_gen.py):
  blender -b --factory-startup -P kit.py -- plano.json

plano.json = {
  "salida": carpeta de los PNG (f_0001.png, f_0003.png... una pose de cada dos fotogramas: "animado en doses"),
  "ancho", "alto", "fps": 24, "muestras": 24, "duracion": segundos,
  "personaje": {"forma": huevo|cubo|gota|gato|perro|oso|conejo|robot|taza|moneda|bombilla, "color": "#f2b33d", "material": barro|plastico|vinilo|peluche,
                "accesorio": ""|gorro|pajarita|gafas|corona},
  "escenario": mesa|cuarto|exterior, "camara": general|medio|primer|contrapicado,
  "gesto": habla|saluda|salta|senala|piensa|sorprendido|triste|baila|camina|celebra,
  "cara": una expresion de caras.py, "boca": "0123..." (un digito por fotograma de 24 fps, del volumen de la voz;
          vacio = la boca de la expresion), "objetos": [{"tipo": cartel|libro|caja|moneda|planta|taza|grafico,
          "texto"?: "...", "color"?: "#hex"}] (2 como mucho, se colocan solos a los lados)
}
Todo sale de primitivas (esferas, cubos, cilindros) con modificadores: rapido de montar y de renderizar sin GPU.
"""
import json
import math
import os
import random
import sys

import bpy
from mathutils import Matrix, Vector

AQUI = os.path.dirname(os.path.abspath(__file__))
P = json.load(open(sys.argv[sys.argv.index("--") + 1], encoding="utf-8"))
FPS = int(P.get("fps", 24))
FIN = max(2, round(P["duracion"] * FPS))
os.makedirs(P["salida"], exist_ok=True)
azar = random.Random(P.get("semilla", 7))

bpy.ops.wm.read_factory_settings(use_empty=True)
escena = bpy.context.scene
escena.frame_start, escena.frame_end, escena.render.fps = 1, FIN, FPS


def hexa(h, a=1.0):
    h = h.lstrip("#")
    c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return [x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c] + [a]


# ------------------------------------------------------------------ materiales
MATERIAL = P["personaje"].get("material", "barro")
hervor = bpy.data.objects.new("hervor", None)   # el "boil" del barro: la textura de grumos salta en cada pose
escena.collection.objects.link(hervor)
grumos = bpy.data.textures.new("grumos", "CLOUDS")
grumos.noise_scale = 0.35


def material(nombre, color, tipo=None):
    tipo = tipo or MATERIAL
    m = bpy.data.materials.new(nombre)
    m.use_nodes = True
    n, l = m.node_tree.nodes, m.node_tree.links
    p = n["Principled BSDF"]
    p.inputs["Base Color"].default_value = hexa(color)
    rugosidad = {"barro": 0.85, "plastico": 0.22, "vinilo": 0.45, "peluche": 1.0, "mate": 0.7}[tipo]
    p.inputs["Roughness"].default_value = rugosidad
    if tipo in ("barro", "vinilo"):
        p.inputs["Subsurface Weight"].default_value = 0.1
        p.inputs["Subsurface Radius"].default_value = (0.4, 0.2, 0.1)
        p.inputs["Subsurface Scale"].default_value = 0.05
    if tipo == "vinilo":
        p.inputs["Coat Weight"].default_value = 0.35
    if tipo == "peluche":
        p.inputs["Sheen Weight"].default_value = 1.0
        p.inputs["Sheen Roughness"].default_value = 0.4
    if tipo in ("barro", "peluche"):
        coord = n.new("ShaderNodeTexCoord")
        ruido = n.new("ShaderNodeTexNoise")
        ruido.inputs["Scale"].default_value = 22 if tipo == "barro" else 180
        ruido.inputs["Detail"].default_value = 6
        l.new(coord.outputs["Object"], ruido.inputs["Vector"])
        alto = ruido.outputs["Fac"]
        if tipo == "barro":   # marcas de dedo
            huella = n.new("ShaderNodeTexVoronoi")
            huella.inputs["Scale"].default_value = 9
            l.new(coord.outputs["Object"], huella.inputs["Vector"])
            suma = n.new("ShaderNodeMath")
            suma.operation = "ADD"
            l.new(ruido.outputs["Fac"], suma.inputs[0])
            l.new(huella.outputs["Distance"], suma.inputs[1])
            alto = suma.outputs["Value"]
        bump = n.new("ShaderNodeBump")
        bump.inputs["Strength"].default_value = 0.18 if tipo == "barro" else 0.5
        bump.inputs["Distance"].default_value = 0.02 if tipo == "barro" else 0.004
        l.new(alto, bump.inputs["Height"])
        l.new(bump.outputs["Normal"], p.inputs["Normal"])
    return m


def acabar(o, mat, sub=2, grumo=None):
    o.data.materials.append(mat)
    if sub:
        o.modifiers.new("sub", "SUBSURF").levels = sub
        o.modifiers["sub"].render_levels = sub
    grumo = (0.012 if MATERIAL == "barro" else 0.0) if grumo is None else grumo
    if grumo:
        d = o.modifiers.new("grumo", "DISPLACE")
        d.texture, d.texture_coords, d.texture_coords_object = grumos, "OBJECT", hervor
        d.strength, d.mid_level = grumo, 0.5
    for pol in getattr(o.data, "polygons", []):
        pol.use_smooth = True
    return o


def esfera(nombre, pos, esc, mat, **kw):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=24, ring_count=12, radius=1, location=pos)
    o = bpy.context.object
    o.name, o.scale = nombre, esc
    return acabar(o, mat, **kw)


def caja(nombre, pos, tam, mat, **kw):
    bpy.ops.mesh.primitive_cube_add(size=1, location=pos)
    o = bpy.context.object
    o.name, o.scale = nombre, tam
    bev = o.modifiers.new("bisel", "BEVEL")
    bev.width, bev.segments, bev.affect = min(tam) * 0.18, 3, "EDGES"
    return acabar(o, mat, sub=kw.pop("sub", 0), **kw)


def cilindro(nombre, pos, radio, alto, mat, **kw):
    bpy.ops.mesh.primitive_cylinder_add(vertices=24, radius=radio, depth=alto, location=pos)
    o = bpy.context.object
    o.name = nombre
    o.data.transform(Matrix.Translation((0, 0, alto / 2)))   # origen en la base
    bev = o.modifiers.new("bisel", "BEVEL")
    bev.width, bev.segments = min(radio, alto) * 0.2, 3
    return acabar(o, mat, sub=kw.pop("sub", 0), **kw)


def texto(cuerpo, pos, tam, color, rot=(math.radians(90), 0, 0)):
    c = bpy.data.curves.new("texto", "FONT")
    c.body, c.size, c.extrude, c.align_x, c.align_y = cuerpo, tam, tam * 0.06, "CENTER", "CENTER"
    fuente = os.path.join(AQUI, "..", "fabrica", "fuentes", "Anton.ttf")
    if os.path.isfile(fuente):
        c.font = bpy.data.fonts.load(fuente)
    o = bpy.data.objects.new("texto", c)
    escena.collection.objects.link(o)
    o.location, o.rotation_euler = pos, rot
    o.data.materials.append(material("letra", color, "mate"))
    return o


def hijo(o, padre):
    o.parent = padre
    o.matrix_parent_inverse = padre.matrix_world.inverted()


def clave(o, f, **props):
    for k, v in props.items():
        setattr(o, k, v)
        o.keyframe_insert(k, frame=f)


# ------------------------------------------------------------------ escenario
ESC = P.get("escenario", "mesa")
FONDOS = {"mesa": ("#c9a27a", "#e9dcc6", "#f4e6d0"), "cuarto": ("#b98c6a", "#d8e2e6", "#e8eef0"),
          "exterior": ("#9cc27a", "#bfe3f2", "#cfeaf7")}
suelo_c, pared_c, cielo_c = FONDOS.get(ESC, FONDOS["mesa"])
bpy.ops.mesh.primitive_plane_add(size=12, location=(0, 2, 0))
acabar(bpy.context.object, material("suelo", suelo_c, "barro" if MATERIAL == "barro" else "mate"), sub=0, grumo=0)
if ESC != "exterior":
    bpy.ops.mesh.primitive_plane_add(size=12, location=(0, 3.2, 3), rotation=(math.radians(90), 0, 0))
    acabar(bpy.context.object, material("pared", pared_c, "mate"), sub=0, grumo=0)
if ESC == "mesa":
    taza = cilindro("taza", (-1.25, 1.6, 0), 0.16, 0.26, material("taza", "#f4f1ec"))
    libros = [caja("libro", (1.35, 1.7, 0.06 + k * 0.12), (0.62, 0.38, 0.11), material("libro", c)) for k, c in enumerate(("#4f8fcb", "#d7372c", "#e0a92e"))]
elif ESC == "cuarto":
    ventana = caja("ventana", (-1.0, 3.15, 1.35), (1.0, 0.04, 0.8), material("marco", "#f4f1ec", "mate"), grumo=0)
    luzv = bpy.data.materials.new("cristal")
    luzv.use_nodes = True
    luzv.node_tree.nodes["Principled BSDF"].inputs["Emission Color"].default_value = hexa("#fff2d6")
    luzv.node_tree.nodes["Principled BSDF"].inputs["Emission Strength"].default_value = 2.0
    bpy.ops.mesh.primitive_plane_add(size=1, location=(-1.0, 3.1, 1.35), rotation=(math.radians(90), 0, 0))
    bpy.context.object.scale = (0.85, 0.65, 1)
    bpy.context.object.data.materials.append(luzv)
    caja("alfombra", (0, 0.4, 0.005), (2.2, 1.4, 0.01), material("alfombra", "#d9772b", "peluche"), grumo=0)
    caja("estante", (1.4, 3.0, 1.1), (0.9, 0.25, 0.06), material("estante", "#8a6a4f"), grumo=0)
else:
    for x, y, s in ((-1.9, 2.4, 1.0), (1.8, 2.8, 1.25), (-0.6, 4.0, 0.9)):
        cilindro("tronco", (x, y, 0), 0.08 * s, 0.5 * s, material("tronco", "#8a5a3c"))
        esfera("copa", (x, y, 0.75 * s), (0.42 * s, 0.42 * s, 0.5 * s), material("copa", "#5e9e4e"))
    for x, z in ((-1.5, 2.6), (1.2, 2.9)):
        esfera("nube", (x, 6, z), (0.6, 0.2, 0.25), material("nube", "#ffffff", "mate"), grumo=0)

# ------------------------------------------------------------------ personaje
PJ = P["personaje"]
mat_pj = material("cuerpo", PJ.get("color", "#f2b33d"))
raiz = bpy.data.objects.new("muneco", None)
escena.collection.objects.link(raiz)
forma = PJ.get("forma", "huevo")
ALTO_PJ = 0.32
PLANO = False      # frente plano (la cara se pega sin adaptarse a una curva)
tope = 0.64        # donde va el gorro o la corona (0 = la forma ya lleva algo arriba)
extras = []        # piezas propias de la forma (orejas, asa, antena...): cuelgan del muneco
color_pj = PJ.get("color", "#f2b33d")


def tono(c, k):
    """Mas claro (k > 0, hacia blanco) o mas oscuro (k < 0) que el color c."""
    v = [int(c[i:i + 2], 16) for i in (1, 3, 5)]
    v = [x + (255 - x) * k if k > 0 else x * (1 + k) for x in v]
    return "#" + "".join(f"{round(x):02x}" for x in v)


def brillo(m, color, fuerza):
    p = m.node_tree.nodes["Principled BSDF"]
    p.inputs["Emission Color"].default_value = hexa(color)
    p.inputs["Emission Strength"].default_value = fuerza
    return m


if forma in ("cubo", "robot"):
    if forma == "robot":   # metal pintado con brillo
        mat_pj = material("cuerpo", color_pj, "plastico")
        mat_pj.node_tree.nodes["Principled BSDF"].inputs["Metallic"].default_value = 0.6
    cuerpo = caja("cuerpo", (0, 0, 0.3), (0.5, 0.42, 0.48), mat_pj, sub=1 if forma == "cubo" else 0)
    frente_y, cara_z, tope, PLANO = -0.215, 0.33, 0.56, True
    if forma == "robot":
        # pantalla donde va la cara, antena con luz y tuercas a los lados
        extras.append(caja("pantalla", (0, frente_y - 0.004, cara_z - 0.03), (0.4, 0.02, 0.3),
                           brillo(material("pantalla", "#cdeefc", "plastico"), "#cdeefc", 0.5), grumo=0))   # LCD clara: se ve la cara
        frente_y -= 0.014
        metal = material("metal", "#9aa0a8", "plastico")
        extras.append(cilindro("antena", (0, 0, 0.53), 0.012, 0.16, metal, grumo=0))
        extras.append(esfera("luz", (0, 0, 0.71), (0.035, 0.035, 0.035), brillo(material("luz", "#ff4d3d", "plastico"), "#ff4d3d", 4.0),
                             sub=1, grumo=0))
        for x in (-0.255, 0.255):
            t = cilindro("tuerca", (x, 0, 0.3), 0.05, 0.03, metal, grumo=0)
            t.rotation_euler = (0, math.radians(90), 0)
            extras.append(t)
        tope = 0.0
elif forma == "moneda":
    mat_pj = material("cuerpo", color_pj, "plastico")
    mat_pj.node_tree.nodes["Principled BSDF"].inputs["Metallic"].default_value = 0.7
    cuerpo = cilindro("cuerpo", (0, 0.06, 0.36), 0.32, 0.12, mat_pj)
    cuerpo.rotation_euler = (math.radians(90), 0, 0)
    canto = cilindro("canto", (0, 0.065, 0.36), 0.335, 0.11, material("canto", tono(color_pj, -0.3), "plastico"))
    canto.rotation_euler = (math.radians(90), 0, 0)
    extras.append(canto)
    frente_y, cara_z, tope, PLANO = -0.065, 0.38, 0.69, True
elif forma == "taza":
    cuerpo = cilindro("cuerpo", (0, 0, 0.0), 0.25, 0.56, mat_pj)
    extras.append(cilindro("cafe", (0, 0, 0.5), 0.215, 0.05, material("cafe", "#4a2c1a", "plastico"), grumo=0))
    bpy.ops.mesh.primitive_torus_add(major_radius=0.12, minor_radius=0.035, location=(0.27, 0, 0.3), rotation=(math.radians(90), 0, 0))
    extras.append(acabar(bpy.context.object, mat_pj, sub=1))
    frente_y, cara_z, tope = -0.25, 0.3, 0.6
elif forma == "bombilla":
    mat_pj = brillo(material("cuerpo", color_pj, "plastico"), color_pj, 0.6)
    cuerpo = esfera("cuerpo", (0, 0, 0.44), (0.27, 0.25, 0.27), mat_pj, grumo=0)
    rosca = material("rosca", "#a7acb3", "plastico")
    rosca.node_tree.nodes["Principled BSDF"].inputs["Metallic"].default_value = 0.8
    for k in range(3):
        extras.append(cilindro("rosca", (0, 0, 0.06 + k * 0.05), 0.12 - k * 0.006, 0.045, rosca, grumo=0))
    extras.append(cilindro("cuello", (0, 0, 0.2), 0.14, 0.06, rosca, grumo=0))
    frente_y, cara_z, tope = -0.245, 0.46, 0.0
elif forma == "gota":
    cuerpo = esfera("cuerpo", (0, 0, 0.3), (0.26, 0.24, 0.3), mat_pj)
    bpy.ops.mesh.primitive_cone_add(vertices=24, radius1=0.17, depth=0.3, location=(0, 0, 0.62))
    acabar(bpy.context.object, mat_pj, sub=2)
    hijo(bpy.context.object, raiz)
    frente_y, cara_z = -0.235, 0.3
else:   # huevo y los animales (cuerpo de huevo con sus orejas, nariz y cola)
    cuerpo = esfera("cuerpo", (0, 0, 0.32), (0.26, 0.24, 0.32), mat_pj)
    frente_y, cara_z = -0.235, 0.36
    mat_claro = material("claro", tono(color_pj, 0.5))
    if forma == "gato":
        for x in (-1, 1):
            bpy.ops.mesh.primitive_cone_add(vertices=4, radius1=0.11, depth=0.2, location=(x * 0.15, -0.03, 0.64),
                                            rotation=(0, x * math.radians(-18), math.radians(45)))
            extras.append(acabar(bpy.context.object, mat_pj, sub=0))   # en punta (el subdividido las encoge)
        tope = 0.0
    elif forma == "perro":
        for x in (-1, 1):
            o = esfera("oreja", (x * 0.25, 0.02, 0.5), (0.06, 0.03, 0.14), material("oreja", tono(color_pj, -0.3)), sub=1)
            o.rotation_euler = (0, x * math.radians(-20), 0)
            extras.append(o)
    elif forma == "oso":
        for x in (-1, 1):
            extras.append(esfera("oreja", (x * 0.16, 0.02, 0.62), (0.07, 0.04, 0.07), mat_pj, sub=1))
        extras.append(esfera("barriga", (0, -0.17, 0.15), (0.14, 0.08, 0.1), mat_claro, sub=1))
        tope = 0.0
    elif forma == "conejo":
        for x in (-1, 1):
            o = esfera("oreja", (x * 0.08, 0.02, 0.78), (0.05, 0.03, 0.2), mat_pj, sub=1)
            o.rotation_euler = (0, x * math.radians(-10), 0)
            extras.append(o)
        tope = 0.0
    if forma in ("gato", "perro", "oso", "conejo"):
        # nariz entre los ojos y la boca, y cola detras
        extras.append(esfera("nariz", (0, frente_y - 0.025, cara_z - 0.025), (0.03, 0.02, 0.022),
                             material("nariz", "#e27a8f" if forma in ("gato", "conejo") else "#2a1d17", "plastico"), sub=1, grumo=0))
        cola = {"gato": (0.03, 0.03, 0.16), "perro": (0.03, 0.03, 0.1), "oso": (0.05, 0.05, 0.05), "conejo": (0.07, 0.07, 0.07)}[forma]
        c = esfera("cola", (0.1 if forma == "gato" else 0, 0.25, 0.22 if forma == "gato" else 0.14), cola,
                   mat_claro if forma == "conejo" else mat_pj, sub=1)
        if forma in ("gato", "perro"):
            c.rotation_euler = (math.radians(-35), 0, 0)
        extras.append(c)
for o in extras:
    if o.parent is None:
        hijo(o, raiz)
pies = [esfera("pie", (x, -0.03, 0.03), (0.09, 0.11, 0.05), mat_pj, sub=1) for x in (-0.11, 0.11)]
hombro_i = bpy.data.objects.new("hombro_i", None)
hombro_d = bpy.data.objects.new("hombro_d", None)
for h, x in ((hombro_i, -0.25), (hombro_d, 0.25)):
    escena.collection.objects.link(h)
    h.location = (x, -0.02, 0.36)
brazos = []
for h, x in ((hombro_i, -0.27), (hombro_d, 0.27)):
    b = esfera("brazo", (x, -0.02, 0.27), (0.05, 0.05, 0.1), mat_pj, sub=1)
    hijo(b, h)
    brazos.append(b)


def calcomania(nombre, z, ancho, alto):
    """Plano con la imagen de los ojos o de la boca pegado al frente del cuerpo (se adapta a su curva)."""
    bpy.ops.mesh.primitive_plane_add(size=1, location=(0, frente_y - 0.03, z), rotation=(math.radians(90), 0, 0))
    o = bpy.context.object
    o.name, o.scale = nombre, (ancho, alto, 1)
    bpy.ops.object.transform_apply(scale=True)
    o.modifiers.new("sub", "SUBSURF").levels = 3
    o.modifiers["sub"].subdivision_type = "SIMPLE"
    if not PLANO:
        sw = o.modifiers.new("pegar", "SHRINKWRAP")
        sw.target, sw.wrap_method, sw.offset = cuerpo, "PROJECT", 0.004
        # el plano esta girado 90 grados: su eje Z local es el que mira al cuerpo
        sw.use_project_z, sw.use_negative_direction, sw.use_positive_direction = True, True, True
    m = bpy.data.materials.new(nombre)
    m.use_nodes = True
    n, l = m.node_tree.nodes, m.node_tree.links
    tex = n.new("ShaderNodeTexImage")
    tex.extension = "CLIP"
    mezcla = n.new("ShaderNodeMixShader")
    transp = n.new("ShaderNodeBsdfTransparent")
    p = n["Principled BSDF"]
    p.inputs["Roughness"].default_value = 0.5
    l.new(tex.outputs["Color"], p.inputs["Base Color"])
    l.new(tex.outputs["Alpha"], mezcla.inputs["Fac"])
    l.new(transp.outputs["BSDF"], mezcla.inputs[1])
    l.new(p.outputs["BSDF"], mezcla.inputs[2])
    l.new(mezcla.outputs["Shader"], n["Material Output"].inputs["Surface"])
    o.data.materials.append(m)
    hijo(o, raiz)
    return tex


tex_ojos = calcomania("ojos", cara_z + 0.01, 0.46, 0.46)
tex_boca = calcomania("boca", cara_z - 0.06, 0.46, 0.46)
IMAGENES = {}


def imagen(nombre):
    if nombre not in IMAGENES:
        IMAGENES[nombre] = bpy.data.images.load(os.path.join(AQUI, "caras", nombre + ".png"))
    return IMAGENES[nombre]


ACC = PJ.get("accesorio", "")
if not tope and ACC in ("gorro", "corona"):
    ACC = ""   # ya lleva orejas o antena arriba
if ACC == "gorro":
    cilindro("gorro", (0, 0, tope - 0.04), 0.14, 0.14, material("gorro", "#d7372c"))
    esfera("pompon", (0, 0, tope + 0.12), (0.05, 0.05, 0.05), material("pompon", "#ffffff"), sub=1)
elif ACC == "corona":
    cilindro("corona", (0, 0, tope - 0.05), 0.13, 0.1, material("corona", "#e0a92e", "plastico"))
elif ACC == "pajarita":
    for x in (-0.05, 0.05):
        esfera("pajarita", (x, frente_y + 0.02, 0.1 if not PLANO else 0.12), (0.05, 0.02, 0.035), material("pajarita", "#d7372c"), sub=1)
elif ACC == "gafas":
    for x in (-0.085, 0.085):
        bpy.ops.mesh.primitive_torus_add(major_radius=0.06, minor_radius=0.009, location=(x, frente_y - 0.035, cara_z + 0.02),
                                         rotation=(math.radians(90), 0, 0))
        acabar(bpy.context.object, material("gafas", "#1e1c1a", "plastico"), sub=0, grumo=0)
for o in [cuerpo, hombro_i, hombro_d, *pies] + [o for o in bpy.data.objects if o.name.startswith(("gorro", "pompon", "corona", "pajarita", "Torus"))]:
    if o.parent is None:
        hijo(o, raiz)

# ------------------------------------------------------------------ objetos con texto
for k, ob in enumerate((P.get("objetos") or [])[:2]):
    lado = 1 if k == 0 else -1
    # en vertical el cuadro es estrecho: los objetos van pegados al muneco (y un poco detras) para que se vean
    x, y = (0.43 if P["alto"] > P["ancho"] else 0.62) * lado, 0.16
    color = ob.get("color") or ("#4f8fcb", "#d7372c")[k % 2]
    tipo, txt = ob.get("tipo", "caja"), (ob.get("texto") or "")[:24]
    if tipo == "cartel":
        cilindro("palo", (x, y, 0), 0.02, 0.55, material("palo", "#8a6a4f"))
        caja("cartel", (x, y, 0.62), (0.52, 0.04, 0.3), material("cartel", "#fbfaf8"))
        if txt:
            texto(txt.upper(), (x, y - 0.03, 0.62), 0.09 if len(txt) < 10 else 0.06, "#1e1c1a")
    elif tipo == "libro":
        caja("libro", (x, y, 0.2), (0.3, 0.1, 0.4), material("libro", color))
        if txt:
            texto(txt.upper(), (x, y - 0.06, 0.2), 0.05, "#fbfaf8")
    elif tipo == "moneda":
        m = cilindro("moneda", (x, y, 0.22), 0.16, 0.04, material("moneda", "#e0a92e", "plastico"))
        m.rotation_euler = (math.radians(90), 0, 0)
        clave(m, 1, rotation_euler=(math.radians(90), 0, 0))
        clave(m, FIN, rotation_euler=(math.radians(90), 0, math.radians(360)))
    elif tipo == "planta":
        cilindro("maceta", (x, y, 0), 0.12, 0.17, material("maceta", "#c8673f"))
        cilindro("tallo", (x, y, 0.17), 0.016, 0.3, material("tallo", "#5e9e4e"))
        esfera("flor", (x, y - 0.01, 0.5), (0.07, 0.03, 0.07), material("flor", "#e2577a"), sub=1)
    elif tipo == "taza":
        cilindro("taza", (x, y, 0), 0.11, 0.17, material("taza", color))
    elif tipo == "grafico":
        for j, h in enumerate((0.15, 0.27, 0.42)):
            caja("barra", (x - 0.12 + j * 0.12, y, h / 2), (0.09, 0.09, h), material("barra", ("#4f8fcb", "#e0a92e", "#d7372c")[j]))
        if txt:
            texto(txt.upper(), (x, y - 0.06, 0.52), 0.06, "#1e1c1a")
    else:
        caja("caja", (x, y, 0.15), (0.3, 0.3, 0.3), material("caja", color))
        if txt:
            texto(txt.upper(), (x, y - 0.16, 0.15), 0.06, "#fbfaf8")

# ------------------------------------------------------------------ gesto (en fotogramas del plano)
GESTO = P.get("gesto", "habla")
f = lambda s: max(1, min(FIN, round(1 + s * FPS)))
clave(raiz, 1, location=(0, 0, 0), scale=(1, 1, 1), rotation_euler=(0, 0, 0))
reposo_i, reposo_d = (0, math.radians(8), 0), (0, math.radians(-8), 0)
clave(hombro_i, 1, rotation_euler=reposo_i)
clave(hombro_d, 1, rotation_euler=reposo_d)
D = P["duracion"]
if GESTO in ("salta", "celebra", "sorprendido"):
    saltos = 2 if GESTO == "celebra" else 1
    for k in range(saltos):
        t0 = 0.25 + k * 0.7
        clave(raiz, f(t0), location=(0, 0, 0), scale=(1.15, 1.15, 0.8))
        clave(raiz, f(t0 + 0.2), location=(0, 0.1 if GESTO == "sorprendido" else 0, 0.28), scale=(0.9, 0.9, 1.2))
        clave(raiz, f(t0 + 0.42), location=(0, 0.1 if GESTO == "sorprendido" else 0, 0), scale=(1.18, 1.18, 0.78))
        clave(raiz, f(t0 + 0.6), scale=(1, 1, 1))
    if GESTO == "celebra":
        clave(hombro_i, f(0.2), rotation_euler=(0, math.radians(150), 0))
        clave(hombro_d, f(0.2), rotation_euler=(0, math.radians(-150), 0))
elif GESTO == "saluda":
    clave(hombro_d, f(0.25), rotation_euler=(0, math.radians(-150), 0))
    for k in range(int((D - 0.6) / 0.3)):
        clave(hombro_d, f(0.45 + k * 0.3), rotation_euler=(0, math.radians(-130 if k % 2 else -165), 0))
elif GESTO == "senala":
    clave(hombro_d, f(0.3), rotation_euler=(0, math.radians(-95), math.radians(-15)))
    clave(raiz, f(0.3), rotation_euler=(0, 0, math.radians(-12)))
elif GESTO == "piensa":
    clave(hombro_i, f(0.3), rotation_euler=(math.radians(-60), math.radians(120), 0))
    clave(raiz, f(0.4), rotation_euler=(0, math.radians(8), 0))
elif GESTO == "triste":
    clave(raiz, f(0.4), scale=(1.06, 1.06, 0.9), rotation_euler=(math.radians(6), 0, 0))
    clave(hombro_i, f(0.4), rotation_euler=(0, math.radians(-4), 0))
    clave(hombro_d, f(0.4), rotation_euler=(0, math.radians(4), 0))
elif GESTO == "baila":
    for k in range(int(D / 0.4) + 1):
        lado = 1 if k % 2 else -1
        clave(raiz, f(k * 0.4), location=(0.06 * lado, 0, 0.03 * (k % 2)), rotation_euler=(0, math.radians(10 * lado), 0))
        clave(hombro_i, f(k * 0.4), rotation_euler=(0, math.radians(120 if k % 2 else 30), 0))
        clave(hombro_d, f(k * 0.4), rotation_euler=(0, math.radians(-30 if k % 2 else -120), 0))
elif GESTO == "camina":
    pasos = int(D / 0.3)
    for k in range(pasos + 1):
        x = -0.9 + 0.9 * min(1, k / max(1, pasos * 0.7))
        clave(raiz, f(k * 0.3), location=(x, 0, 0.05 if k % 2 else 0), rotation_euler=(0, math.radians(5 if k % 2 else -5), 0))
else:   # habla: rebote suave y manos que acompanan
    for k in range(int(D / 0.5) + 1):
        clave(raiz, f(k * 0.5), scale=(1.0, 1.0, 1.03 if k % 2 else 0.98))
        clave(hombro_d, f(k * 0.5), rotation_euler=(0, math.radians(-35 if k % 3 == 1 else -8), 0))

# ------------------------------------------------------------------ luz, camara, render
mundo = bpy.data.worlds.new("mundo")
escena.world = mundo
mundo.use_nodes = True
mundo.node_tree.nodes["Background"].inputs["Color"].default_value = hexa(cielo_c)
mundo.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.4 if ESC != "exterior" else 0.9


def luz(nombre, pos, energia, color, tam, mira=(0, 0, 0.3)):
    d = bpy.data.lights.new(nombre, "AREA")
    d.energy, d.color, d.size = energia, hexa(color)[:3], tam
    o = bpy.data.objects.new(nombre, d)
    escena.collection.objects.link(o)
    o.location = pos
    o.rotation_euler = (Vector(mira) - Vector(pos)).to_track_quat("-Z", "Y").to_euler()


luz("clave", (-1.6, -1.8, 2.2), 260, "#ffe2b8", 1.6)
luz("relleno", (1.8, -1.4, 0.8), 80, "#ffd9c7", 2.5)
luz("contra", (0.6, 2.0, 1.6), 90, "#cfe3ff", 1.0)

vertical = P["alto"] > P["ancho"]
TOMAS = {   # (posicion inicial, final, a donde mira, lente)
    "general": ((0.0, -2.6, 0.95), (0.0, -2.3, 0.85), (0, 0, 0.32), 32),
    "medio": ((0.1, -1.7, 0.6), (0.05, -1.5, 0.55), (0, 0, 0.36), 40),
    "primer": ((0.05, -1.45, 0.52), (0.0, -1.3, 0.5), (0, 0, 0.4), 50),
    "contrapicado": ((-0.35, -1.3, 0.1), (-0.25, -1.15, 0.14), (0, 0, 0.42), 30),
}
ini, fin, mira, lente = TOMAS.get(P.get("camara", "medio"), TOMAS["medio"])
if not vertical:   # en horizontal se abre un poco para que quepan los objetos de los lados
    ini, fin = tuple(Vector(ini) * 1.15), tuple(Vector(fin) * 1.15)
cam_d = bpy.data.cameras.new("cam")
cam_d.lens = lente
cam_d.dof.use_dof = True
cam_d.dof.aperture_fstop = 1.8
cam = bpy.data.objects.new("cam", cam_d)
escena.collection.objects.link(cam)
escena.camera = cam
foco = bpy.data.objects.new("foco", None)
escena.collection.objects.link(foco)
foco.location = mira
hijo(foco, raiz)          # el foco sigue al personaje (si camina o salta)
cam_d.dof.focus_object = foco
clave(cam, 1, location=ini)
clave(cam, FIN, location=fin)
pista = cam.constraints.new("TRACK_TO")
pista.target, pista.track_axis, pista.up_axis = foco, "TRACK_NEGATIVE_Z", "UP_Y"

r = escena.render
for motor in ("BLENDER_EEVEE", "BLENDER_EEVEE_NEXT"):
    try:
        r.engine = motor
        break
    except TypeError:
        pass
escena.eevee.taa_render_samples = int(P.get("muestras", 24))
r.resolution_x, r.resolution_y, r.resolution_percentage = P["ancho"], P["alto"], 100
r.image_settings.file_format = "PNG"
escena.view_settings.view_transform = "Standard"

CARA = P.get("cara", "normal")
BOCA = str(P.get("boca") or "")
tex_ojos.image = imagen(f"ojos_{CARA}")
parpadeos = set()
t = 1.0 + azar.random()
while t < D:
    parpadeos.add(round(t * FPS) // 2 * 2 + 1)   # cae en una pose (fotogramas impares)
    t += 2.4 + azar.random() * 1.8
for fr in range(1, FIN + 1, 2):   # en doses: una pose cada dos fotogramas
    escena.frame_set(fr)
    if MATERIAL == "barro":
        hervor.location = (azar.uniform(-.15, .15), azar.uniform(-.15, .15), azar.uniform(-.15, .15))
    abiertos = CARA not in ("feliz", "dormido", "mareado") and fr in parpadeos
    tex_ojos.image = imagen("ojos_dormido" if abiertos else f"ojos_{CARA}")
    if BOCA:
        nivel = int(BOCA[min(len(BOCA) - 1, fr - 1)])
        tex_boca.image = imagen(f"boca_{CARA}" if nivel == 0 and CARA != "normal" else f"boca_{nivel}")
    else:
        tex_boca.image = imagen(f"boca_{CARA}")
    r.filepath = os.path.join(P["salida"], f"f_{fr:04d}.png")
    bpy.ops.render.render(write_still=True)
    print("POSE", fr, FIN, flush=True)
print("LISTO", flush=True)
# salir sin el cierre normal de Blender: en Windows a veces se cae al liberar la grafica (ACCESS_VIOLATION)
# despues de haber guardado todo, y eso se tomaba como error
sys.stdout.flush()
os._exit(0)
