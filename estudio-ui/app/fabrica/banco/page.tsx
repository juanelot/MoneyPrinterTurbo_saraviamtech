"use client";

// Banco de clips: se pega el enlace de un video largo (MrBeast, una pelicula, una serie...) o se sube, se corta en
// planos de ~3 s sin audio y Claude describe cada uno. En el formulario de la Fabrica se eligen los videos del banco
// y Claude pone sus clips detras de las escenas donde pegan con la frase.

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { ArrowLeft, Ban, Check, Link2, Loader2, Trash2, Upload } from "lucide-react";
import { AvisoError, Campo, Segmentado } from "@/components/ui";
import { banco, mmss, type DetalleBanco, type SesionBanco } from "@/lib/api";

const TRABAJANDO = ["en cola", "descargando", "cortando"];

export default function PaginaBanco() {
  const [lista, setLista] = useState<SesionBanco[] | null>(null);
  const [elegido, setElegido] = useState<string | null>(null);
  const [d, setD] = useState<DetalleBanco | null>(null);
  const [url, setUrl] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [filtro, setFiltro] = useState<"todos" | "si" | "no">("todos");

  const cargar = useCallback(() => banco.listar().then((r) => setLista(r.videos)).catch((e) => setError(String(e.message || e))), []);
  useEffect(() => { cargar(); }, [cargar]);
  useEffect(() => {
    if (!elegido) { setD(null); return; }
    let vivo = true;
    let k: ReturnType<typeof setTimeout>;
    const ver = () => banco.ver(elegido).then((x) => {
      if (!vivo) return;
      setD(x);
      if (TRABAJANDO.includes(x.estado)) k = setTimeout(ver, 2500);
      else cargar();
    }).catch((e) => setError(String(e.message || e)));
    ver();
    return () => { vivo = false; clearTimeout(k); };
  }, [elegido, cargar]);

  async function empezar(fn: () => Promise<SesionBanco>) {
    setEnviando(true);
    setError(null);
    try {
      const s = await fn();
      setUrl("");
      await cargar();
      setElegido(s.id);
    } catch (e) { setError(String((e as Error).message || e)); }
    setEnviando(false);
  }

  const borrar = () => d && confirm("¿Borrar este video y todos sus clips?")
    && banco.borrar(d.id).then(() => { setElegido(null); cargar(); }).catch((e) => setError(String(e.message || e)));
  const utiles = d?.clips.filter((c) => c.sirve).length ?? 0;

  return (
    <main className="mx-auto max-w-6xl px-4 pb-24 pt-8">
      <div className="mb-6 flex flex-wrap items-center gap-3">
        <Link href="/fabrica" className="boton boton-fantasma !p-2"><ArrowLeft size={16} /></Link>
        <div>
          <h1 className="font-display text-2xl font-semibold">Banco de clips</h1>
          <p className="text-sm text-tinta-3">Videos largos cortados en planos de ~3 s. En la Fabrica eliges cuales usar y Claude pone cada clip donde pega con la frase.</p>
        </div>
      </div>
      <AvisoError texto={error} />

      <div className="grid gap-5 lg:grid-cols-[300px_1fr]">
        <aside className="space-y-4">
          <div className="rounded-2xl border border-linea bg-tarjeta p-4">
            <Campo etiqueta="Enlace del video (YouTube…)">
              <input className="campo" value={url} onChange={(e) => setUrl(e.target.value)} placeholder="https://www.youtube.com/watch?v=…" />
            </Campo>
            <button className="boton boton-acento mt-2 w-full justify-center" disabled={enviando || !url.trim()} onClick={() => empezar(() => banco.crear(url))}>
              {enviando ? <Loader2 size={15} className="animate-spin" /> : <Link2 size={15} />} Cortar en clips
            </button>
            <label className="mt-2 flex cursor-pointer items-center justify-center gap-2 rounded-xl border border-dashed border-linea p-2.5 text-xs text-tinta-2 hover:border-tinta-3">
              <Upload size={14} /> o sube el video (pelicula, serie…)
              <input type="file" accept="video/*" hidden disabled={enviando}
                onChange={(e) => { const f = e.target.files?.[0]; if (f) empezar(() => banco.subir(f)); }} />
            </label>
            <p className="mt-2 text-[11px] leading-snug text-tinta-3">Sin audio original (encima va tu narracion) y recortado al formato del video. Ojo: el contenido de otros puede llevar reclamos de derechos.</p>
          </div>
          <ul className="space-y-2">
            {lista?.map((b) => (
              <li key={b.id}>
                <button onClick={() => setElegido(b.id)}
                  className={`w-full rounded-xl border p-3 text-left text-sm transition ${elegido === b.id ? "border-marca bg-tarjeta ring-1 ring-marca" : "border-linea hover:border-tinta-3"}`}>
                  <p className="line-clamp-2 font-semibold">{b.titulo}</p>
                  <p className="mt-0.5 text-xs text-tinta-3">
                    {TRABAJANDO.includes(b.estado) ? `${b.mensaje} (${b.progreso}%)` : b.estado === "error" ? "error" : `${b.n_clips} clips · ${mmss(b.duracion || 0)}`}
                  </p>
                </button>
              </li>
            ))}
            {lista && !lista.length && <p className="text-center text-xs text-tinta-3">Todavia no hay videos en el banco.</p>}
          </ul>
        </aside>

        <section>
          {!d ? (
            <p className="rounded-2xl border border-dashed border-linea p-10 text-center text-sm text-tinta-3">
              Pega el enlace de un video (por ejemplo uno largo de MrBeast) o elige uno de la lista.
            </p>
          ) : TRABAJANDO.includes(d.estado) ? (
            <div className="rounded-2xl border border-linea bg-tarjeta p-5">
              <p className="flex items-center gap-2 text-sm"><Loader2 size={15} className="animate-spin" /> {d.mensaje}</p>
              <div className="mt-3 h-2 overflow-hidden rounded-full bg-hundido"><div className="h-full bg-marca transition-all" style={{ width: `${d.progreso}%` }} /></div>
            </div>
          ) : d.estado === "error" ? (
            <div className="rounded-2xl border border-linea bg-tarjeta p-5">
              <AvisoError texto={d.error} />
              <button className="boton boton-linea mt-3" onClick={borrar}><Trash2 size={14} /> Borrar</button>
            </div>
          ) : (
            <div className="rounded-2xl border border-linea bg-tarjeta p-5">
              <div className="mb-4 flex items-start justify-between gap-3">
                <div>
                  <h2 className="font-display text-xl font-semibold">{d.titulo}</h2>
                  <p className="mt-1 text-xs text-tinta-3">
                    {utiles} de {d.clips.length} clips sirven · {mmss(d.duracion || 0)}
                    {d.origen.startsWith("http") && <> · <a href={d.origen} target="_blank" rel="noreferrer" className="underline">original</a></>}
                    {" "}· pasa el raton para verlo; clic para marcar si sirve
                  </p>
                </div>
                <button className="boton boton-fantasma !p-2" title="Borrar" onClick={borrar}><Trash2 size={15} /></button>
              </div>
              <div className="mb-3 flex flex-wrap items-center gap-3">
                <Segmentado valor={filtro} onChange={setFiltro} opciones={[
                  { v: "todos", t: `Todos (${d.clips.length})` }, { v: "si", t: `Se usan (${utiles})` },
                  { v: "no", t: `No se usan (${d.clips.length - utiles})` }]} />
                <p className="text-xs text-tinta-3">Clic en el boton de cada clip para que Claude lo use o no.</p>
              </div>
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 md:grid-cols-4">
                {d.clips.filter((c) => filtro === "todos" || (filtro === "si") === c.sirve).map((c) => (
                  <figure key={c.n} title={(c.etiquetas || []).join(", ")}
                    className={`overflow-hidden rounded-lg border-2 ${c.sirve ? "border-emerald-500/70" : "border-red-500/60"}`}>
                    <video src={banco.urlClip(d.id, c.n)} poster={banco.urlFoto(d.id, c.n)} muted loop playsInline preload="none"
                      className={`aspect-video w-full bg-black object-cover ${c.sirve ? "" : "opacity-40 grayscale"}`}
                      onMouseEnter={(e) => e.currentTarget.play().catch(() => {})} onMouseLeave={(e) => e.currentTarget.pause()} />
                    <figcaption className="p-1.5 text-[11px] leading-snug text-tinta-2">
                      <span className="font-semibold text-tinta-3">{c.n}</span> {c.describe || "—"}
                      <button type="button"
                        onClick={() => banco.sirve(d.id, c.n).then((r) => setD({ ...d, clips: r.clips })).catch((e) => setError(String(e.message || e)))}
                        className={`mt-1.5 flex w-full items-center justify-center gap-1 rounded-md py-1 text-xs font-semibold ${c.sirve
                          ? "bg-emerald-500/15 text-emerald-600 hover:bg-emerald-500/25" : "bg-red-500/15 text-red-600 hover:bg-red-500/25"}`}>
                        {c.sirve ? <><Check size={13} /> Se usa</> : <><Ban size={13} /> No se usa</>}
                      </button>
                    </figcaption>
                  </figure>
                ))}
              </div>
            </div>
          )}
        </section>
      </div>
    </main>
  );
}
