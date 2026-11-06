#!/usr/bin/env python3
"""
CLI del Estudio: video por etapas con TUS recursos y Claude CLI como cerebro.

    material -> guion (Claude) -> voz (TTS) -> recursos (Claude los mira)
             -> asignacion (Claude elige un recurso por frase) -> render

Cada etapa queda guardada en un PROYECTO del servidor. Volver a lanzar con
--proyecto ID solo rehace lo que cambio (p. ej. otra musica = solo el acabado).
Asi un agente (Hermes, n8n, cron) puede parar en una etapa, dejar que una
persona revise en la web, y seguir despues.

Ejemplos:
  # De cero: material + carpeta de imagenes/videos -> MP4
  python estudio_cli.py --titulo "Resumen de mercados" --material-archivo notas.txt \\
      --recursos-dir ./mis_recursos --duracion 60 --out ./videos

  # Tu propio guion, leido tal cual
  python estudio_cli.py --titulo "Mi video" --guion-archivo guion.txt --recursos-dir ./media

  # Parar tras el guion para revisarlo en la web, y seguir luego
  python estudio_cli.py --titulo "X" --material-archivo notas.txt --hasta guion
  python estudio_cli.py --proyecto 3f9a2c1b7d10 --out ./videos

  # Contenido creado a mano en Flow / extension: 1) prompts y script.json
  python estudio_cli.py --titulo "X" --material-archivo notas.txt --asignacion escenas \\
      --generar imagenes_videos --estilo "fotografia documental" --hasta escenas --exportar-json ./mi-proyecto/script.json
  #   2) (generas con la extension en ./mi-proyecto) 3) subir y montar:
  python estudio_cli.py --proyecto <id> --contenido-dir ./mi-proyecto --out ./videos

  # Perfil con params por etapa (ver estudio_perfil.example.json)
  python estudio_cli.py --perfil estudio_perfil.json --titulo "X" --material "..." --recursos-dir ./media

Salida: codigo 0 si termina bien, 1 si falla. Imprime el id del proyecto al
principio (PROYECTO=<id>) para poder retomarlo.

Variables de entorno:
  MPT_API_BASE    URL base de la API v1 (default: https://studio.saraviamtech.com/api/motor)
  MPT_BASIC_AUTH  usuario:password si hay auth basica delante (opcional)
"""

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

import requests

DEFAULT_API_BASE = os.environ.get("MPT_API_BASE", "https://studio.saraviamtech.com/api/motor")
ETAPAS = ["guion", "voz", "escenas", "recursos", "asignacion", "render"]
EXT = {".jpg", ".jpeg", ".png", ".bmp", ".webp", ".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v"}


def _auth():
    raw = os.environ.get("MPT_BASIC_AUTH", "").strip()
    if raw and ":" in raw:
        u, p = raw.split(":", 1)
        return (u, p)
    return None


class Api:
    def __init__(self, base):
        self.base = base.rstrip("/") + "/estudio"
        self.s = requests.Session()
        self.s.auth = _auth()

    def _r(self, metodo, ruta, **kw):
        r = self.s.request(metodo, self.base + ruta, timeout=kw.pop("timeout", 120), **kw)
        if r.status_code >= 400:
            try:
                detalle = r.json().get("detail") or r.text
            except ValueError:
                detalle = r.text
            raise RuntimeError(f"{metodo} {ruta} -> {r.status_code}: {str(detalle)[:400]}")
        return r

    def crear(self, titulo):
        return self._r("POST", "/proyectos", json={"titulo": titulo}).json()

    def ver(self, pid):
        return self._r("GET", f"/proyectos/{pid}").json()

    def editar(self, pid, cambios):
        return self._r("PATCH", f"/proyectos/{pid}", json=cambios).json()

    def ejecutar(self, pid, hasta, forzar=()):
        return self._r("POST", f"/proyectos/{pid}/ejecutar", json={"hasta": hasta, "forzar": list(forzar)}).json()

    def subir(self, pid, rutas):
        archivos = [("archivos", (p.name, open(p, "rb"))) for p in rutas]
        try:
            return self._r("POST", f"/proyectos/{pid}/recursos", files=archivos, timeout=1800).json()
        finally:
            for _, (_, f) in archivos:
                f.close()

    def subir_a(self, pid, rutas, sub):
        archivos = [("archivos", (p.name, open(p, "rb"))) for p in rutas]
        try:
            return self._r("POST", f"/proyectos/{pid}/recursos", params={"sub": sub}, files=archivos, timeout=1800).json()
        finally:
            for _, (_, f) in archivos:
                f.close()

    def script_json(self, pid, destino: Path):
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_bytes(self._r("GET", f"/proyectos/{pid}/script.json").content)

    def subidos(self, pid):
        return {a["nombre"] for a in self._r("GET", f"/proyectos/{pid}/recursos").json()["archivos"]}

    def descargar(self, pid, destino: Path):
        with self._r("GET", f"/proyectos/{pid}/descargar", stream=True, timeout=600) as r:
            with open(destino, "wb") as f:
                for trozo in r.iter_content(1 << 20):
                    f.write(trozo)


def _slug(t, n=50):
    return re.sub(r"[^a-z0-9]+", "-", t.lower()).strip("-")[:n] or "video"


def _leer(ruta):
    return Path(ruta).read_text(encoding="utf-8")


def construir_params(args, perfil):
    params = {e: dict(perfil.get(e) or {}) for e in ETAPAS}
    g, v, r, a, rd = (params[e] for e in ("guion", "voz", "recursos", "asignacion", "render"))
    if args.material is not None:
        g["material"] = args.material
    if args.material_archivo:
        g["material"] = _leer(args.material_archivo)
    if args.guion_archivo:
        g["material"] = _leer(args.guion_archivo)
        g["modo"] = "literal"
    if args.minutos is not None:
        args.duracion = int(round(min(args.minutos, 180) * 60))
    for clave, valor in [("instrucciones", args.instrucciones), ("duracion_s", args.duracion),
                         ("idioma", args.idioma), ("modelo", args.modelo), ("esfuerzo", args.esfuerzo)]:
        if valor is not None:
            g[clave] = valor
    for clave, valor in [("voz", args.voz), ("velocidad", args.velocidad),
                         ("plano_min_s", args.plano_min), ("plano_max_s", args.plano_max)]:
        if valor is not None:
            v[clave] = valor
    if args.carpeta_servidor is not None:
        r["carpeta"] = args.carpeta_servidor
    if args.sin_vision:
        r["vision"] = False
    if args.criterio is not None:
        a["criterio"] = args.criterio
    esc = params["escenas"]
    for clave, valor in [("generar", args.generar), ("estilo", args.estilo), ("segundos", args.segundos_escena),
                         ("idioma_prompts", args.idioma_prompts)]:
        if valor is not None:
            esc[clave] = valor
    if args.asignacion is not None:
        a["modo"] = args.asignacion
    for clave, valor in [("aspecto", args.formato), ("encaje", args.encaje), ("zoom", args.zoom),
                         ("musica", args.musica), ("musica_volumen", args.musica_volumen),
                         ("volumen_voz", args.volumen_voz), ("sub_posicion", args.sub_posicion),
                         ("tam_fuente", args.tam_fuente), ("fuente", args.fuente),
                         ("codec", args.codec), ("acabado", args.acabado)]:
        if valor is not None:
            rd[clave] = valor
    if args.sin_subtitulos:
        rd["subtitulos"] = False
    return {e: p for e, p in params.items() if p}


def subir_carpeta(api, pid, carpeta):
    rutas = sorted([p for p in Path(carpeta).iterdir() if p.is_file() and p.suffix.lower() in EXT],
                   key=lambda p: p.name.lower())
    ya = api.subidos(pid)
    nuevas = [p for p in rutas if p.name not in ya]
    print(f"recursos: {len(rutas)} en la carpeta, {len(nuevas)} por subir", flush=True)
    for i in range(0, len(nuevas), 20):
        lote = nuevas[i:i + 20]
        res = api.subir(pid, lote)
        print(f"  subidos {i + len(lote)}/{len(nuevas)}"
              + (f" (rechazados: {res['rechazados']})" if res.get("rechazados") else ""), flush=True)


def subir_contenido(api, pid, carpeta):
    """Sube la carpeta de la extension respetando images/ y videos/ (y lo suelto)."""
    base = Path(carpeta)
    grupos = {"": [], "images": [], "videos": []}
    for p in sorted(base.rglob("*"), key=lambda x: str(x).lower()):
        if p.is_file() and p.suffix.lower() in EXT:
            partes = [x.lower() for x in p.relative_to(base).parts[:-1]]
            sub = "videos" if "videos" in partes else "images" if "images" in partes else ""
            grupos[sub].append(p)
    for sub, rutas in grupos.items():
        for i in range(0, len(rutas), 20):
            api.subir_a(pid, rutas[i:i + 20], sub)
        if rutas:
            print(f"contenido: {len(rutas)} archivos en {sub or '(raiz)'}", flush=True)


def esperar(api, pid, timeout):
    t0 = ultimo_cambio = time.time()
    visto = None
    while True:
        v = api.ver(pid)
        trab = v.get("trabajo")
        if not trab:
            return v
        linea = f"[{trab.get('etapa') or '...'}] {trab.get('progreso', 0)}% {trab.get('mensaje', '')}"
        if linea != visto:
            print(linea, flush=True)
            visto, ultimo_cambio = linea, time.time()
        elif time.time() - ultimo_cambio >= 120:
            # Latido: un orquestador no debe creer que se colgo mientras renderiza.
            print(f"  ... sigue trabajando ({int(time.time() - t0)}s)", flush=True)
            ultimo_cambio = time.time()
        if time.time() - t0 > timeout:
            raise TimeoutError(f"sin terminar tras {timeout}s (el proyecto {pid} sigue en el servidor)")
        time.sleep(3)


def main():
    ap = argparse.ArgumentParser(description="Estudio por etapas con tus recursos y Claude CLI.",
                                 formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    ap.add_argument("--api", default=DEFAULT_API_BASE, help="URL base API v1 (o MPT_API_BASE)")
    ap.add_argument("--proyecto", help="id de un proyecto existente para continuarlo")
    ap.add_argument("--perfil", help="JSON con params por etapa {guion:{}, voz:{}, ...}")
    ap.add_argument("--titulo")
    ap.add_argument("--hasta", default="render", choices=ETAPAS, help="ultima etapa a ejecutar")
    ap.add_argument("--forzar", default="", help="etapas a rehacer aunque esten al dia (coma)")
    ap.add_argument("--out", default="./videos_estudio", help="carpeta de salida del MP4")
    ap.add_argument("--timeout", type=int, default=14400, help="segundos de espera maxima (default 4 h)")
    g = ap.add_argument_group("guion")
    g.add_argument("--material", help="texto del material (Claude redacta el guion)")
    g.add_argument("--material-archivo")
    g.add_argument("--guion-archivo", help="tu guion, se lee TAL CUAL (modo literal)")
    g.add_argument("--instrucciones")
    g.add_argument("--duracion", type=int, help="duracion objetivo en segundos")
    g.add_argument("--minutos", type=float, help="duracion objetivo en minutos (hasta 180)")
    g.add_argument("--idioma", help="es, en, pt, fr, it, de")
    g.add_argument("--modelo", choices=["haiku", "sonnet", "opus"])
    g.add_argument("--esfuerzo", choices=["low", "medium", "high"])
    v = ap.add_argument_group("voz")
    v.add_argument("--voz", help="p. ej. es-MX-JorgeNeural-Male")
    v.add_argument("--velocidad", type=float)
    v.add_argument("--plano-min", type=float, help="segundos minimos por plano")
    v.add_argument("--plano-max", type=float, help="segundos maximos por plano")
    r = ap.add_argument_group("recursos y asignacion")
    r.add_argument("--recursos-dir", help="carpeta LOCAL cuyos archivos se suben al proyecto")
    r.add_argument("--carpeta-servidor", help="carpeta que YA esta en el servidor")
    r.add_argument("--sin-vision", action="store_true", help="no pedir a Claude que mire los recursos")
    r.add_argument("--asignacion", choices=["claude", "orden", "escenas"],
                   help="escenas = contenido creado a mano (Flow/extension), un archivo por escena")
    r.add_argument("--contenido-dir", help="carpeta con lo creado (formato extension: images/ videos/)")
    e = ap.add_argument_group("escenas (contenido creado en Flow / extension)")
    e.add_argument("--generar", choices=["no", "imagenes", "imagenes_videos"], help="que prompts escribe Claude")
    e.add_argument("--estilo", help="estilo visual para todas las imagenes")
    e.add_argument("--segundos-escena", type=float, help="duracion objetivo de cada escena")
    e.add_argument("--idioma-prompts", choices=["en", "es", "pt"])
    e.add_argument("--exportar-json", help="guardar aqui el script.json para la extension")
    r.add_argument("--criterio", help="indicacion para elegir recursos")
    rd = ap.add_argument_group("render")
    rd.add_argument("--formato", choices=["9:16", "16:9", "1:1"])
    rd.add_argument("--encaje", choices=["desenfoque", "recortar", "negro"])
    rd.add_argument("--zoom", type=float)
    rd.add_argument("--musica", help='"random", "" (sin musica) o nombre de un MP3 subido')
    rd.add_argument("--musica-volumen", type=float)
    rd.add_argument("--volumen-voz", type=float)
    rd.add_argument("--sin-subtitulos", action="store_true")
    rd.add_argument("--sub-posicion", choices=["bottom", "center", "top", "custom"])
    rd.add_argument("--tam-fuente", type=int)
    rd.add_argument("--fuente")
    rd.add_argument("--codec")
    rd.add_argument("--acabado", choices=["rapido", "clasico"])
    args = ap.parse_args()

    api = Api(args.api)
    perfil = json.loads(_leer(args.perfil)) if args.perfil else {}
    try:
        if args.proyecto:
            vista = api.ver(args.proyecto)
            pid = args.proyecto
        else:
            if not (args.material or args.material_archivo or args.guion_archivo or perfil.get("guion", {}).get("material")):
                ap.error("falta el material: --material, --material-archivo o --guion-archivo")
            vista = api.crear(args.titulo or "Video")
            pid = vista["proyecto"]["id"]
        print(f"PROYECTO={pid}", flush=True)

        cambios = {"params": construir_params(args, perfil)}
        if args.titulo and args.proyecto:
            cambios["titulo"] = args.titulo
        if cambios["params"] or "titulo" in cambios:
            api.editar(pid, cambios)
        if args.recursos_dir:
            subir_carpeta(api, pid, args.recursos_dir)
        if args.contenido_dir:
            subir_contenido(api, pid, args.contenido_dir)

        forzar = [e for e in args.forzar.split(",") if e.strip()]
        api.ejecutar(pid, args.hasta, forzar)
        vista = esperar(api, pid, args.timeout)

        fallo = False
        for e in [x for x in ETAPAS if x in _necesarias(args.hasta)]:
            et = vista["etapas"][e]
            print(f"  {e:<11} {et['estado']}" + (f"  ERROR: {et['error']}" if et.get("error") else ""))
            fallo = fallo or et["estado"] != "ok"
        if fallo:
            print("\n".join(vista.get("log", [])[-15:]))
            return 1
        if args.exportar_json:
            api.script_json(pid, Path(args.exportar_json))
            print(f"script.json -> {args.exportar_json}", flush=True)
        if args.hasta == "render":
            out = Path(args.out)
            out.mkdir(parents=True, exist_ok=True)
            destino = out / f"{_slug(vista['proyecto']['titulo'])}-{pid[:6]}.mp4"
            api.descargar(pid, destino)
            info = vista["etapas"]["render"]["salida"]
            print(f"LISTO {destino}  ({info['duracion']:.1f}s, {info['tam_mb']} MB)", flush=True)
        else:
            print(f"LISTO hasta «{args.hasta}». Revisa en la web y sigue con: --proyecto {pid}", flush=True)
        return 0
    except Exception as e:  # noqa: BLE001
        print(f"ERROR: {e}", file=sys.stderr, flush=True)
        return 1


def _necesarias(hasta):
    deps = {"guion": [], "voz": ["guion"], "escenas": ["voz"], "recursos": [],
            "asignacion": ["voz", "recursos"], "render": ["asignacion", "voz"]}
    vistas, pila = set(), [hasta]
    while pila:
        e = pila.pop()
        if e not in vistas:
            vistas.add(e)
            pila += deps[e]
    return vistas


if __name__ == "__main__":
    sys.exit(main())
