"use client";

// Ideas virales: se pegan cuentas que hacen videos como los nuestros (YouTube Shorts o TikTok) y salen sus videos
// que hicieron 3 veces o mas las vistas normales de esa cuenta (el tema ya demostro que gusta). De cada uno se
// puede ver su gancho de los 3 primeros segundos, likes y comentarios por cada mil vistas y los comentarios mas
// votados. Los elegidos se convierten (Claude) en temas PROPIOS que van al banco de temas de la Fabrica.

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ArrowLeft, CopyPlus, ExternalLink, Lightbulb, Loader2, Search, Sparkles } from "lucide-react";
import { AvisoError, Campo } from "@/components/ui";
import {
  clones, fabrica, virales, type AnalisisViral, type CatalogoFabrica, type DetalleViral, type IdeaFabrica, type VideoViral,
} from "@/lib/api";

const mil = (n: number | null | undefined) =>
  n == null ? "—" : n >= 1e6 ? `${(n / 1e6).toFixed(n >= 1e7 ? 0 : 1)} M` : n >= 1e3 ? `${Math.round(n / 1e3)} k` : String(n);

export default function PaginaIdeas() {
  const router = useRouter();
  const [cat, setCat] = useState<CatalogoFabrica | null>(null);
  const [cuentas, setCuentas] = useState("");
  const [a, setA] = useState<AnalisisViral | null>(null);
  const [analizando, setAnalizando] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [elegidos, setElegidos] = useState<Set<string>>(new Set());
  const [detalles, setDetalles] = useState<Record<string, DetalleViral | "cargando">>({});
  const [nicho, setNicho] = useState("mapas");
  const [serie, setSerie] = useState("");
  const [convirtiendo, setConvirtiendo] = useState(false);
  const [nuevas, setNuevas] = useState<IdeaFabrica[] | null>(null);

  useEffect(() => {
    fabrica.catalogo().then(setCat).catch(() => {});
    setCuentas(localStorage.getItem("virales-cuentas") || "");
    virales.ultimo().then((r) => setA(r.analisis)).catch(() => {});
  }, []);

  async function analizar() {
    const lista = cuentas.split(/[\n,]/).map((x) => x.trim()).filter(Boolean);
    localStorage.setItem("virales-cuentas", cuentas);
    setAnalizando(true);
    setError(null);
    try {
      setA(await virales.analizar(lista));
      setElegidos(new Set());
    } catch (e) { setError(String((e as Error).message || e)); }
    setAnalizando(false);
  }

  async function verDetalle(v: VideoViral) {
    setDetalles((d) => ({ ...d, [v.id]: "cargando" }));
    try {
      const x = await virales.detalle(v.url);
      setDetalles((d) => ({ ...d, [v.id]: x }));
    } catch (e) {
      setDetalles((d) => { const c = { ...d }; delete c[v.id]; return c; });
      setError(String((e as Error).message || e));
    }
  }

  const alternar = (id: string) => setElegidos((s) => { const n = new Set(s); if (n.has(id)) n.delete(id); else n.add(id); return n; });

  async function convertir() {
    if (!a) return;
    setConvirtiendo(true);
    setError(null);
    try {
      const videos = a.videos.filter((v) => elegidos.has(v.id)).map((v) => {
        const d = detalles[v.id];
        return d && d !== "cargando" ? { ...v, gancho: d.gancho, top: d.top } : v;
      });
      const antes = new Set((await fabrica.ideas(nicho)).ideas.map((i) => i.tema));
      const r = await virales.aTemas(videos, nicho, serie);
      setNuevas(r.ideas.filter((i) => !antes.has(i.tema)));
    } catch (e) { setError(String((e as Error).message || e)); }
    setConvirtiendo(false);
  }

  return (
    <main className="mx-auto max-w-6xl px-4 pb-24 pt-8">
      <div className="mb-6 flex flex-wrap items-center gap-3">
        <Link href="/fabrica" className="boton boton-fantasma !p-2"><ArrowLeft size={16} /></Link>
        <div>
          <h1 className="font-display text-2xl font-semibold">Ideas virales</h1>
          <p className="text-sm text-tinta-3">Los videos que funcionaron mucho mejor de lo normal en otras cuentas, convertidos en temas tuyos.</p>
        </div>
      </div>
      <AvisoError texto={error} />

      <div className="mb-6 grid gap-5 md:grid-cols-[1fr_1fr]">
        <div className="rounded-2xl border border-linea bg-tarjeta p-5">
          <Campo etiqueta="Cuentas a mirar (una por linea)">
            <textarea className="campo min-h-28 text-sm" value={cuentas} onChange={(e) => setCuentas(e.target.value)}
              placeholder={"@cuentadeyoutube\nhttps://www.youtube.com/@otra\nhttps://www.tiktok.com/@cuenta"} />
          </Campo>
          <button className="boton boton-acento mt-3 w-full justify-center" disabled={analizando || !cuentas.trim()} onClick={analizar}>
            {analizando ? <Loader2 size={15} className="animate-spin" /> : <Search size={15} />}
            {analizando ? "Mirando sus ultimos videos…" : "Buscar outliers"}
          </button>
          <p className="mt-2 text-xs text-tinta-3">
            YouTube Shorts y TikTok (Instagram no lo permite sin cuenta). De cada cuenta se miran sus ultimos 60 videos cortos (sin descargar nada). Outlier = 3 veces o mas su mediana de vistas y mas de 10.000.
          </p>
        </div>
        <div className="rounded-2xl border border-linea bg-tarjeta p-5">
          <p className="etiqueta mb-2">Convertir en temas propios</p>
          <div className="grid gap-3 sm:grid-cols-2">
            <Campo etiqueta="Nicho">
              <select className="campo" value={nicho} onChange={(e) => setNicho(e.target.value)}>
                {cat?.nichos.map((n) => <option key={n.id} value={n.id}>{n.nombre}</option>)}
              </select>
            </Campo>
            <Campo etiqueta="Serie">
              <select className="campo" value={serie} onChange={(e) => setSerie(e.target.value)}>
                <option value="">Ninguna</option>
                {cat?.series?.map((s) => <option key={s.id} value={s.id}>{s.nombre}</option>)}
              </select>
            </Campo>
          </div>
          <button className="boton boton-acento mt-3 w-full justify-center" disabled={convirtiendo || !elegidos.size} onClick={convertir}>
            {convirtiendo ? <Loader2 size={15} className="animate-spin" /> : <Sparkles size={15} />}
            {convirtiendo ? "Claude esta pensando…" : `Sacar temas de ${elegidos.size} video${elegidos.size === 1 ? "" : "s"}`}
          </button>
          <p className="mt-2 text-xs text-tinta-3">
            Claude ve por que funciono cada uno (y su gancho y comentarios si abriste el detalle) y propone un tema tuyo con
            otro asunto u otro angulo; nunca copia. Van al banco de temas de la Fabrica.
          </p>
          {nuevas && (
            <div className="mt-3 rounded-xl bg-hundido p-3 text-sm">
              <p className="mb-1.5 font-semibold">{nuevas.length ? `${nuevas.length} temas nuevos en el banco` : "No salio ningun tema nuevo (ya estaban)"}</p>
              <ul className="space-y-1 text-xs text-tinta-2">
                {nuevas.map((i) => <li key={i.tema}>• {i.tema}</li>)}
              </ul>
              {nuevas.length > 0 && <Link href="/fabrica" className="boton boton-linea mt-2 !py-1 text-xs"><Lightbulb size={13} /> Ir a la Fabrica</Link>}
            </div>
          )}
        </div>
      </div>

      {a && (
        <>
          <div className="mb-3 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-tinta-3">
            {a.cuentas.map((c) => (
              <span key={c.url}><b className="text-tinta-2">{c.nombre}</b> · mediana {mil(c.mediana)} · {c.n} videos{c.seguidores ? ` · ${mil(c.seguidores)} seguidores` : ""}</span>
            ))}
            <span>Analizado {new Date(a.fecha * 1000).toLocaleString()}</span>
          </div>
          {a.errores.map((e) => <p key={e} className="mb-2 text-xs text-error">{e}</p>)}
          {a.videos.length === 0 ? (
            <p className="rounded-2xl border border-dashed border-linea p-8 text-center text-sm text-tinta-3">
              Ningun video supera 3 veces la mediana de su cuenta. Prueba con otras cuentas.
            </p>
          ) : (
            <ul className="grid gap-3 md:grid-cols-2">
              {a.videos.map((v) => {
                const d = detalles[v.id];
                return (
                  <li key={v.id} className={`rounded-2xl border bg-tarjeta p-4 ${elegidos.has(v.id) ? "border-marca ring-1 ring-marca" : "border-linea"}`}>
                    <div className="flex items-start gap-3">
                      <input type="checkbox" className="mt-1" checked={elegidos.has(v.id)} onChange={() => alternar(v.id)} />
                      <div className="min-w-0 flex-1">
                        <p className="font-semibold leading-snug">{v.titulo}</p>
                        <p className="mt-1 text-xs text-tinta-3">
                          <span className="rounded bg-acento px-1.5 py-0.5 font-semibold text-sobre-acento">{v.veces}x</span>
                          {" "}{mil(v.vistas)} vistas · {v.cuenta}
                        </p>
                      </div>
                      <button className="boton boton-fantasma !px-2 !py-1.5 text-xs" title="Sacar su receta para hacer tu version"
                        onClick={() => clones.crear(v.url).then((c) => router.push(`/fabrica/clonar?c=${c.id}`)).catch((e) => setError(String(e.message || e)))}>
                        <CopyPlus size={14} /> Clonar
                      </button>
                      <a href={v.url} target="_blank" rel="noreferrer" className="boton boton-fantasma !p-1.5" title="Abrir el video"><ExternalLink size={14} /></a>
                    </div>
                    {!d ? (
                      <button className="mt-2 text-xs text-tinta-2 underline" onClick={() => verDetalle(v)}>Ver gancho, likes y comentarios</button>
                    ) : d === "cargando" ? (
                      <p className="mt-2 flex items-center gap-2 text-xs text-tinta-3"><Loader2 size={13} className="animate-spin" /> Leyendo el video…</p>
                    ) : (
                      <div className="mt-2 space-y-1.5 rounded-xl bg-hundido p-3 text-xs text-tinta-2">
                        {d.gancho && <p><b>Primeros 3 s:</b> «{d.gancho}»</p>}
                        <p>
                          <b>Likes:</b> {mil(d.likes)} ({d.likes_mil ?? "—"} por mil) · <b>Comentarios:</b> {mil(d.comentarios)} ({d.comentarios_mil ?? "—"} por mil)
                        </p>
                        {d.top.length > 0 && (
                          <ul className="space-y-0.5">
                            {d.top.slice(0, 4).map((c, k) => <li key={k}>💬 {c.texto} <span className="text-tinta-3">({mil(c.likes)})</span></li>)}
                          </ul>
                        )}
                      </div>
                    )}
                  </li>
                );
              })}
            </ul>
          )}
        </>
      )}
    </main>
  );
}
