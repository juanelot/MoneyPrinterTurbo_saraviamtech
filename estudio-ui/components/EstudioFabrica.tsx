"use client";

// Un video de la Fabrica: el progreso mientras se hace, los videos de cada formato, el guion por
// escenas (se puede corregir el texto y rehacer desde la voz) y rehacer con otro estilo o formatos
// (solo se vuelve a dibujar; las escenas que no cambian salen de la cache).

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ArrowLeft, Clapperboard, Download, Loader2, Mic, RefreshCw, Save, SquarePen, Trash2 } from "lucide-react";
import { AvisoError, Tarjeta } from "./ui";
import GaleriaEstilos from "./GaleriaEstilos";
import { fabrica, listarMusica, mmss, type CatalogoFabrica, type DetalleFabrica, type FormatoFabrica, type GuionFabrica } from "@/lib/api";

const TRABAJANDO = ["en cola", "guion", "voz", "render", "montaje"];
const NOMBRE_ESCENA: Record<string, string> = {
  portada: "Portada", mapa: "Mapa", cifra: "Cifra", ilustracion: "Ilustracion", barras: "Barras", lista: "Lista", versus: "Versus",
  linea_tiempo: "Linea de tiempo", protagonista: "Protagonista", captura: "Captura",
};

export default function EstudioFabrica({ id }: { id: string }) {
  const router = useRouter();
  const [d, setD] = useState<DetalleFabrica | null>(null);
  const [cat, setCat] = useState<CatalogoFabrica | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [guion, setGuion] = useState<GuionFabrica | null>(null);
  const [cambiado, setCambiado] = useState(false);
  const [estilo, setEstilo] = useState("");
  const [formatos, setFormatos] = useState<FormatoFabrica[]>([]);
  const [musica, setMusica] = useState<string | null>(null);
  const [visual, setVisual] = useState<string | null>(null);
  const [presentador, setPresentador] = useState<string | null>(null);
  const [clipsCambiados, setClipsCambiados] = useState(false);
  const [canciones, setCanciones] = useState<string[]>([]);
  // revision: tu grabacion leyendo el guion (subida con fabrica.subirAudio, se manda como "narrada:<archivo>")
  const [miVoz, setMiVoz] = useState<{ voz: string; duracion: number; nombre: string } | null>(null);
  const [subiendoVoz, setSubiendoVoz] = useState(false);
  const [copiadoGuion, setCopiadoGuion] = useState(false);

  const cargar = useCallback(() => fabrica.ver(id).then((x) => {
    setD(x);
    setGuion((g) => (cambiado && g ? g : x.guion));
    setEstilo((e) => e || x.opciones.estilo);
    setFormatos((f) => (f.length ? f : x.opciones.formatos));
    setMusica((m) => m ?? musicaDe(x.opciones.musica));
    setVisual((v) => v ?? (x.opciones.visual || ""));
    setPresentador((p) => p ?? (x.opciones.presentador || ""));
  }).catch((e) => setError(String(e.message || e))), [id, cambiado]);
  useEffect(() => { cargar(); fabrica.catalogo().then(setCat).catch(() => {}); }, [cargar]);
  useEffect(() => { listarMusica().then(setCanciones); }, []);
  const trabajando = !!d && TRABAJANDO.includes(d.estado);
  useEffect(() => {
    if (!trabajando) return;
    const k = setInterval(cargar, 2500);
    return () => clearInterval(k);
  }, [trabajando, cargar]);

  async function accion(fn: () => Promise<unknown>) {
    setError(null);
    try {
      await fn();
      setCambiado(false);
      await cargar();
    } catch (e) { setError(String((e as Error).message || e)); }
  }
  const alternar = (f: FormatoFabrica) =>
    setFormatos((x) => (x.includes(f) ? (x.length > 1 ? x.filter((y) => y !== f) : x) : [...x, f]));
  const cambiarTexto = (i: number, texto: string) => {
    if (!guion) return;
    setGuion({ ...guion, escenas: guion.escenas.map((e, k) => (k === i ? { ...e, texto } : e)) });
    setCambiado(true);
  };

  if (error && !d) return <main className="mx-auto max-w-6xl px-4 pt-10"><AvisoError texto={error} /></main>;
  if (!d) return <main className="mx-auto max-w-6xl px-4 pt-10"><Loader2 className="animate-spin text-tinta-3" /></main>;
  const version = Math.round(d.actualizado);
  const otrasOpciones = estilo !== d.opciones.estilo || formatos.join() !== d.opciones.formatos.join()
    || (musica ?? "random") !== musicaDe(d.opciones.musica) || (visual ?? "") !== (d.opciones.visual || "")
    || (presentador ?? "") !== (d.opciones.presentador || "") || clipsCambiados;
  // con una grabacion propia el texto de las escenas es lo que se oye: no se edita
  const grabada = d.opciones.voz.startsWith("propia:");

  return (
    <main className="mx-auto max-w-6xl px-4 pb-24 pt-8">
      <div className="mb-5 flex flex-wrap items-center gap-3">
        <Link href="/fabrica" className="boton boton-fantasma !p-2"><ArrowLeft size={16} /></Link>
        <h1 className="font-display text-2xl font-semibold">{d.titulo}</h1>
        <button className="boton boton-linea ml-auto !py-1.5 text-sm" title="Guardar las opciones de este video como molde para repetirlas"
          onClick={() => {
            const nombre = prompt("Nombre del molde (estilo, formato, duracion, voz, musica, efectos... de este video)", "");
            if (nombre?.trim()) accion(async () => { await fabrica.guardarMolde(nombre.trim(), { desde: id }); alert("Molde guardado: lo tienes en la Fabrica, arriba del formulario."); });
          }}>
          <Save size={14} /> Guardar como molde
        </button>
        <button className="boton boton-fantasma !p-2" title="Borrar" disabled={trabajando}
          onClick={() => confirm("¿Borrar este video y todo lo generado?") && accion(async () => { await fabrica.borrar(id); router.push("/fabrica"); })}>
          <Trash2 size={16} />
        </button>
      </div>
      <AvisoError texto={error} />
      {(trabajando || d.estado === "error") && (
        <div className="mb-5 rounded-2xl border border-linea bg-tarjeta p-4">
          {d.estado === "error" ? <AvisoError texto={d.error} /> : (
            <>
              <p className="flex items-center gap-2 text-sm"><Loader2 size={15} className="animate-spin" /> {d.mensaje}</p>
              <div className="mt-3 h-2 overflow-hidden rounded-full bg-hundido"><div className="h-full bg-marca transition-all" style={{ width: `${d.progreso}%` }} /></div>
            </>
          )}
        </div>
      )}

      {d.estado === "revision" && (
        <div className="mb-5 rounded-2xl border border-marca/40 bg-tarjeta p-4">
          <p className="flex items-center gap-2 font-semibold"><Clapperboard size={16} /> Antes de montar</p>
          <p className="mt-1 text-sm text-tinta-2">
            El guion y las imagenes estan listos.{d.opciones.clips ? " Sube los clips en sus escenas (abajo)." : ""} Corrige el texto
            si quieres, elige la musica y la voz, y dale a Montar.
          </p>
          <div className="mt-4 grid gap-4 sm:grid-cols-2">
            <div>
              <p className="etiqueta mb-2">Musica</p>
              <select className="campo" value={musica ?? "random"} onChange={(e) => setMusica(e.target.value)}>
                <option value="random">Aleatoria</option>
                <option value="">Sin musica</option>
                {canciones.map((c) => <option key={c} value={c}>{c}</option>)}
              </select>
              {musica && musica !== "random" && (
                <audio key={musica} controls preload="none" className="mt-2 h-8 w-full" src={`/api/motor/musics/${encodeURIComponent(musica)}`} />
              )}
            </div>
            <div>
              <p className="etiqueta mb-2">Voz</p>
              {miVoz ? (
                <p className="flex items-center gap-2 text-sm">
                  <Mic size={14} /> {miVoz.nombre} · {mmss(miVoz.duracion)}
                  <button className="boton boton-fantasma !px-2 !py-1 text-xs" onClick={() => setMiVoz(null)}>Quitar</button>
                </p>
              ) : (
                <p className="text-sm text-tinta-2">{d.opciones.voz.startsWith("clon:") ? "Tu voz clonada" : d.opciones.voz}</p>
              )}
              <div className="mt-2 flex flex-wrap gap-1.5">
                <button className="boton boton-linea !px-2 !py-1 text-xs" disabled={!guion}
                  onClick={() => guion && navigator.clipboard.writeText(guion.escenas.map((e) => e.texto).join("\n\n"))
                    .then(() => { setCopiadoGuion(true); setTimeout(() => setCopiadoGuion(false), 1500); })}>
                  {copiadoGuion ? "Copiado" : "Copiar guion para grabar"}
                </button>
                <label className={`boton boton-linea !px-2 !py-1 text-xs ${subiendoVoz ? "pointer-events-none opacity-50" : "cursor-pointer"}`}>
                  {subiendoVoz && <Loader2 size={12} className="animate-spin" />} {miVoz ? "Cambiar grabacion" : "Subir mi grabacion"}
                  <input type="file" accept="audio/*,video/mp4,video/webm" hidden onChange={async (ev) => {
                    const f = ev.target.files?.[0];
                    if (!f) return;
                    setSubiendoVoz(true);
                    setError(null);
                    try {
                      const r = await fabrica.subirAudio(f);
                      setMiVoz({ voz: "narrada:" + r.voz.split(":").slice(1).join(":"), duracion: r.duracion, nombre: f.name });
                    } catch (e) { setError(String((e as Error).message || e)); }
                    setSubiendoVoz(false);
                  }} />
                </label>
              </div>
              <p className="mt-1.5 text-xs text-tinta-3">Lee el texto de las escenas tal cual: tus palabras marcan el tiempo de cada escena y los subtitulos.</p>
            </div>
          </div>
          <button className="boton boton-acento mt-4" disabled={cambiado || subiendoVoz}
            title={cambiado ? "Guarda primero los cambios del guion" : ""}
            onClick={() => accion(() => fabrica.montar(id, { musica: musica ?? "random", ...(miVoz ? { voz: miVoz.voz } : {}) }))}>
            <Clapperboard size={14} /> Montar video
          </button>
        </div>
      )}

      <div className="grid gap-5 lg:grid-cols-[1.25fr_1fr]">
        <Tarjeta titulo="Videos">
          {d.videos.length === 0 ? (
            <p className="text-sm text-tinta-3">{trabajando ? "Se estan dibujando las escenas…" : "Todavia no hay videos."}</p>
          ) : (
            <div className="flex flex-wrap items-start gap-4">
              {d.videos.map((v) => (
                <div key={v.formato} className="min-w-0" style={{ width: v.alto > v.ancho ? 230 : v.alto === v.ancho ? 300 : 420 }}>
                  <video key={version} src={fabrica.urlVideo(id, v.formato, false, version)} controls className="w-full rounded-xl bg-black" />
                  <div className="mt-2 flex items-center justify-between text-xs text-tinta-3">
                    <span>{v.formato} · {mmss(v.duracion)} · {v.tam_mb} MB</span>
                    <span className="flex gap-1">
                      <button className="boton boton-fantasma !p-1.5" disabled={trabajando}
                        title="Abrir en el editor del Estudio (crea un proyecto con esta voz y estas escenas)"
                        onClick={() => accion(async () => router.push(`/p/${(await fabrica.abrirEditor(id, v.formato)).proyecto}`))}>
                        <SquarePen size={14} />
                      </button>
                      <a className="boton boton-fantasma !p-1.5" href={fabrica.urlVideo(id, v.formato, true, version)} title="Descargar"><Download size={14} /></a>
                    </span>
                  </div>
                </div>
              ))}
            </div>
          )}
          {d.guion?.descripcion && (
            <div className="mt-5 border-t border-linea pt-4 text-sm">
              <p className="etiqueta mb-1">Para publicar</p>
              <p className="font-semibold">{d.guion.titulo}</p>
              <p className="mt-1 text-tinta-2">{d.guion.descripcion}</p>
              {d.capitulos && (
                <pre className="mt-2 whitespace-pre-wrap rounded-lg bg-hundido p-2 font-sans text-xs text-tinta-2"
                  title="Pegalo en la descripcion de YouTube: salen los capitulos en la barra del video">{d.capitulos}</pre>
              )}
              {d.guion.mensaje && <p className="mt-2 text-xs text-tinta-2">Mensaje: {d.guion.mensaje}</p>}
              {d.guion.colores && Object.keys(d.guion.colores).length > 0 && (
                <p className="mt-1 text-xs text-tinta-2">
                  Colores: {Object.entries(d.guion.colores).map(([c, s]) => `${c} = ${s}`).join(" · ")}
                </p>
              )}
            </div>
          )}
        </Tarjeta>

        <div className="space-y-5">
          <Tarjeta titulo="Rehacer">
            <p className="etiqueta mb-2">Estilo</p>
            <GaleriaEstilos valor={estilo} onCambio={setEstilo} compacta />
            <p className="etiqueta mb-2 mt-4">Formatos</p>
            <div className="flex gap-2">
              {(cat?.formatos || ["9:16", "16:9", "1:1"]).map((f) => (
                <button key={f} type="button" onClick={() => alternar(f)}
                  className={`boton ${formatos.includes(f) ? "boton-acento" : "boton-linea"} !px-3 !py-1.5 text-sm`}>{f}</button>
              ))}
            </div>
            <p className="etiqueta mb-2 mt-4">Musica</p>
            <select className="campo" value={musica ?? "random"} onChange={(e) => setMusica(e.target.value)}>
              <option value="random">Aleatoria</option>
              <option value="">Sin musica</option>
              {canciones.map((c) => <option key={c} value={c}>{c}</option>)}
            </select>
            <p className="etiqueta mb-2 mt-4">Imagenes</p>
            <select className="campo" value={visual ?? ""} onChange={(e) => setVisual(e.target.value)}>
              <option value="">Las del estilo</option>
              {cat?.visuales?.map((x) => <option key={x.id} value={x.id}>{x.nombre}</option>)}
            </select>
            <p className="etiqueta mb-2 mt-4">Presentador</p>
            <select className="campo" value={presentador ?? ""} onChange={(e) => setPresentador(e.target.value)}>
              <option value="">Ninguno</option>
              {cat?.presentadores?.map((x) => <option key={x.id} value={x.id}>{x.nombre}</option>)}
            </select>
            <div className="mt-4 flex flex-wrap gap-2">
              <button className="boton boton-acento" disabled={trabajando || !otrasOpciones}
                onClick={() => { setClipsCambiados(false); accion(() => fabrica.rehacer(id, "render", { estilo, formatos, musica: musica ?? "random", visual: visual ?? "", presentador: presentador ?? "" })); }}>
                <RefreshCw size={14} /> Redibujar
              </button>
              <button className="boton boton-linea" disabled={trabajando}
                onClick={() => confirm(grabada ? "Claude repartira tu grabacion en escenas otra vez. ¿Seguir?" : "Claude escribira un guion nuevo para el mismo tema. ¿Seguir?")
                  && accion(() => fabrica.rehacer(id, "guion", { estilo, formatos, musica: musica ?? "random", visual: visual ?? "", presentador: presentador ?? "" }))}>
                Guion nuevo
              </button>
            </div>
          </Tarjeta>

          <Tarjeta titulo="Guion por escenas" extra={cambiado && (
            <button className="boton boton-acento !py-1.5 text-sm" disabled={trabajando}
              onClick={() => guion && accion(() => fabrica.guardarGuion(id, guion))}>
              <Save size={14} /> {d.estado === "revision" ? "Guardar" : "Guardar y rehacer"}
            </button>
          )}>
            {grabada && guion && (
              <p className="mb-3 rounded-xl bg-hundido p-3 text-xs text-tinta-2">
                Es el texto de tu grabacion. Puedes corregir palabras que se oyeron mal, unirlas o separarlas
                («delitoral» → «del litoral») y mover una palabra de una escena a otra. Lo que dices no cambia: para eso, graba de nuevo.
              </p>
            )}
            {!guion ? <p className="text-sm text-tinta-3">Claude esta escribiendo…</p> : (
              <ol className="space-y-3">
                {guion.escenas.map((e, i) => (
                  <li key={i} className="rounded-xl border border-linea p-3">
                    <p className="etiqueta mb-1.5">{i + 1}. {NOMBRE_ESCENA[e.tipo] || e.tipo}</p>
                    <textarea className="campo min-h-16 text-sm" value={e.texto} disabled={trabajando}
                      onChange={(ev) => cambiarTexto(i, ev.target.value)} />
                    {typeof e.video_prompt === "string" && e.video_prompt && (
                      <ClipEscena fid={id} n={i} prompt={e.video_prompt} subido={(d.clips || []).includes(i)} bloqueado={trabajando}
                        formato={d.opciones.formatos[0]} duracion={(e.duracion_s as number) || 0}
                        onCambio={() => { setClipsCambiados(true); cargar(); }} onError={setError} />
                    )}
                  </li>
                ))}
              </ol>
            )}
          </Tarjeta>
        </div>
      </div>
    </main>
  );
}

// Prompt de video de una escena (para hacer el clip en Seedance, Veo...) y la subida del clip: al redibujar, el clip
// va detras de los textos de la escena en lugar de la foto.
function ClipEscena({ fid, n, prompt, subido, bloqueado, formato, duracion, onCambio, onError }: {
  fid: string; n: number; prompt: string; subido: boolean; bloqueado: boolean; formato: string; duracion: number;
  onCambio: () => void; onError: (e: string) => void;
}) {
  const [ocupado, setOcupado] = useState(false);
  const [copiado, setCopiado] = useState(false);
  const accion = async (fn: () => Promise<unknown>) => {
    setOcupado(true);
    try { await fn(); onCambio(); } catch (e) { onError(String((e as Error).message || e)); }
    setOcupado(false);
  };
  return (
    <div className="mt-2 rounded-lg bg-hundido p-2.5 text-xs">
      <div className="mb-1 flex items-center justify-between gap-2">
        <span className="etiqueta">Clip de video {formato}{duracion ? ` · ~${Math.ceil(duracion)} s` : ""}</span>
        <span className={subido ? "font-semibold text-marca" : "text-tinta-3"}>{subido ? "clip subido" : "con foto"}</span>
      </div>
      <p className="text-tinta-2">{prompt}</p>
      <div className="mt-2 flex flex-wrap gap-1.5">
        <button className="boton boton-linea !px-2 !py-1 text-xs" onClick={() => navigator.clipboard.writeText(prompt).then(() => { setCopiado(true); setTimeout(() => setCopiado(false), 1500); })}>
          {copiado ? "Copiado" : "Copiar prompt"}
        </button>
        <label className={`boton boton-linea !px-2 !py-1 text-xs ${bloqueado || ocupado ? "pointer-events-none opacity-50" : "cursor-pointer"}`}>
          {ocupado ? <Loader2 size={12} className="animate-spin" /> : null} {subido ? "Cambiar clip" : "Subir clip"}
          <input type="file" accept="video/*" hidden onChange={(ev) => { const f = ev.target.files?.[0]; if (f) accion(() => fabrica.subirClip(fid, n, f)); }} />
        </label>
        {subido && <button className="boton boton-fantasma !px-2 !py-1 text-xs" disabled={bloqueado || ocupado} onClick={() => accion(() => fabrica.borrarClip(fid, n))}>Quitar</button>}
      </div>
    </div>
  );
}

// Las sesiones viejas guardaban la musica como si/no.
function musicaDe(m: unknown): string {
  return typeof m === "string" ? m : m === false ? "" : "random";
}
