"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { Copy, Download, Eraser, Film, Loader2, Pencil, Play, Plus, SquarePen, Trash2, X } from "lucide-react";
import { api, mmss, tamano, url, type Espacio, type ResumenProyecto } from "@/lib/api";
import { Accion } from "@/components/ui";
import { MARCA } from "@/lib/marca";

// Ejemplos que rotan en el campo de titulo: el tipo de contenido que hace el Estudio.
const EJEMPLOS = [
  "Resumen semanal de mercados: bolsa, dolar y cripto",
  "Noticias de tecnologia: lo mas importante de la semana",
  "Novela narrada — Capitulo 1: La herencia",
  "Reportaje: la crisis del agua en Latinoamerica",
  "Finanzas personales: como funciona el interes compuesto",
  "Documental: la historia del petroleo en 10 minutos",
  "Analisis: que significa la subida de tasas para tu bolsillo",
  "Cronica: el dia que cambio la industria automotriz",
];

export default function Inicio() {
  const router = useRouter();
  const [proyectos, setProyectos] = useState<ResumenProyecto[] | null>(null);
  const [error, setError] = useState("");
  const [titulo, setTitulo] = useState("");
  const [creando, setCreando] = useState(false);
  const [ejemplo, setEjemplo] = useState(0);
  const [viendo, setViendo] = useState<ResumenProyecto | null>(null);
  const [ocupado, setOcupado] = useState<string | null>(null);
  const [espacio, setEspacio] = useState<Espacio | null>(null);
  const [liberando, setLiberando] = useState(false);
  const [aviso, setAviso] = useState("");

  const cargar = () => {
    api.espacio().then(setEspacio).catch(() => setEspacio(null));
    return api.listar().then((r) => setProyectos(r.proyectos)).catch((e) => setError(String(e.message || e)));
  };
  const liberable = (id: string) => espacio?.proyectos.find((x) => x.id === id)?.liberable || 0;

  useEffect(() => {
    cargar();
  }, []);

  useEffect(() => {
    const t = setInterval(() => setEjemplo((i) => (i + 1) % EJEMPLOS.length), 3500);
    return () => clearInterval(t);
  }, []);

  async function crear(e: React.FormEvent) {
    e.preventDefault();
    setCreando(true);
    try {
      const v = await api.crear(titulo.trim() || "Video sin titulo");
      router.push(`/p/${v.proyecto.id}`);
    } catch (err) {
      setError(String((err as Error).message));
      setCreando(false);
    }
  }

  async function accion(p: ResumenProyecto, fn: () => Promise<unknown>) {
    setOcupado(p.id);
    try {
      await fn();
      await cargar();
    } catch (err) {
      setError(String((err as Error).message));
    } finally {
      setOcupado(null);
    }
  }

  const borrar = (p: ResumenProyecto) =>
    confirm(`¿Borrar «${p.titulo}» y todo lo generado?`) && accion(p, () => api.borrar(p.id));

  const renombrar = (p: ResumenProyecto) => {
    const t = prompt("Nuevo titulo", p.titulo);
    if (t && t.trim() && t !== p.titulo) accion(p, () => api.editar(p.id, { titulo: t.trim() }));
  };

  const liberar = (p: ResumenProyecto) =>
    accion(p, async () => {
      const r = await api.liberar(p.id);
      setAviso(`«${p.titulo}»: ${tamano(r.liberado)} liberados.`);
    });

  async function liberarTodo() {
    if (!espacio || !confirm(
      `¿Liberar ${tamano(espacio.liberable)}? Se borran solo la cache de clips, los archivos intermedios del montaje y las escenas ya dibujadas de la Fábrica. ` +
      "Tus videos finales y lo que subiste no se tocan; si vuelves a montar un video, los clips se rehacen solos.")) return;
    setLiberando(true);
    try {
      const r = await api.liberarTodo();
      setAviso(`${tamano(r.liberado)} liberados en ${r.proyectos} proyectos` +
        (r.ocupados.length ? ` (${r.ocupados.length} trabajando, se saltaron)` : "") + ".");
      await cargar();
    } catch (err) {
      setError(String((err as Error).message));
    } finally {
      setLiberando(false);
    }
  }

  const duplicar = (p: ResumenProyecto) =>
    accion(p, async () => {
      const v = await api.duplicar(p.id);
      router.push(`/p/${v.proyecto.id}`);
    });

  return (
    <main className="mx-auto max-w-6xl px-4 pb-24 pt-12">
      <section className="mb-12 grid gap-8 md:grid-cols-[1.2fr_1fr] md:items-end">
        <div>
          <p className="etiqueta mb-3 flex items-center gap-2">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src={MARCA.logo.icono} alt="" className="h-5 w-5" />
            Estudio de video
          </p>
          <h1 className="font-display text-4xl font-semibold leading-tight tracking-tight md:text-5xl">
            {MARCA.eslogan}
          </h1>
          <p className="mt-4 max-w-xl text-tinta-2">
            Noticias, finanzas, reportajes, novelas narradas… Escribe el material, Claude redacta el guion,
            eliges la voz, subes tus imagenes y videos, y Claude decide que va en cada frase. Cada etapa se
            puede revisar y solo se rehace lo que cambia.
          </p>
        </div>
        <form onSubmit={crear} className="rounded-2xl border border-linea bg-tarjeta p-5 shadow-sm">
          <label className="etiqueta" htmlFor="titulo">Nuevo video</label>
          <input
            id="titulo"
            className="campo mt-2"
            placeholder={`Ej.: ${EJEMPLOS[ejemplo]}`}
            value={titulo}
            onChange={(e) => setTitulo(e.target.value)}
          />
          <button className="boton boton-acento mt-3 w-full justify-center" disabled={creando}>
            {creando ? <Loader2 size={16} className="animate-spin" /> : <Plus size={16} />} Empezar
          </button>
        </form>
      </section>

      <div className="mb-4 flex items-baseline justify-between">
        <h2 className="font-display text-2xl font-semibold">Mis videos</h2>
        <div className="flex flex-wrap items-center justify-end gap-3">
          {proyectos && (
            <span className="text-sm text-tinta-3">
              {proyectos.length} proyectos{espacio ? ` · ${tamano(espacio.total)}` : ""}
            </span>
          )}
          {espacio && (
            <button className="boton boton-linea !py-1.5 text-sm" disabled={liberando || espacio.liberable < 1e6}
              onClick={liberarTodo}
              title="Borra la cache de clips y los archivos intermedios del montaje (se regeneran si hace falta)">
              {liberando ? <Loader2 size={15} className="animate-spin" /> : <Eraser size={15} />}
              {espacio.liberable < 1e6 ? "Nada que liberar" : `Liberar espacio (${tamano(espacio.liberable)})`}
            </button>
          )}
        </div>
      </div>

      {aviso && (
        <p className="mb-4 flex justify-between gap-3 rounded-xl bg-hundido p-3 text-sm text-tinta-2">
          {aviso}
          <button onClick={() => setAviso("")}><X size={16} /></button>
        </p>
      )}

      {error && (
        <p className="mb-4 flex justify-between gap-3 rounded-xl bg-error-suave p-3 text-sm text-error">
          {error}
          <button onClick={() => setError("")}><X size={16} /></button>
        </p>
      )}

      {proyectos === null ? (
        <p className="text-tinta-3">Cargando…</p>
      ) : proyectos.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-linea p-12 text-center text-tinta-2">
          Aun no hay videos. Crea el primero arriba.
        </div>
      ) : (
        <ul className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {proyectos.map((p) => (
            <li key={p.id} className="group flex flex-col overflow-hidden rounded-2xl border border-linea bg-tarjeta transition hover:shadow-md">
              <button
                onClick={() => (p.mp4 ? setViendo(p) : router.push(`/p/${p.id}`))}
                className="relative aspect-video overflow-hidden bg-hundido text-left"
                title={p.mp4 ? "Reproducir" : "Abrir"}
              >
                {p.mp4 ? (
                  <>
                    {p.portada ? (
                      // eslint-disable-next-line @next/next/no-img-element
                      <img src={url.archivo(p.id, p.portada, p.actualizado)} alt="" className="absolute inset-0 h-full w-full bg-black object-contain" loading="lazy" />
                    ) : (
                      <video src={`${url.archivo(p.id, p.mp4, p.actualizado)}#t=1`} className="absolute inset-0 h-full w-full bg-black object-contain" muted preload="metadata" />
                    )}
                    <span className="absolute inset-0 grid place-items-center bg-black/0 transition group-hover:bg-black/30">
                      <span className="grid h-12 w-12 place-items-center rounded-full bg-white/90 text-tinta opacity-0 shadow transition group-hover:opacity-100">
                        <Play size={20} className="ml-0.5" />
                      </span>
                    </span>
                  </>
                ) : (
                  <div className="grid h-full place-items-center text-tinta-3">
                    <div className="flex flex-col items-center gap-1.5">
                      <Film size={28} />
                      <span className="text-xs">Sin video todavia · abrir</span>
                    </div>
                  </div>
                )}
                {p.trabajando && (
                  <span className="latido absolute left-3 top-3 rounded-full bg-acento px-2.5 py-0.5 text-xs font-semibold text-sobre-acento">
                    trabajando
                  </span>
                )}
                {p.duracion ? (
                  <span className="absolute bottom-2 right-2 rounded-md bg-black/70 px-1.5 py-0.5 text-xs text-white">
                    {mmss(p.duracion)}
                  </span>
                ) : null}
              </button>
              <Link href={`/p/${p.id}`} className="block flex-1 p-4">
                <h3 className="line-clamp-1 font-semibold">{p.titulo}</h3>
                <p className="mt-1 text-xs text-tinta-3">Editado {new Date(p.actualizado * 1000).toLocaleString()}</p>
              </Link>
              <div className="flex flex-wrap items-center gap-0.5 border-t border-linea px-1.5 py-1.5">
                {ocupado === p.id ? (
                  <span className="flex items-center gap-2 px-2 py-1.5 text-xs text-tinta-3">
                    <Loader2 size={14} className="animate-spin" /> Un momento…
                  </span>
                ) : (
                  <>
                    <Accion icono={<Play size={14} />} texto="Ver" disabled={!p.mp4} onClick={() => setViendo(p)} />
                    <Accion icono={<Download size={14} />} texto="Descargar" disabled={!p.mp4} href={p.mp4 ? url.descargar(p.id) : undefined} />
                    <Accion icono={<SquarePen size={14} />} texto="Editar" soloIcono derecha href={`/p/${p.id}`} />
                    <Accion icono={<Eraser size={14} />} soloIcono disabled={p.trabajando || liberable(p.id) < 1e6}
                      texto={liberable(p.id) < 1e6 ? "Nada que liberar" : `Liberar espacio (${tamano(liberable(p.id))})`}
                      onClick={() => liberar(p)} />
                    <Accion icono={<Copy size={14} />} texto="Duplicar" soloIcono onClick={() => duplicar(p)} />
                    <Accion icono={<Pencil size={14} />} texto="Renombrar" soloIcono onClick={() => renombrar(p)} />
                    <Accion icono={<Trash2 size={14} />} texto="Borrar" soloIcono peligro onClick={() => borrar(p)} />
                  </>
                )}
              </div>
            </li>
          ))}
        </ul>
      )}

      {viendo && viendo.mp4 && <Reproductor p={viendo} onCerrar={() => setViendo(null)} />}
    </main>
  );
}

function Reproductor({ p, onCerrar }: { p: ResumenProyecto; onCerrar: () => void }) {
  useEffect(() => {
    const tecla = (e: KeyboardEvent) => e.key === "Escape" && onCerrar();
    window.addEventListener("keydown", tecla);
    return () => window.removeEventListener("keydown", tecla);
  }, [onCerrar]);
  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-black/75 p-4" onClick={onCerrar}>
      <div className="flex max-h-[92vh] w-full max-w-3xl flex-col" onClick={(e) => e.stopPropagation()}>
        <div className="mb-3 flex items-center justify-between gap-3 text-white">
          <h3 className="truncate font-display text-lg font-semibold">{p.titulo}</h3>
          <div className="flex shrink-0 gap-2">
            <a href={url.descargar(p.id)} className="boton boton-acento !py-1.5 text-xs"><Download size={14} /> Descargar</a>
            <Link href={`/p/${p.id}`} className="boton !bg-white/15 !py-1.5 text-xs text-white hover:!bg-white/25"><SquarePen size={14} /> Editar</Link>
            <button onClick={onCerrar} className="boton !bg-white/15 !p-2 text-white hover:!bg-white/25" title="Cerrar"><X size={16} /></button>
          </div>
        </div>
        <video
          src={url.archivo(p.id, p.mp4!, p.actualizado)}
          controls
          autoPlay
          className="max-h-[80vh] w-full rounded-xl bg-black object-contain"
        />
      </div>
    </div>
  );
}
