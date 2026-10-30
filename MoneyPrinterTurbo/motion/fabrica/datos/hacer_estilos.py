"""
Recursos de los estilos de la Fabrica, con Nano Banana en Google Flow (solo en el PC local; el resultado va
al repo):

    python hacer_estilos.py                 # genera lo que falte (retomable) y recorta
    python hacer_estilos.py --muestra       # solo unas pocas de cada familia, para ver como quedan
    python hacer_estilos.py --solo-recortar

  familias/<familia>/pegatinas/<id>.webp      los mismos ids que la base, dibujados como pide la familia
  familias/<familia>/ilustraciones/<id>.webp  (biblioteca.FAMILIAS)
  texturas/<estilo>_v.webp y _h.webp          fondo del estilo en vertical y horizontal (el cuadrado usa la vertical)
"""
import os
import sys

from PIL import Image

from hacer_pegatinas import AQUI, ESCENAS, FABRICA, PEGATINAS, TRABAJO, crudo, generar

sys.path.insert(0, os.path.normpath(os.path.join(FABRICA, "..", "..")))
from app.services.estudio.biblioteca import FAMILIAS, FONDO, _guardar_ilustracion, recortar  # noqa: E402

LISO = ", flat and evenly lit, seamless, no objects, no people, no text, empty background texture"
TEXTURAS = {
    "papel": "Aged parchment paper texture with subtle stains, fibers and darker worn edges" + LISO,
    "pizarra": "Dark green school chalkboard texture with faint chalk dust and eraser smudges" + LISO,
    "cuaderno": "Top-down photo of a blank lined notebook page, faint blue ruled lines and a red margin line on the left" + LISO,
    "periodico": "Blank old newsprint paper, off-white with fine grain and faint ink smudges" + LISO,
    "documental": "Abstract dark cinematic backdrop, deep black with a soft warm golden haze in one corner and subtle film grain" + LISO,
    "neon": "Abstract dark synthwave backdrop, deep purple and midnight blue gradient with a faint glowing magenta horizon line low in the frame" + LISO,
}
MUESTRA = ["rey", "napoleon", "barco_vela", "monedas", "volcan"]


def recortar_lista(lista, carpeta, destino, guardar):
    os.makedirs(destino, exist_ok=True)
    for i, (clave, _) in enumerate(lista):
        origen, final = crudo(carpeta, i + 1), os.path.join(destino, f"{clave}.webp")
        if origen and not (os.path.isfile(final) and os.path.getmtime(final) >= os.path.getmtime(origen)):
            with Image.open(origen) as img:
                guardar(img, final)


def guardar_textura(img, destino):
    img = img.convert("RGB")
    if max(img.size) > 1920:
        f = 1920 / max(img.size)
        img = img.resize((round(img.width * f), round(img.height * f)), Image.LANCZOS)
    img.save(destino, "WEBP", quality=80, method=6)


def main():
    muestra, solo_recortar = "--muestra" in sys.argv, "--solo-recortar" in sys.argv
    trabajos = []
    for fam, p in FAMILIAS.items():
        pegs = [(k, p["pegatina"].format(en) + FONDO) for k, (_, en, _) in PEGATINAS.items()]
        escs = [(k, p["escena"].format(en)) for k, (en, _) in ESCENAS.items()]
        destino = os.path.join(FABRICA, "familias", fam)
        trabajos += [(pegs, os.path.join(TRABAJO, fam, "pegatinas"), "1:1", os.path.join(destino, "pegatinas"), recortar),
                     (escs, os.path.join(TRABAJO, fam, "ilustraciones"), "9:16", os.path.join(destino, "ilustraciones"), _guardar_ilustracion)]
    for lado, aspecto in (("v", "9:16"), ("h", "16:9")):
        tex = [(f"{k}_{lado}", t) for k, t in TEXTURAS.items()]
        trabajos.append((tex, os.path.join(TRABAJO, "texturas", lado), aspecto, os.path.join(FABRICA, "texturas"), guardar_textura))
    for lista, carpeta, aspecto, destino, guardar in trabajos:
        if not solo_recortar:
            solo = None
            if muestra:
                # unas pocas por familia (y la primera ilustracion); las texturas son pocas: todas
                claves = [k for k, _ in lista]
                solo = [claves.index(k) + 1 for k in MUESTRA if k in claves] or ([1] if "ilustraciones" in carpeta else None)
            generar(lista, carpeta, aspecto, solo)
        recortar_lista(lista, carpeta, destino, guardar)
    for fam in FAMILIAS:
        for tipo in ("pegatinas", "ilustraciones"):
            d = os.path.join(FABRICA, "familias", fam, tipo)
            print(f"{fam}/{tipo}: {len(os.listdir(d)) if os.path.isdir(d) else 0}")
    print("texturas:", len(os.listdir(os.path.join(FABRICA, "texturas"))))


if __name__ == "__main__":
    main()
