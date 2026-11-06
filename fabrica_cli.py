#!/usr/bin/env python3
"""
CLI de la Fabrica: videos enteros desde un tema (guion por escenas, voz y escenas dibujadas con
codigo: mapas, barras, listas, cifras...). Uno o un lote; espera a que terminen y los descarga.

Ejemplos:
  # Un video
  python fabrica_cli.py --tema "Por que Bolivia no tiene mar" --estilo papel --out ./videos

  # Un lote (un tema por linea), en dos formatos; se hacen de uno en uno en el servidor
  python fabrica_cli.py --temas-archivo temas.txt --nicho finanzas --estilo minimal --formatos 9:16,16:9

  # Ver nichos, estilos y formatos que hay
  python fabrica_cli.py --catalogo

  # Al terminar, abrir cada video en el editor del Estudio (crea un proyecto por video)
  python fabrica_cli.py --tema "..." --editor

  # Retomar videos ya creados (se corto la conexion, o se lanzaron desde la web)
  python fabrica_cli.py --seguir 8f9e617ca583,3413045dfb69 --out ./videos

  # Perfil JSON con las opciones fijas (las flags lo sobreescriben), ver fabrica_perfil.example.json
  python fabrica_cli.py --perfil fabrica_perfil.json --tema "..."

  # Moldes (las opciones guardadas en la web de un video que funciono): listarlos y usar uno;
  # solo cambia el tema (y lo que se pase por flags: --musica, --voz...)
  python fabrica_cli.py --moldes
  python fabrica_cli.py --molde "Zombies stickman" --tema "Dia uno sin internet" --musica "Closing In.mp3"

  # Saga: el siguiente episodio de un video (Dia 1 -> Dia 2); --idea opcional (si no, lo decide Claude)
  python fabrica_cli.py --siguiente 8f9e617ca583 --idea "se acaba el agua"
  # Temporada: varios episodios seguidos (Claude planea la tanda; --final = el ultimo cierra la historia)
  python fabrica_cli.py --siguiente 8f9e617ca583 --episodios 5 --idea "buscan un barco"

  # Videos que se paran antes de montar (molde con clips o "revisar"): por defecto el CLI no se para;
  # con --con-pausa se para, imprime REVISION=<id> y sale con codigo 2; despues se sigue con --montar
  python fabrica_cli.py --montar 8f9e617ca583 --musica random

Salida: codigo 0 si todos terminan bien, 1 si alguno falla, 2 si alguno quedo esperando (REVISION=<id>). Imprime FABRICA=<id> por video al
empezar (para seguirlo en la web) y la ruta de cada MP4 descargado. Junto a cada video deja un
.txt con el titulo y la descripcion para publicar.

Variables de entorno (las mismas que estudio_cli.py):
  MPT_API_BASE    URL base de la API v1 (default: https://studio.saraviamtech.com/api/motor)
  MPT_BASIC_AUTH  usuario:password si hay auth basica delante (opcional)
"""

import argparse
import json
import os
import re
import sys
import time
import unicodedata
from pathlib import Path

import requests

DEFAULT_API_BASE = os.environ.get("MPT_API_BASE", "https://studio.saraviamtech.com/api/motor")
TRABAJANDO = {"en cola", "guion", "voz", "render", "montaje"}
IDIOMAS = {"es": "espanol", "en": "ingles", "pt": "portugues", "fr": "frances", "it": "italiano", "de": "aleman"}


def _auth():
    raw = os.environ.get("MPT_BASIC_AUTH", "").strip()
    if raw and ":" in raw:
        u, p = raw.split(":", 1)
        return (u, p)
    return None


class Api:
    def __init__(self, base):
        self.base = base.rstrip("/") + "/estudio/fabrica"
        self.s = requests.Session()
        self.s.auth = _auth()

    def _r(self, metodo, ruta, **kw):
        timeout = kw.pop("timeout", 120)
        # las consultas se reintentan: el servidor cierra las conexiones quietas y la red puede fallar un momento
        for intento in range(4 if metodo == "GET" else 1):
            try:
                r = self.s.request(metodo, self.base + ruta, timeout=timeout, **kw)
                break
            except requests.ConnectionError:
                if intento == 3 or metodo != "GET":
                    raise
                time.sleep(2 * (intento + 1))
        if r.status_code >= 400:
            try:
                detalle = r.json().get("detail") or r.text
            except ValueError:
                detalle = r.text
            raise RuntimeError(f"{metodo} {ruta} -> {r.status_code}: {str(detalle)[:400]}")
        return r

    def catalogo(self):
        return self._r("GET", "/catalogo").json()

    def moldes(self):
        return self._r("GET", "/moldes").json()["moldes"]

    def siguiente(self, fid, idea=""):
        return [self._r("POST", f"/{fid}/siguiente", json={"idea": idea}).json()]

    def temporada(self, fid, cuantos, idea="", final=False):
        return self._r("POST", f"/{fid}/temporada", json={"cuantos": cuantos, "idea": idea, "final": final}).json()["videos"]

    def montar(self, fid, opciones):
        return [self._r("POST", f"/{fid}/montar", json={"opciones": opciones}).json()]

    def crear(self, opciones):
        return [self._r("POST", "", json=opciones).json()]

    def lote(self, temas, opciones):
        return self._r("POST", "/lote", json={"temas": temas, "opciones": opciones}).json()["videos"]

    def ver(self, fid):
        return self._r("GET", f"/{fid}").json()

    def editor(self, fid, formato):
        # puede tardar si el video es de antes de guardar sus clips (los vuelve a dibujar)
        return self._r("POST", f"/{fid}/editor", json={"formato": formato}, timeout=1800).json()["proyecto"]

    def descargar(self, fid, formato, destino: Path):
        with self._r("GET", f"/{fid}/video/{formato.replace(':', 'x')}", params={"descargar": "true"},
                     stream=True, timeout=600) as r:
            with open(destino, "wb") as f:
                for trozo in r.iter_content(1 << 20):
                    f.write(trozo)


def _slug(t, n=50):
    # sin tildes ("Por qué" -> "por-que", no "por-qu")
    t = "".join(c for c in unicodedata.normalize("NFD", t.lower()) if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]+", "-", t).strip("-")[:n] or "video"


def molde(api, nombre):
    """Opciones de un molde por su nombre (sin importar mayusculas) o su id."""
    for m in api.moldes():
        if nombre.strip().lower() in (m["nombre"].lower(), m["id"]):
            return m["opciones"]
    raise RuntimeError(f"no hay ningun molde «{nombre}» (mira --moldes)")


def opciones(args, perfil):
    o = dict(perfil)
    cambios = {
        "nicho": args.nicho, "serie": args.serie, "marca": args.marca, "presentador": args.presentador, "estilo": args.estilo, "duracion": args.duracion, "voz": args.voz,
        "velocidad": args.velocidad, "musica": args.musica, "musica_volumen": args.musica_volumen,
        "formatos": [f.strip() for f in args.formatos.split(",") if f.strip()] if args.formatos else None,
        "idioma": IDIOMAS.get(args.idioma, args.idioma) if args.idioma else None,
        "subtitulos": False if args.sin_subtitulos else None, "efectos": False if args.sin_efectos else None,
        "nuevos": False if args.sin_nuevos else None,
    }
    o.update({k: v for k, v in cambios.items() if v is not None})
    if "idioma" not in o and o.get("voz"):   # "es-MX-JorgeNeural-Male" -> espanol
        o["idioma"] = IDIOMAS.get(str(o["voz"])[:2], "espanol")
    return o


def esperar(api, fids, timeout):
    """Hasta que todos terminen (listo o error). Imprime cada cambio de estado."""
    t0, visto, latido = time.time(), {}, time.time()
    pendientes = set(fids)
    finales = {}
    while pendientes:
        for fid in sorted(pendientes):
            d = api.ver(fid)
            linea = f"[{fid}] {d['estado']} {d.get('progreso', 0)}% {d.get('mensaje') or ''}".rstrip()
            if linea != visto.get(fid):
                print(linea, flush=True)
                visto[fid], latido = linea, time.time()
            if d["estado"] not in TRABAJANDO:
                finales[fid] = d
        pendientes -= set(finales)
        if not pendientes:
            break
        if time.time() - latido >= 120:
            # Latido: un orquestador no debe creer que se colgo mientras renderiza.
            print(f"  ... sigue trabajando ({int(time.time() - t0)}s)", flush=True)
            latido = time.time()
        if time.time() - t0 > timeout:
            raise TimeoutError(f"sin terminar tras {timeout}s: {', '.join(sorted(pendientes))} (siguen en el servidor)")
        time.sleep(4)   # menos que lo que el servidor guarda una conexion quieta (5 s)
    return finales


def main():
    ap = argparse.ArgumentParser(description="Videos de la Fabrica desde la terminal",
                                 formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    ap.add_argument("--api", default=DEFAULT_API_BASE, help="URL base API v1 (o MPT_API_BASE)")
    ap.add_argument("--catalogo", action="store_true", help="muestra nichos, estilos y formatos y sale")
    ap.add_argument("--tema", action="append", default=[], help="tema del video (se puede repetir: lote)")
    ap.add_argument("--temas-archivo", help="un tema por linea (lote)")
    ap.add_argument("--seguir", help="ids de videos ya creados (coma): esperar y descargar sin crear otros")
    ap.add_argument("--perfil", help="JSON con opciones fijas (nicho, estilo, formatos, voz, musica...)")
    ap.add_argument("--moldes", action="store_true", help="lista los moldes guardados (JSON) y sale")
    ap.add_argument("--molde", help="nombre o id de un molde: sus opciones en lugar del perfil (las flags mandan)")
    ap.add_argument("--siguiente", help="id de un video: hace su siguiente episodio (saga)")
    ap.add_argument("--idea", default="", help="con --siguiente: que pasa en el episodio (opcional)")
    ap.add_argument("--episodios", type=int, default=1,
                    help="con --siguiente: cuantos episodios seguidos (Claude planea la tanda; maximo 10)")
    ap.add_argument("--final", action="store_true", help="con --episodios: el ultimo cierra la historia")
    ap.add_argument("--montar", help="id de un video parado antes de montar: lo monta (con --musica/--voz si se dan)")
    ap.add_argument("--con-pausa", action="store_true",
                    help="respetar la pausa antes de montar del molde (clips/revisar): sale con REVISION=<id>")
    ap.add_argument("--nicho", help="mapas, datos, curiosidades, finanzas, historia, ciencia, animales, tecnologia, "
                                    "misterios (ver --catalogo)")
    ap.add_argument("--serie", help="mitos, abuela, estafas, historias, noticias, explicador, top (formato fijo; opcional)")
    ap.add_argument("--presentador", help="leo, ana, max o sol: personaje que habla abajo a la derecha (opcional)")
    ap.add_argument("--marca", help="nombre del canal para el cierre (opcional)")
    ap.add_argument("--estilo", help="papel, oscuro, documental, periodico, pizarra, cuaderno, minimal, pop, neon, terminal")
    ap.add_argument("--formatos", help="9:16,16:9,1:1 (coma)")
    ap.add_argument("--duracion", type=int, help="segundos aproximados (20-600; mas de 120 = video largo por capitulos)")
    ap.add_argument("--voz", help="voz de Microsoft (es-ES-AlvaroNeural-Male)")
    ap.add_argument("--velocidad", type=float)
    ap.add_argument("--idioma", help="es, en, pt... (si no, sale de la voz)")
    ap.add_argument("--musica", help='"random", "" (sin musica) o el nombre de una cancion del servidor')
    ap.add_argument("--musica-volumen", type=float)
    ap.add_argument("--sin-subtitulos", action="store_true")
    ap.add_argument("--sin-efectos", action="store_true")
    ap.add_argument("--sin-nuevos", action="store_true", help="no pedir dibujos nuevos a Nano Banana")
    ap.add_argument("--editor", action="store_true", help="al terminar, abrir cada video en el editor del Estudio")
    ap.add_argument("--no-descargar", action="store_true", help="no bajar los MP4 (solo esperar)")
    ap.add_argument("--out", default="./videos_fabrica", help="carpeta de salida")
    ap.add_argument("--timeout", type=int, default=14400, help="segundos de espera maxima (default 4 h)")
    args = ap.parse_args()
    api = Api(args.api)

    if args.catalogo:
        print(json.dumps(api.catalogo(), ensure_ascii=False, indent=1))
        return 0
    if args.moldes:
        print(json.dumps([{"nombre": m["nombre"], "id": m["id"], **m["opciones"]} for m in api.moldes()], ensure_ascii=False, indent=1))
        return 0
    if args.seguir:
        videos = [api.ver(f.strip()) for f in args.seguir.split(",") if f.strip()]
        return terminar(api, args, videos)
    if args.montar:
        cambios = {k: v for k, v in {"musica": args.musica, "voz": args.voz}.items() if v is not None}
        return terminar(api, args, api.montar(args.montar.strip(), cambios))
    if args.siguiente:
        if args.episodios > 1:
            videos = api.temporada(args.siguiente.strip(), args.episodios, args.idea, args.final)
        else:
            videos = api.siguiente(args.siguiente.strip(), args.idea)
        for v in videos:
            print(f"FABRICA={v['id']}  {v['titulo']}", flush=True)
        return terminar(api, args, videos)
    temas = [t.strip() for t in args.tema if t.strip()]
    if args.temas_archivo:
        temas += [t.strip() for t in Path(args.temas_archivo).read_text(encoding="utf-8").splitlines() if t.strip()]
    if not temas:
        ap.error("falta --tema o --temas-archivo")
    perfil = json.loads(Path(args.perfil).read_text(encoding="utf-8")) if args.perfil else {}
    if args.molde:
        perfil = molde(api, args.molde)
    o = opciones(args, perfil)
    if not args.con_pausa:   # sin nadie delante no se pueden subir clips: el video sale entero (con fotos)
        o.update(revisar=False, clips=False)

    videos = api.crear({**o, "tema": temas[0]}) if len(temas) == 1 else api.lote(temas, o)
    for v in videos:
        print(f"FABRICA={v['id']}  {v['titulo']}", flush=True)
    return terminar(api, args, videos)


def terminar(api, args, videos):
    """Espera a los videos, descarga los que salen bien y, si se pide, los abre en el editor."""
    finales = esperar(api, [v["id"] for v in videos], args.timeout)

    out = Path(args.out)
    fallos = esperando = 0
    for v in videos:
        d = finales[v["id"]]
        if d["estado"] == "revision":
            esperando += 1
            print(f"REVISION={v['id']}  {d['titulo']} (sube clips/voz en la web o sigue con --montar {v['id']})", flush=True)
            continue
        if d["estado"] != "listo":
            fallos += 1
            print(f"ERROR [{v['id']}] {d.get('error') or d['estado']}", file=sys.stderr, flush=True)
            continue
        base = f"{_slug(d['titulo'])}-{v['id'][:8]}"
        if not args.no_descargar:
            out.mkdir(parents=True, exist_ok=True)
            for video in d.get("videos") or []:
                destino = out / f"{base}-{video['formato'].replace(':', 'x')}.mp4"
                api.descargar(v["id"], video["formato"], destino)
                print(f"VIDEO={destino}", flush=True)
            g = d.get("guion") or {}
            (out / f"{base}.txt").write_text(f"{g.get('titulo') or d['titulo']}\n\n{g.get('descripcion') or ''}\n", encoding="utf-8")
        if args.editor:
            print(f"PROYECTO={api.editor(v['id'], (d.get('videos') or [{}])[0].get('formato'))}  ({d['titulo']})", flush=True)
    return 1 if fallos else 2 if esperando else 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (RuntimeError, TimeoutError, requests.RequestException) as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)
