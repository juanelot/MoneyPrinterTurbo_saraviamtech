"use client";

// Biblioteca de dibujos de la Fabrica: las pegatinas (personajes y objetos que se ponen encima del mapa) y las
// ilustraciones (escenas a pantalla completa). Claude elige de aqui al escribir el guion. Se pueden crear nuevas
// con Nano Banana (Flow, solo en el PC local) o subir imagenes propias (tambien en el VPS).

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { ArrowLeft, ChevronLeft, ChevronRight, ImagePlus, Loader2, Search, Sparkles, Trash2, Upload } from "lucide-react";
import { AvisoError, Campo, Segmentado } from "@/components/ui";
import { biblioteca, type Biblioteca, type TipoDibujo } from "@/lib/api";

const NICHOS: Record<string, string> = {
  mapas: "Mapas e historia", datos: "Datos", curiosidades: "Curiosidades", finanzas: "Finanzas", historia: "Historia",
  ciencia: "Ciencia y espacio", animales: "Animales", tecnologia: "Tecnologia", misterios: "Misterios",
};
const FAMILIAS: Record<string, string> = {
  madera: "Madera", plano: "Plano", grabado: "Grabado", stickman: "Stickman", retrotv: "Retro TV", thriller: "Thriller",
};
const POR_PAGINA = { pegatinas: 35, ilustraciones: 18 };

export default function PaginaBiblioteca() {
  const [datos, setDatos] = useState<Biblioteca | null>(null);
  const [tipo, setTipo] = useState<TipoDibujo>("pegatinas");
  const [buscar, setBuscar] = useState("");
  const [nicho, setNicho] = useState("");
  const [grupo, setGrupo] = useState("");
  const [familia, setFamilia] = useState("madera");
  const [pagina, setPagina] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [version, setVersion] = useState(0);
  // crear con Nano Banana
  const [descripcion, setDescripcion] = useState("");
  const [nombre, setNombre] = useState("");
  const [clase, setClase] = useState<"personaje" | "objeto">("personaje");
  const [creando, setCreando] = useState(false);
  // subir
  const [archivo, setArchivo] = useState<File | null>(null);
  const [nombreSubida, setNombreSubida] = useState("");
  const [fondoVerde, setFondoVerde] = useState(false);
  const [subiendo, setSubiendo] = useState(false);

  const cargar = useCallback(() => biblioteca.listar().then(setDatos).catch((e) => setError(String(e.message || e))), []);
  useEffect(() => { cargar(); }, [cargar]);

  // grupos que se ven con el nicho elegido (las propias siempre)
  const grupos = useMemo(() => {
    const todos = (datos?.grupos || []).filter((g) => (datos?.[tipo] || []).some((d) => d.grupo === g.id));
    const delNicho = nicho ? datos?.nichos[nicho] || [] : null;
    return delNicho ? todos.filter((g) => delNicho.includes(g.id) || g.id === "propias") : todos;
  }, [datos, tipo, nicho]);

  const lista = useMemo(() => {
    const q = buscar.trim().toLowerCase();
    const validos = new Set(grupos.map((g) => g.id));
    return (datos?.[tipo] || []).filter((d) => (grupo ? d.grupo === grupo : validos.has(d.grupo))
      && (!q || d.id.includes(q) || d.descripcion.toLowerCase().includes(q)));
  }, [datos, tipo, buscar, grupo, grupos]);

  const porPagina = POR_PAGINA[tipo];
  const paginas = Math.max(1, Math.ceil(lista.length / porPagina));
  const visibles = lista.slice(pagina * porPagina, (pagina + 1) * porPagina);
  // al cambiar de filtro se vuelve a la primera pagina
  useEffect(() => { setPagina(0); }, [tipo, buscar, nicho, grupo]);
  useEffect(() => { if (grupo && !grupos.some((g) => g.id === grupo)) setGrupo(""); }, [grupo, grupos]);

  async function crear() {
    setCreando(true);
    setError(null);
    try {
      await biblioteca.crear(tipo, descripcion, nombre, clase, familia);
      setDescripcion("");
      setNombre("");
      setVersion(Date.now());
      await cargar();
    } catch (e) { setError(String((e as Error).message || e)); }
    setCreando(false);
  }

  async function subir() {
    if (!archivo) return;
    setSubiendo(true);
    setError(null);
    try {
      await biblioteca.subir(tipo, archivo, nombreSubida || archivo.name.replace(/\.[^.]+$/, ""), "", fondoVerde);
      setArchivo(null);
      setNombreSubida("");
      setVersion(Date.now());
      await cargar();
    } catch (e) { setError(String((e as Error).message || e)); }
    setSubiendo(false);
  }

  async function borrar(id: string) {
    if (!confirm(`¿Borrar "${id}" de la biblioteca?`)) return;
    try {
      await biblioteca.borrar(tipo, id);
      await cargar();
    } catch (e) { setError(String((e as Error).message || e)); }
  }

  const pegatinas = tipo === "pegatinas";

  return (
    <main className="mx-auto max-w-6xl px-4 pb-24 pt-8">
      <div className="mb-6 flex flex-wrap items-center gap-3">
        <Link href="/fabrica" className="boton boton-fantasma !p-2"><ArrowLeft size={16} /></Link>
        <div>
          <h1 className="font-display text-2xl font-semibold">Biblioteca de dibujos</h1>
          <p className="text-sm text-tinta-3">Claude elige de aqui los personajes, objetos y escenas de cada video.</p>
        </div>
        <div className="ml-auto">
          <Segmentado valor={tipo} onChange={(v) => setTipo(v as TipoDibujo)}
            opciones={[{ v: "pegatinas", t: `Pegatinas (${datos?.pegatinas.length ?? 0})` }, { v: "ilustraciones", t: `Ilustraciones (${datos?.ilustraciones.length ?? 0})` }]} />
        </div>
      </div>
      <AvisoError texto={error} />

      <div className="mb-6 grid gap-4 md:grid-cols-2">
        <div className="rounded-2xl border border-linea bg-tarjeta p-4">
          <p className="etiqueta mb-3 flex items-center gap-2"><Sparkles size={14} /> Crear con Nano Banana</p>
          {datos && !datos.crear ? (
            <p className="text-sm text-tinta-3">Crear dibujos solo funciona en el PC con Flow conectado. Aqui puedes subir una imagen.</p>
          ) : (
            <>
              <Campo etiqueta={pegatinas ? "Que personaje u objeto" : "Que escena"}>
                <textarea className="campo min-h-16 text-sm" value={descripcion} onChange={(e) => setDescripcion(e.target.value)} disabled={creando}
                  placeholder={pegatinas ? "un rey azteca con penacho de plumas" : "un rey azteca recibiendo a los conquistadores en su palacio"} />
              </Campo>
              <div className="mt-3 flex flex-wrap items-end gap-3">
                <Campo etiqueta="Nombre (opcional)" className="min-w-40 flex-1">
                  <input className="campo" value={nombre} onChange={(e) => setNombre(e.target.value)} placeholder="rey_azteca" disabled={creando} />
                </Campo>
                {pegatinas && (
                  <Segmentado valor={clase} onChange={(v) => setClase(v as "personaje" | "objeto")}
                    opciones={[{ v: "personaje", t: "Personaje" }, { v: "objeto", t: "Objeto" }]} />
                )}
                <button className="boton boton-acento" disabled={creando || !descripcion.trim()} onClick={crear}>
                  {creando ? <Loader2 size={14} className="animate-spin" /> : <Sparkles size={14} />} {creando ? "Dibujando… (~1 min)" : "Crear"}
                </button>
              </div>
              <p className="mt-2 text-xs text-tinta-3">Sale en el estilo de dibujo elegido arriba (madera, plano o grabado). Las pegatinas salen ya recortadas.</p>
            </>
          )}
        </div>
        <div className="rounded-2xl border border-linea bg-tarjeta p-4">
          <p className="etiqueta mb-3 flex items-center gap-2"><Upload size={14} /> Subir una imagen</p>
          <label className="flex cursor-pointer items-center gap-2 rounded-xl border border-dashed border-linea p-3 text-sm text-tinta-2 hover:border-tinta-3">
            <ImagePlus size={16} /> {archivo ? archivo.name : pegatinas ? "PNG o WebP con fondo transparente (o sobre verde)" : "Imagen vertical (9:16)"}
            <input type="file" accept="image/*" className="hidden" onChange={(e) => setArchivo(e.target.files?.[0] || null)} />
          </label>
          <div className="mt-3 flex flex-wrap items-end gap-3">
            <Campo etiqueta="Nombre" className="min-w-40 flex-1">
              <input className="campo" value={nombreSubida} onChange={(e) => setNombreSubida(e.target.value)} placeholder="mi_personaje" />
            </Campo>
            {pegatinas && (
              <label className="mb-2 flex items-center gap-2 text-sm text-tinta-2">
                <input type="checkbox" checked={fondoVerde} onChange={(e) => setFondoVerde(e.target.checked)} /> Quitar fondo verde
              </label>
            )}
            <button className="boton boton-linea" disabled={!archivo || subiendo} onClick={subir}>
              {subiendo ? <Loader2 size={14} className="animate-spin" /> : <Upload size={14} />} Subir
            </button>
          </div>
        </div>
      </div>

      <div className="mb-3 flex flex-wrap items-center gap-3">
        <div className="flex min-w-56 flex-1 items-center gap-2">
          <Search size={15} className="text-tinta-3" />
          <input className="campo max-w-sm" value={buscar} onChange={(e) => setBuscar(e.target.value)} placeholder="Buscar (rey, barco, batalla…)" />
        </div>
        <select className="campo !w-auto" value={nicho} onChange={(e) => setNicho(e.target.value)} title="Ver lo que mas se usa en un nicho">
          <option value="">Todos los nichos</option>
          {Object.keys(datos?.nichos || {}).map((n) => <option key={n} value={n}>{NICHOS[n] || n}</option>)}
        </select>
        <Segmentado valor={familia} onChange={setFamilia}
          opciones={(datos?.familias || ["madera"]).map((f) => ({ v: f, t: FAMILIAS[f] || f }))} />
      </div>
      <div className="mb-4 flex flex-wrap gap-1.5">
        {[{ id: "", nombre: "Todo" }, ...grupos].map((g) => (
          <button key={g.id || "todo"} onClick={() => setGrupo(g.id)}
            className={`rounded-full border px-3 py-1 text-xs font-medium transition ${grupo === g.id ? "border-marca bg-marca text-white" : "border-linea bg-tarjeta text-tinta-2 hover:border-tinta-3"}`}>
            {g.nombre}
            {g.id && <span className="ml-1 opacity-60">{(datos?.[tipo] || []).filter((d) => d.grupo === g.id).length}</span>}
          </button>
        ))}
      </div>

      {!datos ? <Loader2 className="animate-spin text-tinta-3" /> : lista.length === 0 ? (
        <p className="rounded-2xl border border-dashed border-linea p-10 text-center text-tinta-3">No hay dibujos{buscar ? " con esa busqueda" : " todavia"}.</p>
      ) : (
        <ul className={`grid gap-3 ${pegatinas ? "grid-cols-3 sm:grid-cols-5 lg:grid-cols-7" : "grid-cols-2 sm:grid-cols-4 lg:grid-cols-6"}`}>
          {visibles.map((d) => (
            <li key={d.id} className="group relative overflow-hidden rounded-xl border border-linea bg-tarjeta">
              <div className={pegatinas ? "flex aspect-square items-center justify-center bg-gradient-to-b from-[#7fa8c9] to-[#3f6f9f] p-2" : "aspect-[9/16] bg-black"}>
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img src={biblioteca.urlImagen(tipo, d.id, version, familia)} alt={d.descripcion} loading="lazy"
                  className={pegatinas ? "max-h-full max-w-full object-contain drop-shadow-md" : "h-full w-full object-cover"} />
              </div>
              <div className="p-2">
                <p className="truncate text-xs font-semibold" title={d.id}>{d.id}</p>
                <p className="truncate text-[11px] text-tinta-3" title={d.descripcion}>{d.descripcion}</p>
              </div>
              {d.origen === "propia" && (
                <>
                  <span className="absolute left-1.5 top-1.5 rounded-full bg-marca px-1.5 py-0.5 text-[10px] font-semibold text-white">propia</span>
                  <button className="boton boton-fantasma absolute right-1 top-1 !bg-tarjeta/80 !p-1 opacity-0 group-hover:opacity-100"
                    title="Borrar" onClick={() => borrar(d.id)}><Trash2 size={13} /></button>
                </>
              )}
            </li>
          ))}
        </ul>
      )}
      {paginas > 1 && (
        <div className="mt-5 flex items-center justify-center gap-2 text-sm">
          <button className="boton boton-fantasma !p-2" disabled={pagina === 0} onClick={() => setPagina(pagina - 1)} title="Anterior"><ChevronLeft size={16} /></button>
          {Array.from({ length: paginas }, (_, i) => (
            <button key={i} onClick={() => setPagina(i)}
              className={`h-8 min-w-8 rounded-lg px-2 ${i === pagina ? "bg-marca font-semibold text-white" : "text-tinta-2 hover:bg-tarjeta"}`}>{i + 1}</button>
          ))}
          <button className="boton boton-fantasma !p-2" disabled={pagina >= paginas - 1} onClick={() => setPagina(pagina + 1)} title="Siguiente"><ChevronRight size={16} /></button>
          <span className="ml-2 text-tinta-3">{lista.length} dibujos</span>
        </div>
      )}
    </main>
  );
}
