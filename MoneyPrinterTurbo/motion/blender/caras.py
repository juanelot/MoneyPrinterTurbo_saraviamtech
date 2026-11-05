"""Caras del muneco de Blender dibujadas con codigo (PNG transparente, 512x512): los ojos de cada expresion y las bocas
(10 de hablar, 0 cerrada - 9 muy abierta, mas las de cada expresion). En Blender son dos calcomanias encima del cuerpo:
cambiar de expresion o mover la boca es cambiar de imagen, asi el personaje siempre es el mismo.

Uso: python caras.py  (deja caras/ojos_<expresion>.png y caras/boca_<n|expresion>.png junto a este archivo)
"""
import math
import os

from PIL import Image, ImageDraw

LADO = 512
ESCALA = 4                     # se dibuja a 4x y se reduce: bordes suaves
TINTA = (30, 26, 24, 255)
BLANCO = (255, 255, 255, 255)
BOCA = (92, 30, 30, 255)
LENGUA = (217, 101, 90, 255)
DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "caras")

EXPRESIONES = ("normal", "feliz", "triste", "enojado", "sorprendido", "mareado", "guino", "pensando", "dormido")


def _lienzo():
    img = Image.new("RGBA", (LADO * ESCALA, LADO * ESCALA), (0, 0, 0, 0))
    return img, ImageDraw.Draw(img)


def _guardar(img, nombre):
    img.resize((LADO, LADO), Image.LANCZOS).save(os.path.join(DIR, nombre))


def _p(x, y):
    return x * ESCALA, y * ESCALA


def _arco(d, cx, cy, r, a0, a1, ancho, color=TINTA):
    caja = [*_p(cx - r, cy - r), *_p(cx + r, cy + r)]
    d.arc(caja, a0, a1, fill=color, width=int(ancho * ESCALA))


def _ojo_abierto(d, cx, cy, mira=(-6, 4), r=34):
    d.ellipse([*_p(cx - r, cy - r * 1.15), *_p(cx + r, cy + r * 1.15)], fill=TINTA)
    bx, by = cx + mira[0] - 10, cy + mira[1] - 16
    d.ellipse([*_p(bx - 10, by - 10), *_p(bx + 10, by + 10)], fill=BLANCO)
    d.ellipse([*_p(bx + 14, by + 22), *_p(bx + 19, by + 27)], fill=BLANCO)


def ojos(expresion):
    img, d = _lienzo()
    izq, der, y = 176, 336, 210
    if expresion in ("normal", "pensando"):
        mira = (8, -10) if expresion == "pensando" else (-6, 4)
        _ojo_abierto(d, izq, y, mira)
        _ojo_abierto(d, der, y, mira)
        if expresion == "pensando":   # una ceja levantada
            d.line([*_p(izq - 34, y - 70), *_p(izq + 30, y - 58)], fill=TINTA, width=14 * ESCALA)
            _arco(d, der, y - 50, 40, 200, 340, 14)
    elif expresion == "feliz":        # arcos hacia arriba
        for cx in (izq, der):
            _arco(d, cx, y + 18, 36, 200, 340, 18)
    elif expresion == "triste":
        for cx, s in ((izq, 1), (der, -1)):
            _ojo_abierto(d, cx, y + 10, (-4, 10), r=28)
            d.line([*_p(cx - 40, y - 40 - 14 * s), *_p(cx + 40, y - 40 + 14 * s)], fill=TINTA, width=13 * ESCALA)
        d.ellipse([*_p(izq - 6, y + 50), *_p(izq + 10, y + 74)], fill=(120, 190, 240, 255))   # lagrima
    elif expresion == "enojado":
        for cx, s in ((izq, 1), (der, -1)):
            _ojo_abierto(d, cx, y + 12, (0, 6), r=27)
            d.line([*_p(cx - 44, y - 50 + 22 * s), *_p(cx + 44, y - 50 - 22 * s)], fill=TINTA, width=16 * ESCALA)
    elif expresion == "sorprendido":
        for cx in (izq, der):
            d.ellipse([*_p(cx - 42, y - 48), *_p(cx + 42, y + 48)], fill=BLANCO, outline=TINTA, width=9 * ESCALA)
            d.ellipse([*_p(cx - 16, y - 16), *_p(cx + 16, y + 16)], fill=TINTA)
            _arco(d, cx, y - 60, 36, 210, 330, 12)
    elif expresion == "mareado":      # espirales
        for cx in (izq, der):
            pts = [_p(cx + math.cos(a) * a * 4.2, y + math.sin(a) * a * 4.2) for a in [k * 0.25 for k in range(0, 44)]]
            d.line(pts, fill=TINTA, width=9 * ESCALA, joint="curve")
    elif expresion == "guino":
        _ojo_abierto(d, izq, y)
        _arco(d, der, y + 18, 36, 200, 340, 18)
    elif expresion == "dormido":
        for cx in (izq, der):
            _arco(d, cx, y - 6, 34, 20, 160, 14)
    _guardar(img, f"ojos_{expresion}.png")


def boca(nivel=None, expresion=None):
    """nivel 0-9 (hablar) o una expresion (su boca quieta)."""
    img, d = _lienzo()
    cx, cy = 256, 330
    if expresion in ("feliz", "guino"):
        d.chord([*_p(cx - 62, cy - 50), *_p(cx + 62, cy + 50)], 0, 180, fill=BOCA, outline=TINTA, width=9 * ESCALA)
        d.chord([*_p(cx - 30, cy + 14), *_p(cx + 30, cy + 46)], 0, 180, fill=LENGUA)
    elif expresion == "triste":
        _arco(d, cx, cy + 40, 44, 220, 320, 13)
    elif expresion == "enojado":
        d.rounded_rectangle([*_p(cx - 52, cy - 14), *_p(cx + 52, cy + 22)], radius=12 * ESCALA, fill=BLANCO, outline=TINTA, width=9 * ESCALA)
        for k in (-26, 0, 26):
            d.line([*_p(cx + k, cy - 14), *_p(cx + k, cy + 22)], fill=TINTA, width=5 * ESCALA)
    elif expresion == "sorprendido":
        d.ellipse([*_p(cx - 26, cy - 30), *_p(cx + 26, cy + 34)], fill=BOCA, outline=TINTA, width=9 * ESCALA)
    elif expresion == "mareado":
        pts = [_p(cx - 56 + k * 4, cy + math.sin(k * 0.6) * 10) for k in range(29)]
        d.line(pts, fill=TINTA, width=11 * ESCALA, joint="curve")
    elif expresion in ("pensando", "dormido"):
        d.line([*_p(cx - 24, cy + 4), *_p(cx + 30, cy - 4)], fill=TINTA, width=11 * ESCALA)
    elif nivel == 0 or expresion == "normal":
        _arco(d, cx, cy - 26, 40, 30, 150, 12)
    else:
        w, h = 30 + nivel * 3.4, 8 + nivel * 7.2
        d.ellipse([*_p(cx - w, cy - h * 0.45), *_p(cx + w, cy + h * 0.75)], fill=BOCA, outline=TINTA, width=9 * ESCALA)
        if nivel >= 4:   # dientes de arriba
            d.chord([*_p(cx - w * 0.75, cy - h * 0.42), *_p(cx + w * 0.75, cy - h * 0.42 + 26)], 0, 180, fill=BLANCO)
        if nivel >= 6:
            d.chord([*_p(cx - w * 0.5, cy + h * 0.2), *_p(cx + w * 0.5, cy + h * 0.7)], 180, 360, fill=LENGUA)
    _guardar(img, f"boca_{expresion or nivel}.png")


def todas():
    os.makedirs(DIR, exist_ok=True)
    for e in EXPRESIONES:
        ojos(e)
        boca(expresion=e)
    for n in range(10):
        boca(nivel=n)


if __name__ == "__main__":
    todas()
    print("caras en", DIR)
