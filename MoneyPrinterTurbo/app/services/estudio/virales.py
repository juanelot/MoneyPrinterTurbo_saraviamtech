"""Ideas virales: que videos de otras cuentas funcionan MUCHO mejor de lo normal en esa cuenta (outliers) y por que.

analizar(urls)  -> los ultimos shorts de cada cuenta (yt-dlp, sin descargar nada), su mediana de vistas y los que
                   la superan 3 veces o mas (y pasan de 10.000 vistas): esos temas ya han demostrado que gustan.
detalle(url)    -> de un video: likes y comentarios por cada mil vistas, la frase de sus 3 primeros segundos (de los
                   subtitulos automaticos) y sus comentarios mas votados.
a_temas(...)    -> Claude convierte los elegidos en temas PROPIOS para un nicho de la Fabrica (otro angulo, nunca
                   copiar) y los deja en el banco de temas.

El ultimo analisis se guarda en storage/estudio/virales.json para no repetir la consulta al volver a la pagina.
"""

import json
import re
import statistics
import time
import urllib.request

from loguru import logger

from app.services import claude_cli
from app.services.estudio import almacen

VECES = 3.0          # un outlier hace al menos 3 veces la mediana de su cuenta
VISTAS_MIN = 10_000
POR_CUENTA = 60      # ultimos videos que se miran de cada cuenta
GUARDADO = almacen.raiz("virales.json")


def _yt():
    import yt_dlp   # solo hace falta aqui
    return yt_dlp


def _url_cuenta(texto):
    """@cuenta, enlace de canal o de TikTok. En YouTube se miran sus Shorts."""
    t = str(texto or "").strip()
    if not t:
        return None
    if t.startswith("@"):
        t = "https://www.youtube.com/" + t
    if not t.startswith("http"):
        t = "https://" + t
    if re.match(r"https?://(www\.)?youtube\.com/(@[^/]+|channel/[^/]+|c/[^/]+)/?$", t):
        t = t.rstrip("/") + "/shorts"
    return t


def _cuenta(url):
    yt = _yt()
    with yt.YoutubeDL({"extract_flat": "in_playlist", "quiet": True, "no_warnings": True, "playlistend": POR_CUENTA,
                       "socket_timeout": 20}) as y:
        info = y.extract_info(url, download=False)
    nombre = info.get("channel") or info.get("uploader") or info.get("title") or url
    videos = []
    for e in info.get("entries") or []:
        if not e or not e.get("view_count"):
            continue
        videos.append({"id": e.get("id"), "titulo": e.get("title") or "", "vistas": int(e["view_count"]),
                       "url": e.get("url") or e.get("webpage_url") or "", "cuenta": nombre})
    mediana = statistics.median(v["vistas"] for v in videos) if videos else 0
    for v in videos:
        v["veces"] = round(v["vistas"] / mediana, 1) if mediana else 0
    return {"nombre": nombre, "url": url, "seguidores": info.get("channel_follower_count"), "mediana": int(mediana),
            "n": len(videos)}, videos


def analizar(urls):
    urls = [u for u in dict.fromkeys(_url_cuenta(x) for x in (urls or [])) if u][:10]
    if not urls:
        raise ValueError("pega al menos una cuenta (@nombre o enlace)")
    cuentas, outliers, errores = [], [], []
    for u in urls:
        if "instagram.com" in u:
            # Instagram no deja listar los reels de un perfil sin iniciar sesion
            errores.append(f"{u}: Instagram no deja ver sus reels sin cuenta; usa el TikTok o el canal de YouTube de esa cuenta")
            continue
        try:
            c, videos = _cuenta(u)
        except Exception as e:  # noqa: BLE001 -- una cuenta que falla no para las demas
            logger.warning(f"virales: {u}: {e}")
            errores.append(f"{u}: {str(e)[-160:]}")
            continue
        cuentas.append(c)
        outliers += [v for v in videos if v["veces"] >= VECES and v["vistas"] >= VISTAS_MIN]
    outliers.sort(key=lambda v: v["veces"], reverse=True)
    resultado = {"cuentas": cuentas, "videos": outliers, "errores": errores, "fecha": time.time(),
                 "urls": urls, "criterio": f">= {VECES:g}x la mediana de su cuenta y >= {VISTAS_MIN:,} vistas".replace(",", ".")}
    almacen.escribir_json(GUARDADO, resultado)
    return resultado


def ultimo():
    return almacen.leer_json(GUARDADO, None)


def _gancho(info):
    """Lo que se dice (o se lee) en los 3 primeros segundos, de los subtitulos (los puestos o los automaticos)."""
    for fuente in (info.get("subtitles") or {}, info.get("automatic_captions") or {}):
        idiomas = sorted(fuente, key=lambda k: (not k.startswith(("es", "en")), "-orig" not in k, k))
        for idioma in idiomas[:3]:
            pista = next((f for f in fuente[idioma] if f.get("ext") == "json3"), None)
            if not pista:
                continue
            try:
                with urllib.request.urlopen(pista["url"], timeout=15) as r:
                    datos = json.loads(r.read().decode("utf-8"))
            except Exception:  # noqa: BLE001
                continue
            palabras = []
            for ev in datos.get("events") or []:
                t0 = ev.get("tStartMs", 0)
                for s in ev.get("segs") or []:
                    if t0 + s.get("tOffsetMs", 0) <= 3000:
                        palabras.append(s.get("utf8", ""))
            frase = re.sub(r"\s+", " ", "".join(palabras)).strip()
            if frase:
                return frase
    return ""


def detalle(url):
    yt = _yt()
    opciones = {"quiet": True, "no_warnings": True, "skip_download": True, "socket_timeout": 20, "getcomments": True,
                "extractor_args": {"youtube": {"max_comments": ["15", "15", "0", "0"], "comment_sort": ["top"]}}}
    with yt.YoutubeDL(opciones) as y:
        info = y.extract_info(url, download=False)
    vistas = info.get("view_count") or 0
    por_mil = lambda n: round(n * 1000 / vistas, 1) if vistas and n is not None else None   # noqa: E731
    comentarios = sorted(info.get("comments") or [], key=lambda c: c.get("like_count") or 0, reverse=True)
    return {
        "titulo": info.get("title") or "", "vistas": vistas, "duracion": info.get("duration"),
        "likes": info.get("like_count"), "comentarios": info.get("comment_count"),
        "likes_mil": por_mil(info.get("like_count")), "comentarios_mil": por_mil(info.get("comment_count")),
        "gancho": _gancho(info), "descripcion": (info.get("description") or "")[:400],
        "top": [{"texto": (c.get("text") or "")[:240], "likes": c.get("like_count") or 0} for c in comentarios[:8]],
    }


def a_temas(videos, nicho, serie=""):
    """Claude saca de los videos elegidos (titulo, gancho, comentarios) temas propios para la Fabrica y los
    anade al banco del nicho."""
    from app.services.estudio import fabrica   # evita el import circular
    if nicho not in fabrica.NICHOS:
        raise ValueError("nicho no valido")
    filas = [v for v in (videos or []) if isinstance(v, dict) and v.get("titulo")][:20]
    if not filas:
        raise ValueError("elige al menos un video")
    s = fabrica.SERIES.get(serie or "")
    ya = fabrica._hechos(nicho, cuantos=60) + [i["tema"] for i in fabrica.ideas(nicho)]
    lineas = []
    for v in filas:
        extra = []
        if v.get("gancho"):
            extra.append(f"empieza diciendo: \"{v['gancho']}\"")
        if v.get("top"):
            extra.append("comentarios: " + " | ".join(str(c.get("texto", ""))[:100] for c in v["top"][:3]))
        lineas.append(f"- \"{v['titulo']}\" ({v.get('veces', '?')}x su media)" + (f"; {'; '.join(extra)}" if extra else ""))
    prompt = (
        f"Estos videos cortos de otras cuentas funcionaron mucho mejor de lo normal:\n" + "\n".join(lineas) + "\n\n"
        f"Para cada uno, piensa POR QUE funciono (la curiosidad que abre, la emocion, la cifra) y propon un tema "
        f"PROPIO para nuestro canal del nicho {fabrica.NICHOS[nicho]['nombre']} ({fabrica.NICHOS[nicho]['descripcion']})"
        + (f", serie {s['nombre']}" if s else "") + " que aproveche lo mismo con otro asunto u otro angulo. Nunca copies el "
        "video: ni su titulo ni su guion. Temas concretos (nombre propio, lugar o cifra) que se cuenten con datos reales.\n"
        + ("No repitas estos (ya hechos o en el banco):\n" + "\n".join(f"- {t}" for t in ya) + "\n" if ya else "")
        + 'Responde SOLO con JSON: [{"tema": "el tema en una frase", "gancho": "primera frase, maximo 12 palabras", '
        '"porque": "por que funcionara, 1 frase"}]')
    crudo = claude_cli.extraer_json(claude_cli.ejecutar(prompt, modelo="sonnet", esfuerzo="low", tiempo_max_s=180))
    nuevas = [{"tema": str(x.get("tema") or "").strip()[:200], "gancho": str(x.get("gancho") or "").strip()[:120],
               "porque": str(x.get("porque") or "").strip()[:200], "serie": serie or "", "creado": time.time(),
               "origen": "virales"}
              for x in (crudo if isinstance(crudo, list) else []) if isinstance(x, dict) and str(x.get("tema") or "").strip()]
    return fabrica.al_banco(nicho, nuevas, ya)
