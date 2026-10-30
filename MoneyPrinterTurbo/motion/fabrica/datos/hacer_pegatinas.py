"""
Genera la biblioteca de pegatinas (personajes y objetos de juguete) y escenas ilustradas de la Fabrica
con Nano Banana en Google Flow (tools/flow, solo en el PC local; el resultado se guarda en el repo y
sirve tambien en el VPS):

    python hacer_pegatinas.py              # genera lo que falte (retomable) y recorta
    python hacer_pegatinas.py --solo-recortar

  pegatinas/<id>.webp   figura sobre fondo transparente (se pide sobre verde croma y se le quita)
  ilustraciones/<id>.webp  ilustracion vertical 9:16 a pantalla completa
  catalogo.json         {"pegatinas": {id: descripcion}, "ilustraciones": {id: descripcion}} (lo lee Claude)
"""
import hashlib
import json
import os
import subprocess
import sys

from PIL import Image

AQUI = os.path.dirname(os.path.abspath(__file__))
FABRICA = os.path.dirname(AQUI)
RAIZ = os.path.normpath(os.path.join(FABRICA, "..", ".."))
FLOW = os.path.normpath(os.path.join(RAIZ, "..", "tools", "flow"))
TRABAJO = os.path.join(AQUI, "_flow")  # crudos de Flow (no van al repo)

sys.path.insert(0, RAIZ)
# los mismos prompts y el mismo recorte que cuando la persona crea un dibujo desde la Fabrica
from app.services.estudio.biblioteca import ESCENA, FIGURA, FONDO, OBJETO, _guardar_ilustracion, recortar  # noqa: E402

# id: (plantilla, descripcion en ingles para el prompt, descripcion en espanol para el catalogo)
PEGATINAS = {
    # personas
    "rey": (FIGURA, "a medieval king with golden crown and red ermine cape", "rey con corona y capa"),
    "reina": (FIGURA, "a queen with a small golden crown and royal blue gown", "reina"),
    "emperador_romano": (FIGURA, "a Roman emperor with laurel wreath and purple toga", "emperador romano"),
    "legionario": (FIGURA, "a Roman legionary with red cape, helmet and rectangular shield", "soldado romano"),
    "faraon": (FIGURA, "an ancient Egyptian pharaoh with blue and gold nemes headdress", "faraón egipcio"),
    "vikingo": (FIGURA, "a viking warrior with horned helmet, beard and round shield", "vikingo"),
    "caballero": (FIGURA, "a medieval knight in silver armor with a sword", "caballero medieval"),
    "samurai": (FIGURA, "a Japanese samurai in red lacquered armor with katana", "samurái"),
    "conquistador": (FIGURA, "a Spanish conquistador with morion helmet and breastplate", "conquistador español"),
    "explorador": (FIGURA, "an explorer with pith helmet, khaki clothes and binoculars", "explorador"),
    "pirata": (FIGURA, "a pirate captain with tricorn hat, eye patch and cutlass", "pirata"),
    "marinero": (FIGURA, "a sailor with white sailor cap and striped shirt", "marinero"),
    "napoleon": (FIGURA, "Napoleon-style general with bicorne hat and blue coat with golden epaulettes", "general napoleónico"),
    "soldado_1914": (FIGURA, "a World War I soldier with brodie helmet and rifle", "soldado de la Primera Guerra Mundial"),
    "soldado_1944": (FIGURA, "a World War II soldier with green helmet and rifle", "soldado de la Segunda Guerra Mundial"),
    "soldado_moderno": (FIGURA, "a modern soldier in camouflage uniform", "soldado moderno"),
    "presidente": (FIGURA, "a politician in a dark suit and red tie", "presidente o político"),
    "diplomatico": (FIGURA, "an 18th century diplomat with white powdered wig holding a quill", "diplomático antiguo con peluca"),
    "monje": (FIGURA, "a medieval monk in brown robe holding a book", "monje"),
    "campesino": (FIGURA, "a peasant farmer with straw hat holding a pitchfork", "campesino"),
    "mercader": (FIGURA, "a medieval merchant with turban holding a bag of coins", "mercader"),
    "jeque": (FIGURA, "an Arab sheikh in white thobe and red checkered keffiyeh", "jeque árabe"),
    "vaquero": (FIGURA, "a cowboy with brown hat and lasso", "vaquero"),
    "inuit": (FIGURA, "an Inuit person in a fur parka with hood", "inuit"),
    "cientifico": (FIGURA, "a scientist in white lab coat with glasses holding a flask", "científico"),
    "astronauta": (FIGURA, "an astronaut in white space suit with helmet", "astronauta"),
    "turista": (FIGURA, "a tourist with hawaiian shirt, sunglasses and camera", "turista"),
    "minero": (FIGURA, "a miner with helmet lamp and pickaxe", "minero"),
    "pescador": (FIGURA, "a fisherman with yellow raincoat holding a fish", "pescador"),
    "nino": (FIGURA, "a curious little boy with backpack", "niño"),
    "abuela": (FIGURA, "a kind grandmother with grey bun and glasses", "abuela"),
    "obrero": (FIGURA, "a construction worker with yellow hard hat", "obrero"),
    "banquero": (FIGURA, "a rich banker with top hat, monocle and moustache", "banquero rico"),
    # animales
    "mono": (OBJETO, "a fluffy macaque monkey sitting on a rock", "mono"),
    "camello": (OBJETO, "a camel with saddle", "camello"),
    "oso_polar": (OBJETO, "a polar bear", "oso polar"),
    "pinguino": (OBJETO, "a penguin", "pingüino"),
    "elefante": (OBJETO, "an elephant", "elefante"),
    "canguro": (OBJETO, "a kangaroo", "canguro"),
    "leon": (OBJETO, "a lion", "león"),
    # transporte
    "barco_vela": (OBJETO, "an old wooden sailing galleon on a small square block of stylized ocean waves, diorama style", "barco de vela antiguo"),
    "buque_guerra": (OBJETO, "a modern grey navy warship on a small square block of ocean waves, diorama style", "buque de guerra moderno"),
    "barco_carga": (OBJETO, "a container cargo ship with colorful containers on a small block of ocean waves, diorama style", "barco de carga con contenedores"),
    "avion": (OBJETO, "a white passenger airplane", "avión de pasajeros"),
    "avion_guerra": (OBJETO, "a fighter jet", "avión de combate"),
    "tren_vapor": (OBJETO, "a steam locomotive", "tren de vapor"),
    "coche": (OBJETO, "a red classic car", "coche"),
    "camion": (OBJETO, "a delivery truck", "camión"),
    "tanque": (OBJETO, "a military tank", "tanque"),
    "cohete": (OBJETO, "a space rocket", "cohete"),
    # objetos
    "corona": (OBJETO, "a golden royal crown with red velvet and jewels", "corona"),
    "canon": (OBJETO, "an old black cannon on a wooden carriage with a puff of smoke", "cañón antiguo"),
    "espadas": (OBJETO, "two crossed swords", "espadas cruzadas (guerra, batalla)"),
    "escudo": (OBJETO, "a medieval heraldic shield", "escudo"),
    "bomba": (OBJETO, "a round black cartoon bomb with lit fuse", "bomba"),
    "candado": (OBJETO, "a heavy old iron padlock, locked", "candado (cerrado, bloqueo)"),
    "llave": (OBJETO, "an old golden key", "llave"),
    "pergamino": (OBJETO, "a rolled parchment scroll with red wax seal", "pergamino o tratado"),
    "libro": (OBJETO, "an old leather book", "libro"),
    "mapa_antiguo": (OBJETO, "an old treasure map, partially rolled", "mapa antiguo"),
    "brujula": (OBJETO, "a brass compass", "brújula"),
    "globo_terraqueo": (OBJETO, "a desk globe", "globo terráqueo"),
    "lupa": (OBJETO, "a magnifying glass", "lupa"),
    "reloj_arena": (OBJETO, "an hourglass", "reloj de arena (tiempo)"),
    "calendario": (OBJETO, "a tear-off desk calendar", "calendario"),
    "urna": (OBJETO, "a ballot box with a voting paper going in", "urna de votación"),
    "trofeo": (OBJETO, "a golden trophy cup", "trofeo"),
    "bandera_blanca": (OBJETO, "a white surrender flag on a pole", "bandera blanca (rendición)"),
    "dinero": (OBJETO, "a stack of green banknotes", "dinero, billetes"),
    "monedas": (OBJETO, "a pile of gold coins", "monedas de oro"),
    "lingotes": (OBJETO, "a stack of gold bars", "lingotes de oro"),
    "grafico_sube": (OBJETO, "a 3D bar chart with green arrow going up", "gráfico que sube"),
    "grafico_baja": (OBJETO, "a 3D bar chart with red arrow going down", "gráfico que baja"),
    "petroleo": (OBJETO, "an oil barrel with black oil drip", "barril de petróleo"),
    "fabrica": (OBJETO, "a factory with smoking chimneys", "fábrica"),
    "casa": (OBJETO, "a small cozy house", "casa"),
    "castillo": (OBJETO, "a medieval stone castle", "castillo"),
    "muralla": (OBJETO, "a section of stone wall with battlements", "muralla"),
    "piramide": (OBJETO, "an Egyptian pyramid on sand", "pirámide"),
    "rascacielos": (OBJETO, "a group of modern skyscrapers", "rascacielos, ciudad"),
    "puente": (OBJETO, "a suspension bridge", "puente"),
    "presa": (OBJETO, "a concrete hydroelectric dam with water", "presa"),
    "tienda_campana": (OBJETO, "a camping tent", "tienda de campaña"),
    # naturaleza
    "montana": (OBJETO, "a snowy mountain peak", "montaña"),
    "volcan": (OBJETO, "an erupting volcano", "volcán"),
    "palmera": (OBJETO, "a palm tree on a small sand island", "palmera o isla"),
    "arbol": (OBJETO, "a leafy tree", "árbol, bosque"),
    "iceberg": (OBJETO, "an iceberg", "iceberg, hielo"),
    "gota": (OBJETO, "a big blue water drop", "agua"),
    "fuego": (OBJETO, "a campfire flame", "fuego"),
    "sol": (OBJETO, "a smiling sun", "sol, calor"),
    "nube_lluvia": (OBJETO, "a rain cloud with drops", "lluvia"),
    "rayo": (OBJETO, "a lightning bolt", "rayo, energía"),
    "trigo": (OBJETO, "a bundle of golden wheat", "trigo, agricultura"),
    "oro": (OBJETO, "a gold nugget", "pepita de oro"),
    "diamante": (OBJETO, "a sparkling diamond", "diamante"),
    # finanzas (nicho finanzas y datos)
    "hucha": (OBJETO, "a pink piggy bank with a coin going in", "hucha, ahorro"),
    "tarjeta_credito": (OBJETO, "a golden credit card", "tarjeta de crédito"),
    "bitcoin": (OBJETO, "a golden bitcoin coin", "bitcoin, criptomonedas"),
    "cartera": (OBJETO, "a brown leather wallet with banknotes sticking out", "cartera, dinero personal"),
    "factura": (OBJETO, "a long paper receipt bill with numbers", "factura, recibo, gastos"),
    "carrito": (OBJETO, "a supermarket shopping cart full of groceries", "compra, supermercado, precios"),
    "calculadora": (OBJETO, "a calculator", "calculadora, cuentas"),
    "maletin": (OBJETO, "a black business briefcase", "empresa, negocios"),
    "banco_edificio": (OBJETO, "a classical bank building with columns", "banco (edificio)"),
    "bolsa_dinero": (OBJETO, "a sack of money with a dollar sign", "saco de dinero"),
    "billete_quemado": (OBJETO, "a banknote burning with flames", "dinero que se pierde, inflación"),
    "etiqueta_precio": (OBJETO, "a price tag", "precio"),
    "casa_venta": (OBJETO, "a small house with a for sale sign without text", "vivienda en venta, alquiler"),
    "hombre_negocios": (FIGURA, "a businessman in a grey suit holding a briefcase", "empresario"),
    "inversor": (FIGURA, "a young investor holding a tablet with a rising chart", "inversor"),
    "trabajadora": (FIGURA, "an office worker woman with glasses holding documents", "trabajadora de oficina"),
    "toro_bolsa": (OBJETO, "a charging golden bull", "mercado alcista, bolsa"),
    "oso_bolsa": (OBJETO, "a grumpy brown bear", "mercado bajista"),
    # curiosidades (ciencia, animales, objetos de todos los dias)
    "bombilla": (OBJETO, "a glowing light bulb", "idea, invento"),
    "cerebro": (OBJETO, "a pink human brain", "cerebro, mente"),
    "corazon": (OBJETO, "a red anatomical heart", "corazón, salud"),
    "adn": (OBJETO, "a DNA double helix", "ADN, genética"),
    "microscopio": (OBJETO, "a microscope", "ciencia, microscopio"),
    "telescopio": (OBJETO, "a brass telescope on a tripod", "telescopio, astronomía"),
    "planeta": (OBJETO, "the planet Saturn with rings", "planeta, espacio"),
    "luna": (OBJETO, "the full moon with craters", "luna"),
    "robot": (OBJETO, "a friendly robot", "robot, inteligencia artificial"),
    "movil": (OBJETO, "a modern smartphone", "móvil, teléfono"),
    "ordenador": (OBJETO, "a laptop computer", "ordenador, internet"),
    "dinosaurio": (OBJETO, "a green tyrannosaurus rex", "dinosaurio"),
    "gato": (OBJETO, "a curious orange cat", "gato"),
    "perro": (OBJETO, "a happy dog", "perro"),
    "tiburon": (OBJETO, "a great white shark", "tiburón"),
    "pulpo": (OBJETO, "an octopus", "pulpo"),
    "abeja": (OBJETO, "a honey bee", "abeja"),
    "hormiga": (OBJETO, "an ant", "hormiga, insecto"),
    "pizza": (OBJETO, "a pizza with one slice pulled", "pizza, comida"),
    "hamburguesa": (OBJETO, "a hamburger", "hamburguesa, comida rápida"),
    "cafe": (OBJETO, "a steaming cup of coffee", "café"),
    "chocolate": (OBJETO, "a bar of chocolate", "chocolate, dulce"),
    "medicina": (OBJETO, "a medicine bottle with pills", "medicina, pastillas"),
    "interrogacion": (OBJETO, "a big question mark", "pregunta, misterio"),
    "exclamacion": (OBJETO, "a big exclamation mark", "sorpresa, atención"),
    "regalo": (OBJETO, "a wrapped gift box with ribbon", "regalo"),
    "reloj": (OBJETO, "an alarm clock", "reloj, hora"),
    "medalla": (OBJETO, "a gold medal with ribbon", "medalla, récord"),
}

ESCENAS = {
    "trono": ("a king sitting on a golden throne in a royal hall", "rey en su trono"),
    "rey_enfermo": ("a sick old king lying in a canopy bed in a candle-lit royal bedroom with worried courtiers", "rey enfermo o muerte de un rey"),
    "tratado": ("diplomats with powdered wigs signing a treaty at a long table in a palace hall", "firma de un tratado"),
    "batalla_naval": ("two fleets of sailing galleons firing cannons at sea with smoke", "batalla naval antigua"),
    "batalla": ("two armies clashing on a battlefield with flags and smoke", "batalla en tierra"),
    "asedio": ("soldiers besieging a stone fortress with cannons", "asedio de una fortaleza"),
    "desembarco": ("soldiers landing on a beach from rowing boats, sailing ships behind", "desembarco"),
    "votacion": ("citizens queuing to vote at ballot boxes in a town hall", "votación, referéndum"),
    "parlamento": ("politicians arguing in a parliament chamber", "parlamento, política"),
    "mercado": ("a busy medieval market with stalls of spices and fabrics", "mercado, comercio"),
    "puerto": ("a busy harbor with sailing ships and workers loading crates", "puerto, comercio marítimo"),
    "caravana": ("a camel caravan crossing golden desert dunes", "caravana en el desierto"),
    "exploradores": ("explorers in a small boat arriving at an unknown jungle coast", "exploración, descubrimiento"),
    "construccion": ("workers building a huge stone monument with scaffolding", "construcción de una gran obra"),
    "fabrica": ("factory workers operating machines in a 19th century industrial factory", "revolución industrial"),
    "bolsa": ("traders shouting at a stock exchange with big screens of charts", "bolsa, economía"),
    "banco": ("a banker counting piles of gold coins in a vault", "banco, riqueza"),
    "protesta": ("a crowd protesting in a city square holding blank signs", "protesta, revolución"),
    "frontera": ("border guards at a checkpoint barrier between two countries", "frontera"),
    "muro": ("people looking at a tall concrete wall dividing a city", "muro que divide"),
    "granja": ("farmers harvesting wheat in golden fields", "agricultura"),
    "rio_nilo": ("farmers along a green river bank in the desert with palm trees", "río en el desierto"),
    "hielo_polar": ("an expedition with sled dogs on a frozen polar landscape", "expedición polar"),
    "ciudad_moderna": ("a modern city skyline at sunset with traffic", "ciudad moderna"),
    "laboratorio": ("scientists working in a laboratory", "ciencia, descubrimiento"),
    "aula": ("a teacher pointing at a world map in a classroom", "escuela, aprender"),
    "oficina": ("office workers at desks with computers in a modern office", "oficina, trabajo"),
    "supermercado": ("shoppers pushing carts in a supermarket aisle looking at prices", "supermercado, precios, inflación"),
    "facturas": ("a worried family at a kitchen table looking at a pile of bills", "facturas, economía familiar"),
    "inversor_pantallas": ("an investor at a desk looking at several screens with stock charts", "invertir, bolsa"),
    "cajero": ("people queuing at a bank ATM on a city street", "banco, sacar dinero"),
    "tienda_barrio": ("a shopkeeper behind the counter of a small neighborhood shop", "comercio, pequeño negocio"),
    "espacio": ("an astronaut floating in space next to a space station with Earth behind", "espacio, astronautas"),
    "fondo_mar": ("a small submarine exploring the deep sea with glowing fish", "fondo del mar, océano"),
    "dinosaurios": ("dinosaurs walking in a prehistoric jungle with a volcano", "dinosaurios, prehistoria"),
    "hospital": ("doctors and nurses treating a patient in a hospital room", "hospital, medicina"),
    "atasco": ("a city traffic jam with many cars and buses", "tráfico, ciudad"),
    "cocina": ("a chef cooking in a busy restaurant kitchen", "cocina, comida"),
}


def generar(lista, carpeta, aspecto, solo=None):
    os.makedirs(carpeta, exist_ok=True)
    escenas = [{"scene_number": i + 1, "image_prompt": prompt} for i, (_, prompt) in enumerate(lista)]
    script = os.path.join(carpeta, "script.json")
    with open(script, "w", encoding="utf-8") as f:
        json.dump({"scenes": escenas}, f, ensure_ascii=False)
    # el lote salta las que ya tienen archivo: se puede cortar y volver a lanzar
    for _ in range(3):
        subprocess.run(["node", os.path.join(FLOW, "lote.js"), "--script", script, "--out", carpeta,
                        "--aspect", aspecto, "--model", "2", "--pasadas-extra", "2"]
                       + (["--solo", ",".join(map(str, solo))] if solo else []), cwd=FLOW, check=False)
        if not repetidas(carpeta, len(lista)):
            break


def repetidas(carpeta, total):
    """Flow a veces descarga una imagen que ya habia hecho en vez de la nueva: se borran las copias
    (y la siguiente, que suele llevar el desfase) para que el lote las vuelva a pedir."""
    vistas, borrar = {}, set()
    for n in range(1, total + 1):
        ruta = crudo(carpeta, n)
        if not ruta:
            continue
        with open(ruta, "rb") as f:
            clave = hashlib.md5(f.read()).hexdigest()
        if clave in vistas:
            borrar.update({n, n + 1})
        vistas.setdefault(clave, n)
    for n in borrar:
        ruta = crudo(carpeta, n)
        if ruta:
            os.remove(ruta)
    return bool(borrar)


def crudo(carpeta, n):
    for ext in (".jpeg", ".jpg", ".png", ".webp"):
        ruta = os.path.join(carpeta, f"scene_{n:04d}{ext}")
        if os.path.isfile(ruta):
            return ruta
    return None


def main():
    solo_recortar = "--solo-recortar" in sys.argv
    pegs = [(k, plantilla.format(en) + FONDO) for k, (plantilla, en, _) in PEGATINAS.items()]
    escs = [(k, ESCENA.format(en)) for k, (en, _) in ESCENAS.items()]
    # el numero de cada imagen es su posicion en la lista: anadir siempre al final
    trabajos = [(pegs, os.path.join(TRABAJO, "pegatinas"), "1:1", "pegatinas"),
                (escs, os.path.join(TRABAJO, "ilustraciones"), "9:16", "ilustraciones")]
    for lista, carpeta, aspecto, salida in trabajos:
        if not solo_recortar:
            generar(lista, carpeta, aspecto)
        destino = os.path.join(FABRICA, salida)
        os.makedirs(destino, exist_ok=True)
        for i, (clave, _) in enumerate(lista):
            origen, final = crudo(carpeta, i + 1), os.path.join(destino, f"{clave}.webp")
            if not origen or (os.path.isfile(final) and os.path.getmtime(final) >= os.path.getmtime(origen)):
                continue
            with Image.open(origen) as img:
                (recortar if salida == "pegatinas" else _guardar_ilustracion)(img, final)
    catalogo = {"pegatinas": {k: v[2] for k, v in PEGATINAS.items() if os.path.isfile(os.path.join(FABRICA, "pegatinas", f"{k}.webp"))},
                "ilustraciones": {k: v[1] for k, v in ESCENAS.items() if os.path.isfile(os.path.join(FABRICA, "ilustraciones", f"{k}.webp"))}}
    with open(os.path.join(AQUI, "catalogo.json"), "w", encoding="utf-8") as f:
        json.dump(catalogo, f, ensure_ascii=False, indent=1)
    print(f"pegatinas: {len(catalogo['pegatinas'])}/{len(PEGATINAS)}  ilustraciones: {len(catalogo['ilustraciones'])}/{len(ESCENAS)}")


if __name__ == "__main__":
    main()
