"use client";

// Clonar video: se pega el enlace de un video que funciona (o se sube) y sale su receta: gancho, bloques de la
// estructura, tipo de cada plano y ritmo. Con la receta, la Fabrica hace un video NUEVO (otro tema, formato o
// estilo) con la misma estructura. Los planos que en el original son video (presentador, B-roll) se hacen con fotos
// de Nano Banana; si se marca "prompts de video", Claude escribe ademas el prompt de cada uno para hacerlo aparte
// (Seedance, Veo...) y subirlo luego en el video.

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ArrowLeft, Copy as Clonar, Link2, Loader2, Sparkles, Trash2, Upload } from "lucide-react";
import { AvisoError, Campo, Segmentado } from "@/components/ui";
import {
  clones, fabrica, mmss, type CatalogoFabrica, type DetalleClon, type FormatoFabrica, type SesionClon,
} from "@/lib/api";
import { AZURE_VOICES } from "@/lib/voces";
import GaleriaEstilos from "@/components/GaleriaEstilos";

const TRABAJANDO = ["en cola", "descargando", "analizando"];

export default function PaginaClonar() {
  const router = useRouter();
  const [lista, setLista] = useState<SesionClon[] | null>(null);
  const [elegido, setElegido] = useState<string | null>(null);
  const [d, setD] = useState<DetalleClon | null>(null);
  const [url, setUrl] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const cargar = useCallback(() => clones.listar().then((r) => setLista(r.clones)).catch((e) => setError(String(e.message || e))), []);
  useEffect(() => {
    cargar();
    const c = new URLSearchParams(window.location.search).get("c");
    if (c) setElegido(c);
  }, [cargar]);
  useEffect(() => {
    if (!elegido) { setD(null); return; }
    let vivo = true;
    let k: ReturnType<typeof setTimeout>;
    const ver = () => clones.ver(elegido).then((x) => {
      if (!vivo) return;
      setD(x);
      if (TRABAJANDO.includes(x.estado)) k = setTimeout(ver, 2500);
      else cargar();
    }).catch((e) => setError(String(e.message || e)));
    ver();
    return () => { vivo = false; clearTimeout(k); };
  }, [elegido, cargar]);

  async function empezar(fn: () => Promise<SesionClon>) {
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

  return (
    <main className="mx-auto max-w-6xl px-4 pb-24 pt-8">
      <div className="mb-6 flex flex-wrap items-center gap-3">
        <Link href="/fabrica" className="boton boton-fantasma !p-2"><ArrowLeft size={16} /></Link>
        <div>
          <h1 className="font-display text-2xl font-semibold">Clonar video</h1>
          <p className="text-sm text-tinta-3">La receta de un video que funciona (gancho, estructura y ritmo) para hacer uno tuyo con otro tema.</p>
        </div>
      </div>
      <AvisoError texto={error} />

      <div className="grid gap-5 lg:grid-cols-[300px_1fr]">
        <aside className="space-y-4">
          <div className="rounded-2xl border border-linea bg-tarjeta p-4">
            <Campo etiqueta="Enlace del video (YouTube, TikTok…)">
              <input className="campo" value={url} onChange={(e) => setUrl(e.target.value)} placeholder="https://www.tiktok.com/@…/video/…" />
            </Campo>
            <button className="boton boton-acento mt-2 w-full justify-center" disabled={enviando || !url.trim()} onClick={() => empezar(() => clones.crear(url))}>
              {enviando ? <Loader2 size={15} className="animate-spin" /> : <Link2 size={15} />} Sacar la receta
            </button>
            <label className="mt-2 flex cursor-pointer items-center justify-center gap-2 rounded-xl border border-dashed border-linea p-2.5 text-xs text-tinta-2 hover:border-tinta-3">
              <Upload size={14} /> o sube el video (hasta 5 min)
              <input type="file" accept="video/*" hidden disabled={enviando}
                onChange={(e) => { const f = e.target.files?.[0]; if (f) empezar(() => clones.subir(f)); }} />
            </label>
          </div>
          <ul className="space-y-2">
            {lista?.map((c) => (
              <li key={c.id}>
                <button onClick={() => setElegido(c.id)}
                  className={`w-full rounded-xl border p-3 text-left text-sm transition ${elegido === c.id ? "border-marca bg-tarjeta ring-1 ring-marca" : "border-linea hover:border-tinta-3"}`}>
                  <p className="line-clamp-2 font-semibold">{c.titulo}</p>
                  <p className="mt-0.5 text-xs text-tinta-3">
                    {TRABAJANDO.includes(c.estado) ? `${c.mensaje} (${c.progreso}%)` : c.estado === "error" ? "error" : `${c.formato || ""} · ${mmss(c.duracion || 0)}`}
                  </p>
                </button>
              </li>
            ))}
            {lista && !lista.length && <p className="text-center text-xs text-tinta-3">Todavia no has clonado ningun video.</p>}
          </ul>
        </aside>

        <section>
          {!d ? (
            <p className="rounded-2xl border border-dashed border-linea p-10 text-center text-sm text-tinta-3">
              Pega un enlace o elige un clon de la lista. Tambien puedes darle a «Clonar» en Ideas virales.
            </p>
          ) : TRABAJANDO.includes(d.estado) ? (
            <div className="rounded-2xl border border-linea bg-tarjeta p-5">
              <p className="flex items-center gap-2 text-sm"><Loader2 size={15} className="animate-spin" /> {d.mensaje}</p>
              <div className="mt-3 h-2 overflow-hidden rounded-full bg-hundido"><div className="h-full bg-marca transition-all" style={{ width: `${d.progreso}%` }} /></div>
            </div>
          ) : d.estado === "error" ? (
            <div className="rounded-2xl border border-linea bg-tarjeta p-5">
              <AvisoError texto={d.error} />
              <button className="boton boton-linea mt-3" onClick={() => clones.borrar(d.id).then(() => { setElegido(null); cargar(); })}><Trash2 size={14} /> Borrar</button>
            </div>
          ) : d.receta && (
            <Receta d={d} onBorrar={() => clones.borrar(d.id).then(() => { setElegido(null); cargar(); })}
              onReplicar={async (opciones) => {
                setError(null);
                try { router.push(`/fabrica/${(await fabrica.crear(opciones)).id}`); } catch (e) { setError(String((e as Error).message || e)); }
              }} />
          )}
        </section>
      </div>
    </main>
  );
}

function Receta({ d, onBorrar, onReplicar }: {
  d: DetalleClon; onBorrar: () => void; onReplicar: (o: Parameters<typeof fabrica.crear>[0]) => Promise<void>;
}) {
  const r = d.receta!;
  const [cat, setCat] = useState<CatalogoFabrica | null>(null);
  const [tema, setTema] = useState("");
  const [nicho, setNicho] = useState(r.nicho_sugerido || "curiosidades");
  const [estilo, setEstilo] = useState("oscuro");
  const [visual, setVisual] = useState("");
  const [formato, setFormato] = useState<FormatoFabrica>(r.formato || "9:16");
  const [duracion, setDuracion] = useState(String(Math.max(20, Math.round(r.duracion / 5) * 5)));
  const [voz, setVoz] = useState("es-ES-AlvaroNeural-Male");
  const [clips, setClips] = useState(false);
  const [enviando, setEnviando] = useState(false);
  useEffect(() => { fabrica.catalogo().then(setCat).catch(() => {}); }, []);
  const voces = AZURE_VOICES.filter((v) => v.lang.startsWith("es"));

  return (
    <div className="space-y-5">
      <div className="rounded-2xl border border-linea bg-tarjeta p-5">
        <div className="flex items-start justify-between gap-3">
          <div>
            <h2 className="font-display text-xl font-semibold">{r.titulo}</h2>
            <p className="mt-1 text-sm text-tinta-2">{r.resumen}</p>
            <p className="mt-1 text-xs text-tinta-3">
              {r.formato} · {mmss(r.duracion)} · {r.ritmo.planos} planos (uno cada {r.ritmo.plano_medio_s} s) · {r.palabras_por_segundo} palabras/s
              {d.origen.startsWith("http") && <> · <a href={d.origen} target="_blank" rel="noreferrer" className="underline">original</a></>}
            </p>
          </div>
          <button className="boton boton-fantasma !p-2" title="Borrar" onClick={() => confirm("¿Borrar esta receta?") && onBorrar()}><Trash2 size={15} /></button>
        </div>
        <div className="mt-4 grid gap-4 md:grid-cols-2">
          <div className="rounded-xl bg-hundido p-3 text-sm">
            <p className="etiqueta mb-1">Gancho ({r.gancho?.tipo})</p>
            <p>«{r.gancho?.texto}»</p>
            <p className="mt-1 text-xs text-tinta-3">Se ve: {r.gancho?.visual}</p>
            <p className="mt-1 text-xs text-tinta-2">Patron: {r.gancho?.patron}</p>
          </div>
          <div className="rounded-xl bg-hundido p-3 text-sm">
            <p className="etiqueta mb-1">Por que funciona</p>
            <ul className="space-y-0.5 text-xs text-tinta-2">{(r.por_que_funciona || []).map((x) => <li key={x}>• {x}</li>)}</ul>
          </div>
        </div>
        <p className="etiqueta mb-1.5 mt-4">Estructura</p>
        <ol className="space-y-1 text-xs">
          {(r.estructura || []).map((b, k) => (
            <li key={k} className="flex gap-2">
              <span className="w-24 shrink-0 font-semibold text-tinta-2">{b.bloque} <span className="font-normal text-tinta-3">{b.desde}-{b.hasta}s</span></span>
              <span className="text-tinta-2">{b.que_pasa} <span className="text-tinta-3">— {b.patron}</span></span>
            </li>
          ))}
        </ol>
        <p className="etiqueta mb-1.5 mt-4">Planos</p>
        <div className="flex gap-1.5 overflow-x-auto pb-1">
          {d.planos.filter((p) => p.foto).map((p) => (
            <figure key={p.n} className="w-20 shrink-0" title={`${p.describe || ""}\n«${p.texto}»`}>
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src={clones.urlFoto(d.id, p.foto!)} alt="" className="w-full rounded-md" loading="lazy" />
              <figcaption className="mt-0.5 truncate text-[10px] text-tinta-3">{p.tipo} · {p.desde.toFixed(1)}s</figcaption>
            </figure>
          ))}
        </div>
        {(r.efectos?.length || r.subtitulos) && (
          <p className="mt-3 text-xs text-tinta-3">Efectos: {(r.efectos || []).join(", ")} · Subtitulos: {r.subtitulos} · Musica: {r.musica}</p>
        )}
      </div>

      <div className="rounded-2xl border border-linea bg-tarjeta p-5">
        <p className="etiqueta mb-2 flex items-center gap-1.5"><Clonar size={13} /> Hacer mi version</p>
        <Campo etiqueta="Tema nuevo">
          <textarea className="campo min-h-16" value={tema} onChange={(e) => setTema(e.target.value)} placeholder="De que va tu video" />
        </Campo>
        {(r.temas_parecidos || []).length > 0 && (
          <div className="mt-1.5 flex flex-wrap gap-1.5">
            {r.temas_parecidos.map((t) => (
              <button key={t} type="button" onClick={() => setTema(t)} className="rounded-full border border-linea px-2.5 py-1 text-xs text-tinta-2 hover:border-tinta-3">{t}</button>
            ))}
          </div>
        )}
        <div className="mt-4 grid gap-4 sm:grid-cols-3">
          <Campo etiqueta="Nicho">
            <select className="campo" value={nicho} onChange={(e) => setNicho(e.target.value)}>
              {cat?.nichos.map((n) => <option key={n.id} value={n.id}>{n.nombre}</option>)}
            </select>
          </Campo>
          <Campo etiqueta="Imagenes">
            <select className="campo" value={visual} onChange={(e) => setVisual(e.target.value)}>
              <option value="">Las del estilo</option>
              {cat?.visuales?.map((x) => <option key={x.id} value={x.id}>{x.nombre}</option>)}
            </select>
          </Campo>
          <Campo etiqueta="Voz">
            <select className="campo" value={voz} onChange={(e) => setVoz(e.target.value)}>
              {voces.map((v) => <option key={v.value} value={v.value}>{v.label}</option>)}
            </select>
          </Campo>
        </div>
        <div className="mt-4"><p className="etiqueta mb-1.5">Estilo</p><GaleriaEstilos valor={estilo} onCambio={setEstilo} compacta /></div>
        <div className="mt-4 flex flex-wrap items-end gap-5">
          <Campo etiqueta="Formato">
            <Segmentado valor={formato} onChange={setFormato} opciones={(["9:16", "16:9", "1:1"] as FormatoFabrica[]).map((f) => ({ v: f, t: f }))} />
          </Campo>
          <Campo etiqueta="Duracion (s)">
            <input className="campo w-24" type="number" min={20} max={600} value={duracion} onChange={(e) => setDuracion(e.target.value)} />
          </Campo>
        </div>
        <label className="mt-4 flex items-start gap-2 text-sm text-tinta-2">
          <input type="checkbox" className="mt-1" checked={clips} onChange={(e) => setClips(e.target.checked)} />
          <span>
            Prompts de video para hacer los clips aparte (Seedance, Veo/Gemini…)
            <span className="block text-xs text-tinta-3">
              El video sale igual con fotos (sin gasto). Ademas, en cada escena tendras su prompt de video para generarlo donde
              quieras y subirlo. El video se para antes de montar para que subas los clips (el clip sustituye a la foto).
            </span>
          </span>
        </label>
        <button className="boton boton-acento mt-4 w-full justify-center" disabled={enviando || !tema.trim()}
          onClick={async () => {
            setEnviando(true);
            await onReplicar({ tema, nicho, estilo, visual, formatos: [formato], duracion: Number(duracion), voz, receta: d.id, clips,
              musica: "random", subtitulos: true, efectos: true, foco: true, nuevos: true, idioma: "espanol" });
            setEnviando(false);
          }}>
          {enviando ? <Loader2 size={15} className="animate-spin" /> : <Sparkles size={15} />} Hacer mi version con esta receta
        </button>
      </div>
    </div>
  );
}
