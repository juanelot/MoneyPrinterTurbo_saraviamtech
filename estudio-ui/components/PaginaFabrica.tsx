"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Clapperboard, Copy, CopyPlus, Download, Eraser, Factory, Film, Library, Lightbulb, ListPlus, Loader2, Mic, Pencil, Play, Save, Sparkles, SquarePen, Trash2, TrendingUp, Upload, X } from "lucide-react";
import { Accion, AvisoError, Campo, Deslizador, Segmentado } from "@/components/ui";
import {
  banco, fabrica, listarMusica, mmss, presentadores, type CatalogoFabrica, type FormatoFabrica, type IdeaFabrica, type MoldeFabrica, type ResumenFabrica, type SesionBanco, type VideoFabrica,
} from "@/lib/api";
import { AZURE_VOICES } from "@/lib/voces";
import GaleriaEstilos from "@/components/GaleriaEstilos";
import NuevoPresentador from "@/components/NuevoPresentador";
import Paginacion, { usePaginas } from "@/components/Paginacion";

const TRABAJANDO = ["en cola", "guion", "voz", "render", "montaje"];

export default function PaginaFabrica() {
  const router = useRouter();
  const [cat, setCat] = useState<CatalogoFabrica | null>(null);
  const [lista, setLista] = useState<ResumenFabrica[] | null>(null);
  const [viendo, setViendo] = useState<ResumenFabrica | null>(null);
  const [ocupado, setOcupado] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [enviando, setEnviando] = useState(false);
  const [tema, setTema] = useState("");
  const [nicho, setNicho] = useState("mapas");
  const [estilo, setEstilo] = useState("papel");
  const [formatos, setFormatos] = useState<FormatoFabrica[]>(["9:16"]);
  const [duracion, setDuracion] = useState("55");
  const [idioma, setIdioma] = useState("es-ES");
  const [voz, setVoz] = useState("es-ES-AlvaroNeural-Male");
  // voz: de Microsoft o una grabacion propia (el guion se adapta a ella)
  const [fuente, setFuente] = useState<"microsoft" | "grabacion">("microsoft");
  const [grabacion, setGrabacion] = useState<{ voz: string; duracion: number; nombre: string } | null>(null);
  const [subiendoVoz, setSubiendoVoz] = useState(false);
  // musica: "random", "" (sin musica) o una cancion
  const [musica, setMusica] = useState("random");
  const [volMusica, setVolMusica] = useState(0.16);
  const [canciones, setCanciones] = useState<string[]>([]);
  const subidaMusica = useRef<HTMLInputElement>(null);
  const [subtitulos, setSubtitulos] = useState(true);
  const [efectos, setEfectos] = useState(true);
  const [foco, setFoco] = useState(true);
  const [nuevos, setNuevos] = useState(true);
  // por defecto se para tras el guion: copias el texto, lo grabas (o usas la voz de Microsoft) y luego se monta
  const [revisar, setRevisar] = useState(true);
  const [clips, setClips] = useState(false);
  const [usarBanco, setUsarBanco] = useState(false);
  const [bancoSel, setBancoSel] = useState<string[]>([]);
  const [bancoModo, setBancoModo] = useState<"insertos" | "mayoria">("insertos");
  const [bancos, setBancos] = useState<SesionBanco[]>([]);
  // moldes: opciones guardadas; lo que no esta en el formulario (receta, velocidad) viaja en "extra"
  const [moldes, setMoldes] = useState<MoldeFabrica[]>([]);
  const [molde, setMolde] = useState("");
  const [extra, setExtra] = useState<{ receta?: string; velocidad?: number }>({});
  useEffect(() => { fabrica.moldes().then((r) => setMoldes(r.moldes)).catch(() => {}); }, []);
  useEffect(() => { banco.listar().then((r) => setBancos(r.videos.filter((b) => b.estado === "listo"))).catch(() => {}); }, []);
  const [varios, setVarios] = useState(false);
  const [serie, setSerie] = useState("");
  const [visual, setVisual] = useState("");
  // presentador: personaje que habla abajo a la derecha (los subtitulos pasan arriba a la izquierda)
  const [presentador, setPresentador] = useState("");
  const [nuevoPres, setNuevoPres] = useState(false);
  // cierre de marca: el nombre del canal, se recuerda en este navegador
  const [marca, setMarca] = useState("");
  useEffect(() => { setMarca(localStorage.getItem("fabrica-marca") || ""); }, []);
  const cambiarMarca = (m: string) => { setMarca(m); localStorage.setItem("fabrica-marca", m); };
  // banco de temas del nicho
  const [ideas, setIdeas] = useState<IdeaFabrica[]>([]);
  const [sugiriendo, setSugiriendo] = useState(false);
  useEffect(() => { fabrica.ideas(nicho).then((r) => setIdeas(r.ideas)).catch(() => setIdeas([])); }, [nicho]);
  async function sugerir() {
    setSugiriendo(true);
    setError(null);
    try { setIdeas((await fabrica.sugerir(nicho, serie)).ideas); } catch (e) { setError(String((e as Error).message || e)); }
    setSugiriendo(false);
  }
  const usarIdea = (t: string) => setTema((x) => (varios && x.trim() ? `${x.trim()}\n${t}` : t));
  const quitarIdea = (t: string) => fabrica.quitarIdea(nicho, t).then((r) => setIdeas(r.ideas)).catch(() => {});

  const cargar = useCallback(() => fabrica.listar()
    .then((r) => setLista(r.videos))
    .catch((e) => setError(String(e.message || e))), []);
  useEffect(() => {
    fabrica.catalogo().then(setCat).catch((e) => setError(String(e.message || e)));
    cargar();
    listarMusica().then(setCanciones);
  }, [cargar]);
  const trabajando = !!lista?.some((s) => TRABAJANDO.includes(s.estado));
  useEffect(() => {
    if (!trabajando) return;
    const k = setInterval(cargar, 3000);
    return () => clearInterval(k);
  }, [trabajando, cargar]);

  const idiomas = useMemo(() => [...new Set(AZURE_VOICES.map((v) => v.lang))].sort(), []);
  const voces = AZURE_VOICES.filter((v) => v.lang === idioma);
  const nombreIdioma = idioma.startsWith("es") ? "espanol" : idioma.startsWith("en") ? "ingles" : idioma.startsWith("pt") ? "portugues" : idioma;

  const alternar = (f: FormatoFabrica) =>
    setFormatos((x) => (x.includes(f) ? (x.length > 1 ? x.filter((y) => y !== f) : x) : [...x, f]));

  async function accion(s: ResumenFabrica, fn: () => Promise<unknown>) {
    setOcupado(s.id);
    setError(null);
    try {
      await fn();
      await cargar();
    } catch (e) { setError(String((e as Error).message || e)); }
    setOcupado(null);
  }
  const borrar = (s: ResumenFabrica) =>
    confirm(`¿Borrar «${s.titulo}» y todo lo generado?`) && accion(s, () => fabrica.borrar(s.id));
  const renombrar = (s: ResumenFabrica) => {
    const t = prompt("Nuevo titulo", s.titulo);
    if (t && t.trim() && t !== s.titulo) accion(s, () => fabrica.renombrar(s.id, t.trim()));
  };
  const duplicar = (s: ResumenFabrica) => accion(s, async () => router.push(`/fabrica/${(await fabrica.duplicar(s.id)).id}`));
  const liberar = (s: ResumenFabrica) =>
    confirm(`¿Liberar espacio de «${s.titulo}»? Se borran solo las escenas ya dibujadas (cache). ` +
      "El video, el guion, la voz y tus clips se quedan; si rehaces o lo abres en el editor, se vuelven a dibujar.") &&
    accion(s, async () => {
      const r = await fabrica.liberar(s.id);
      alert(`${(r.liberado / 1048576).toFixed(0)} MB liberados.`);
    });
  const [episodios, setEpisodios] = useState<ResumenFabrica | null>(null);
  const siguiente = (s: ResumenFabrica, cuantos: number, idea: string, final: boolean, sinParar: boolean) => {
    setEpisodios(null);
    accion(s, async () => {
      if (cuantos === 1 && !sinParar) router.push(`/fabrica/${(await fabrica.siguiente(s.id, idea)).id}`);
      else await fabrica.temporada(s.id, cuantos, idea, final, sinParar);
    });
  };
  const montarSaga = (s: ResumenFabrica) => {
    const n = (lista || []).filter((x) => x.saga === s.saga && x.estado === "revision").length;
    if (s.saga && confirm(`¿Montar los ${n} episodios de «${s.saga_nombre || s.titulo}» que esperan? Se hacen de uno en uno, con lo que ya tienen.`))
      accion(s, () => fabrica.montarSaga(s.saga!));
  };
  const paginas = usePaginas(lista, 12);

  const vozFinal = fuente === "microsoft" ? voz : grabacion?.voz || "";
  const listo = !!vozFinal && (fuente === "grabacion" || !!tema.trim());
  // lote: un video por linea (no con grabacion propia, que es de un solo video)
  const temas = varios && fuente !== "grabacion" ? tema.split("\n").map((t) => t.trim()).filter(Boolean) : [];

  async function subirVoz(f: File | undefined) {
    if (!f) return;
    setSubiendoVoz(true);
    setError(null);
    try {
      const r = await fabrica.subirAudio(f);
      setGrabacion({ ...r, nombre: f.name });
    } catch (e) { setError(String((e as Error).message || e)); }
    setSubiendoVoz(false);
  }

  async function subirMusica(f: File | undefined) {
    if (!f) return;
    const fd = new FormData();
    fd.append("file", f);
    const res = await fetch("/api/motor/musics", { method: "POST", body: fd });
    const j = await res.json().catch(() => null);
    setCanciones(await listarMusica());
    if (j?.data?.file) setMusica(j.data.file);
    else setError("No se pudo subir la cancion (solo MP3)");
  }

  async function crear() {
    setEnviando(true);
    setError(null);
    try {
      const opciones = { nicho, estilo, formatos, voz: vozFinal, duracion: Number(duracion), musica,
        musica_volumen: volMusica, subtitulos, efectos, foco, nuevos, idioma: nombreIdioma, velocidad: 1, serie, marca, visual, presentador, revisar, clips, banco: usarBanco ? bancoSel : [], banco_modo: bancoModo, ...extra };
      const unico = temas.length > 1 ? "" : (temas[0] || tema).trim();
      if (unico) {
        // no repetir: si ya hay un video casi igual, se pregunta antes
        const { parecido } = await fabrica.parecido(unico, nicho).catch(() => ({ parecido: null }));
        if (parecido && !confirm(`Ya hiciste un video muy parecido: «${parecido.titulo}». ¿Hacerlo igualmente?`)) {
          setEnviando(false);
          return;
        }
      }
      if (temas.length > 1) {
        await fabrica.lote(temas, opciones);
        setTema("");
        setEnviando(false);
        await cargar();
        return;
      }
      const s = await fabrica.crear({ ...opciones, tema: temas[0] || tema });
      router.push(`/fabrica/${s.id}`);
    } catch (e) {
      setError(String((e as Error).message || e));
      setEnviando(false);
    }
  }

  function usarMolde(mid: string) {
    setMolde(mid);
    const m = moldes.find((x) => x.id === mid);
    if (!m) { setExtra({}); return; }
    const o = m.opciones;
    setNicho(o.nicho); setEstilo(o.estilo); setFormatos(o.formatos); setDuracion(String(o.duracion));
    setMusica(o.musica); setVolMusica(o.musica_volumen); setSubtitulos(o.subtitulos); setEfectos(o.efectos);
    setFoco(o.foco ?? true); setNuevos(o.nuevos); setSerie(o.serie || ""); setVisual(o.visual || ""); setPresentador(o.presentador || "");
    setRevisar(!!o.revisar); setClips(!!o.clips);
    setBancoSel(o.banco || []); setUsarBanco(!!o.banco?.length); setBancoModo(o.banco_modo || "insertos");
    if (o.marca) cambiarMarca(o.marca);
    {
      const v = AZURE_VOICES.find((x) => x.value === o.voz);
      setFuente("microsoft");
      if (v) setIdioma(v.lang);
      setVoz(o.voz);
    }
    setExtra({ ...(o.receta ? { receta: o.receta } : {}), ...(o.velocidad ? { velocidad: o.velocidad } : {}) });
  }
  async function guardarMolde() {
    const nombre = prompt("Nombre del molde (con el mismo nombre se reemplaza)", moldes.find((x) => x.id === molde)?.nombre || "");
    if (!nombre?.trim()) return;
    setError(null);
    try {
      const m = await fabrica.guardarMolde(nombre.trim(), { opciones: { nicho, estilo, formatos, voz: vozFinal, duracion: Number(duracion), musica,
        musica_volumen: volMusica, subtitulos, efectos, foco, nuevos, idioma: nombreIdioma, velocidad: 1, serie, marca, visual, presentador, revisar, clips, banco: usarBanco ? bancoSel : [], banco_modo: bancoModo, ...extra } });
      const r = await fabrica.moldes();
      setMoldes(r.moldes);
      setMolde(m.id);
    } catch (e) { setError(String((e as Error).message || e)); }
  }
  async function borrarMolde() {
    const m = moldes.find((x) => x.id === molde);
    if (!m || !confirm(`¿Borrar el molde «${m.nombre}»?`)) return;
    await fabrica.borrarMolde(m.id).catch(() => {});
    setMoldes((x) => x.filter((y) => y.id !== m.id));
    setMolde("");
    setExtra({});
  }

  return (
    <main className="mx-auto max-w-6xl px-4 pb-24 pt-12">
      <section className="mb-10 grid gap-8 md:grid-cols-[1fr_1.15fr]">
        <div>
          <p className="etiqueta mb-3 flex items-center gap-2">
            <Factory size={15} /> Videos enteros desde un tema
          </p>
          <h1 className="font-display text-4xl font-semibold leading-tight tracking-tight md:text-5xl">Fabrica</h1>
          <p className="mt-4 max-w-xl text-tinta-2">
            Escribe el tema y elige nicho, estilo y formatos. Claude escribe el guion por escenas, la voz marca el segundo
            de cada palabra y cada escena se dibuja con codigo (mapas, satelite, banderas, personajes, rutas, cifras) justo
            cuando se dice. Sin modelos de video: no gasta creditos.
          </p>
          <div className="mt-5 flex flex-wrap gap-2">
            <Link href="/fabrica/biblioteca" className="boton boton-linea inline-flex"><Library size={15} /> Biblioteca de dibujos</Link>
            <Link href="/fabrica/ideas" className="boton boton-linea inline-flex"><TrendingUp size={15} /> Ideas virales</Link>
            <Link href="/fabrica/clonar" className="boton boton-linea inline-flex"><CopyPlus size={15} /> Clonar video</Link>
            <Link href="/fabrica/banco" className="boton boton-linea inline-flex"><Clapperboard size={15} /> Banco de clips</Link>
          </div>
          {cat?.falta && <p className="mt-4 rounded-xl bg-error-suave p-3 text-sm text-error">{cat.falta}</p>}
        </div>
        <div className="rounded-2xl border border-linea bg-tarjeta p-5 shadow-sm">
          <div className="mb-4 flex items-end gap-2 border-b border-linea pb-4">
            <Campo etiqueta="Molde (opciones guardadas)" className="flex-1">
              <select className="campo" value={molde} onChange={(e) => usarMolde(e.target.value)}>
                <option value="">Sin molde</option>
                {moldes.map((m) => <option key={m.id} value={m.id}>{m.nombre}</option>)}
              </select>
            </Campo>
            <button type="button" className="boton boton-linea shrink-0 !px-3" title="Guardar estas opciones como molde" onClick={guardarMolde}
              disabled={!vozFinal}><Save size={15} /></button>
            {molde && (
              <button type="button" className="boton boton-fantasma shrink-0 !px-3" title="Borrar este molde" onClick={borrarMolde}>
                <Trash2 size={15} />
              </button>
            )}
          </div>
          {extra.receta && <p className="mb-3 text-xs text-tinta-3">Este molde sigue la estructura de un video clonado.</p>}
          <Campo etiqueta={fuente === "grabacion" ? "De que trata (opcional: el texto sale de tu grabacion)" : "Tema"}>
            <textarea className={`campo ${varios ? "min-h-32" : "min-h-20"}`} value={tema} onChange={(e) => setTema(e.target.value)}
              placeholder={varios ? "Por que Bolivia no tiene mar\nPor que Alaska es de Estados Unidos\n…" : "Por que Bolivia no tiene mar"} />
          </Campo>
          {fuente !== "grabacion" && (
            <label className="mt-2 flex items-center gap-2 text-sm text-tinta-2"
              title="Cada linea es un video con las mismas opciones; se hacen de uno en uno">
              <input type="checkbox" checked={varios} onChange={(e) => setVarios(e.target.checked)} />
              Varios videos: uno por linea{temas.length > 1 ? ` (${temas.length})` : ""}
            </label>
          )}
          {fuente !== "grabacion" && (
            <div className="mt-3">
              <div className="flex items-center justify-between gap-2">
                <p className="etiqueta">Banco de temas{ideas.length ? ` (${ideas.length})` : ""}</p>
                <button type="button" className="boton boton-linea !px-2.5 !py-1 text-xs" disabled={sugiriendo} onClick={sugerir}
                  title="Claude propone temas nuevos para este nicho (y serie) sin repetir los videos que ya hiciste">
                  {sugiriendo ? <Loader2 size={13} className="animate-spin" /> : <Lightbulb size={13} />} {sugiriendo ? "Pensando…" : "Sugerir temas"}
                </button>
              </div>
              {ideas.length > 0 && (
                <ul className="mt-2 max-h-40 space-y-1 overflow-y-auto pr-1">
                  {ideas.map((i) => (
                    <li key={i.tema} className="group flex items-start gap-1.5 rounded-lg border border-linea px-2 py-1.5 text-xs hover:border-tinta-3">
                      <button type="button" className="flex-1 text-left" onClick={() => usarIdea(i.tema)} title={[i.gancho && `Gancho: ${i.gancho}`, i.porque].filter(Boolean).join("\n") || "Usar este tema"}>
                        {i.origen === "virales" && <TrendingUp size={12} className="mr-1 inline text-acento" />}{i.tema}
                      </button>
                      <button type="button" className="text-tinta-3 opacity-0 transition hover:text-error group-hover:opacity-100" title="Quitar del banco"
                        onClick={() => quitarIdea(i.tema)}><X size={13} /></button>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          )}
          <div className="mt-4 grid gap-4 sm:grid-cols-2">
            <Campo etiqueta="Nicho">
              <select className="campo" value={nicho} onChange={(e) => setNicho(e.target.value)}>
                {cat?.nichos.map((n) => <option key={n.id} value={n.id}>{n.nombre}</option>)}
              </select>
            </Campo>
            <Campo etiqueta="Serie">
              <select className="campo" value={serie} onChange={(e) => {
                setSerie(e.target.value);
                // el explicador esta pensado con su estilo y un presentador
                if (e.target.value === "explicador") { setEstilo("explicador"); if (!presentador) setPresentador("leo"); }
              }}
                title={cat?.series?.find((s) => s.id === serie)?.descripcion || "Sin formato fijo"}>
                <option value="">Ninguna</option>
                {cat?.series?.map((s) => <option key={s.id} value={s.id}>{s.nombre}</option>)}
              </select>
            </Campo>
            <Campo etiqueta="Presentador">
              <select className="campo" value={presentador} onChange={(e) => setPresentador(e.target.value)}
                title={cat?.presentadores?.find((x) => x.id === presentador)?.descripcion || "Sin presentador"}>
                <option value="">Ninguno</option>
                {cat?.presentadores?.map((x) => <option key={x.id} value={x.id}>{x.nombre} — {x.descripcion}</option>)}
              </select>
              <div className="mt-1.5 flex items-center gap-2">
                {presentador.startsWith("propio:") && (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img src={presentadores.urlImagen(presentador.slice(7))} alt="" className="h-14 w-14 rounded-lg bg-hundido object-contain" />
                )}
                {presentador.startsWith("propio:") && (
                  <button type="button" className="boton boton-fantasma !px-2 !py-1 text-xs text-error" title="Borrar este presentador"
                    onClick={() => {
                      const nombre = cat?.presentadores?.find((x) => x.id === presentador)?.nombre || "este presentador";
                      if (!confirm(`¿Borrar a ${nombre}? Los videos ya hechos no cambian.`)) return;
                      presentadores.borrar(presentador.slice(7))
                        .then(() => fabrica.catalogo()).then((c) => { setCat(c); setPresentador(""); })
                        .catch((e) => alert(String((e as Error).message || e)));
                    }}>
                    <Trash2 size={13} /> Borrar
                  </button>
                )}
                {!nuevoPres && (
                  <button type="button" className="boton boton-fantasma !px-2 !py-1 text-xs" onClick={() => setNuevoPres(true)}>
                    + Crear el mio (con foto o descripcion)
                  </button>
                )}
              </div>
              {nuevoPres && (
                <NuevoPresentador onCerrar={() => setNuevoPres(false)} onCreado={(id) => {
                  setNuevoPres(false);
                  fabrica.catalogo().then((c) => { setCat(c); setPresentador(id); }).catch(() => {});
                }} />
              )}
            </Campo>
            <Campo etiqueta={fuente === "grabacion" ? "Idioma de los textos" : "Idioma de la voz"}>
              <select className="campo" value={idioma} onChange={(e) => {
                setIdioma(e.target.value);
                const primera = AZURE_VOICES.find((v) => v.lang === e.target.value);
                if (primera) setVoz(primera.value);
              }}>
                {idiomas.map((l) => <option key={l} value={l}>{l}</option>)}
              </select>
            </Campo>
            {fuente === "microsoft" && (
              <Campo etiqueta="Voz">
                <select className="campo" value={voz} onChange={(e) => setVoz(e.target.value)}>
                  {voces.map((v) => <option key={v.value} value={v.value}>{v.label}</option>)}
                </select>
              </Campo>
            )}
          </div>
          <div className="mt-4">
            <Segmentado valor={fuente} onChange={setFuente} opciones={[
              { v: "microsoft" as const, t: "Voz de Microsoft" },
              { v: "grabacion" as const, t: "Subir grabacion" },
            ]} />
            {fuente === "grabacion" && (
              <div className="mt-3">
                <label className="flex cursor-pointer items-center gap-2 rounded-xl border border-dashed border-linea p-3 text-sm text-tinta-2 hover:border-tinta-3">
                  {subiendoVoz ? <Loader2 size={16} className="animate-spin" /> : <Mic size={16} />}
                  {grabacion ? `${grabacion.nombre} · ${mmss(grabacion.duracion)}` : "Tu narracion grabada (mp3, wav, m4a…)"}
                  <input type="file" accept="audio/*,.m4a,.opus" className="hidden" disabled={subiendoVoz}
                    onChange={(e) => subirVoz(e.target.files?.[0])} />
                </label>
                <p className="mt-1.5 text-xs text-tinta-3">
                  Whisper escucha cada palabra y Claude reparte tu texto en escenas sin cambiarlo: cada mapa sale justo cuando lo dices.
                </p>
              </div>
            )}
          </div>
          <div className="mt-4">
            <p className="etiqueta mb-1.5">Estilo</p>
            <GaleriaEstilos valor={estilo} onCambio={setEstilo} />
          </div>
          <Campo etiqueta="Imagenes" className="mt-4">
            <select className="campo" value={visual} onChange={(e) => setVisual(e.target.value)}>
              <option value="">Las del estilo</option>
              {cat?.visuales?.map((x) => <option key={x.id} value={x.id}>{x.nombre}</option>)}
            </select>
            {visual && !["", "madera", "plano", "grabado"].includes(visual) && (
              <p className="mt-1.5 text-xs text-tinta-3">
                Los dibujos que aun no esten en este aspecto los hace Nano Banana mientras se prepara el video (~45 s cada uno,
                solo en el PC con Flow) y quedan guardados para los siguientes.
              </p>
            )}
          </Campo>
          <div className="mt-4 flex flex-wrap items-end gap-5">
            <Campo etiqueta="Formatos">
              <div className="flex gap-2">
                {(cat?.formatos || ["9:16", "16:9", "1:1"]).map((f) => (
                  <button key={f} type="button" onClick={() => alternar(f)}
                    className={`boton ${formatos.includes(f) ? "boton-acento" : "boton-linea"} !px-3 !py-1.5 text-sm`}>{f}</button>
                ))}
              </div>
            </Campo>
            {fuente !== "grabacion" && (
              <Campo etiqueta="Duracion">
                <Segmentado valor={duracion} onChange={setDuracion}
                  opciones={[{ v: "35", t: "~35 s" }, { v: "55", t: "~55 s" }, { v: "80", t: "~80 s" },
                    { v: "180", t: "~3 min" }, { v: "300", t: "~5 min" }, { v: "480", t: "~8 min" }]} />
                {Number(duracion) > 120 && (
                  <p className="mt-1.5 max-w-sm text-xs text-tinta-3">
                    Video largo para YouTube: se escribe por capitulos (con sus minutos para la descripcion). Mejor en 16:9.
                    Tarda bastante mas en dibujarse.
                  </p>
                )}
              </Campo>
            )}
          </div>
          <div className="mt-4 grid items-end gap-4 sm:grid-cols-[1.4fr_1fr]">
            <Campo etiqueta="Musica">
              <div className="flex gap-2">
                <select className="campo" value={musica} onChange={(e) => setMusica(e.target.value)}>
                  <option value="random">Aleatoria</option>
                  <option value="">Sin musica</option>
                  {canciones.map((c) => <option key={c} value={c}>{c}</option>)}
                </select>
                <button type="button" className="boton boton-linea shrink-0 !px-3" title="Subir MP3" onClick={() => subidaMusica.current?.click()}>
                  <Upload size={15} />
                </button>
                <input ref={subidaMusica} type="file" accept="audio/mpeg,.mp3" hidden onChange={(e) => subirMusica(e.target.files?.[0])} />
              </div>
            </Campo>
            {musica !== "" && (
              <Campo etiqueta="Volumen">
                <Deslizador valor={volMusica} min={0.05} max={0.5} paso={0.01} onChange={setVolMusica} formato={(x) => `${Math.round(x * 100)}%`} />
              </Campo>
            )}
          </div>
          {musica && musica !== "random" && (
            <audio key={musica} controls preload="none" className="mt-2 h-8 w-full" src={`/api/motor/musics/${encodeURIComponent(musica)}`} />
          )}
          <Campo etiqueta="Cierre de marca (opcional)" className="mt-4">
            <input className="campo" value={marca} maxLength={40} onChange={(e) => cambiarMarca(e.target.value)}
              placeholder="@tucanal: sale al final de cada video" />
          </Campo>
          <div className="mt-4 flex flex-wrap gap-5 text-sm text-tinta-2">
            <label className="flex items-center gap-2"><input type="checkbox" checked={subtitulos} onChange={(e) => setSubtitulos(e.target.checked)} /> Subtitulos</label>
            <label className="flex items-center gap-2"><input type="checkbox" checked={efectos} onChange={(e) => setEfectos(e.target.checked)} /> Efectos de sonido</label>
            <label className="flex items-center gap-2" title="Solo brilla lo que se nombra: en listas, barras, lineas de tiempo y mapas que van de un sitio a otro, lo de antes se apaga">
              <input type="checkbox" checked={foco} onChange={(e) => setFoco(e.target.checked)} /> Foco
            </label>
            <label className="flex items-center gap-2" title="Si a Claude le falta un personaje o una escena, Nano Banana lo dibuja y se guarda en la biblioteca (solo en el PC con Flow)">
              <input type="checkbox" checked={nuevos} onChange={(e) => setNuevos(e.target.checked)} /> Dibujos nuevos con Nano Banana
            </label>
            <label className="flex items-center gap-2" title="Se para con el guion y las imagenes hechos: subes tus clips, tu voz leyendo el guion o eliges la musica, y luego Montar">
              <input type="checkbox" checked={revisar || clips} disabled={clips} onChange={(e) => setRevisar(e.target.checked)} /> Revisar antes de montar
            </label>
            <label className="flex items-center gap-2" title="Cada ilustracion trae su prompt de video para hacer el clip aparte (Seedance, Veo...) y subirlo antes de montar">
              <input type="checkbox" checked={clips} onChange={(e) => setClips(e.target.checked)} /> Clips de video
            </label>
          </div>
          {bancos.length > 0 && (
            <div className={`mt-4 rounded-xl border p-3 ${usarBanco ? "border-marca" : "border-linea"}`}>
              <label className="flex cursor-pointer items-start gap-2 text-sm">
                <input type="checkbox" className="mt-1" checked={usarBanco}
                  onChange={(e) => { setUsarBanco(e.target.checked); if (e.target.checked && !bancoSel.length) setBancoSel([bancos[0].id]); }} />
                <span>
                  <span className="font-semibold">Usar clips reales del banco</span>
                  <span className="block text-xs text-tinta-3">Sin marcar: el video sale solo con dibujos. Marcado: Claude pone clips de los videos que elijas detras de las escenas donde pegan.</span>
                </span>
              </label>
              {usarBanco && <>
              <p className="etiqueta mb-1.5 mt-3">De que videos del banco</p>
              <div className="flex flex-wrap gap-1.5">
                {bancos.map((b) => {
                  const si = bancoSel.includes(b.id);
                  return (
                    <button key={b.id} type="button" title={b.origen}
                      onClick={() => setBancoSel((x) => si ? x.filter((y) => y !== b.id) : [...x, b.id])}
                      className={`max-w-56 truncate rounded-full border px-2.5 py-1 text-xs ${si ? "border-marca bg-marca/10 text-tinta" : "border-linea text-tinta-2 hover:border-tinta-3"}`}>
                      {b.titulo} · {b.n_clips}
                    </button>
                  );
                })}
              </div>
              {bancoSel.length > 0 && (
                <div className="mt-2">
                  <Segmentado valor={bancoModo} onChange={setBancoModo}
                    opciones={[{ v: "insertos", t: "Insertos (1 de cada 3)" }, { v: "mayoria", t: "Casi todo con clips" }]} />
                </div>
              )}
              </>}
            </div>
          )}
          <button className="boton boton-acento mt-5 w-full justify-center" disabled={enviando || !listo || !!cat?.falta} onClick={crear}>
            {enviando ? <Loader2 size={15} className="animate-spin" /> : <Sparkles size={15} />} {enviando ? "Empezando…" : temas.length > 1 ? `Hacer ${temas.length} videos` : "Hacer el video"}
          </button>
          <p className="mt-2 text-xs text-tinta-3">Cada formato se dibuja aparte: en un PC normal, ~1 min por cada 5 s de video.</p>
        </div>
      </section>

      <AvisoError texto={error} />

      {!lista ? (
        <Loader2 className="animate-spin text-tinta-3" />
      ) : lista.length === 0 ? (
        <p className="rounded-2xl border border-dashed border-linea p-10 text-center text-tinta-3">Todavia no hay videos. Escribe el primer tema.</p>
      ) : (
        <ul className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {paginas.items.map((s) => {
            const v = principal(s.videos || []);
            const enCurso = TRABAJANDO.includes(s.estado);
            return (
              <li key={s.id} className="group flex flex-col overflow-hidden rounded-2xl border border-linea bg-tarjeta transition hover:shadow-md">
                <button onClick={() => (v ? setViendo(s) : router.push(`/fabrica/${s.id}`))}
                  className="relative aspect-video overflow-hidden bg-hundido text-left" title={v ? "Reproducir" : "Abrir"}>
                  {v ? (
                    <>
                      <video src={`${fabrica.urlVideo(s.id, v.formato, false, Math.round(v.creado))}#t=1`}
                        className="absolute inset-0 h-full w-full bg-black object-contain" muted preload="metadata" />
                      <span className="absolute inset-0 grid place-items-center bg-black/0 transition group-hover:bg-black/30">
                        <span className="grid h-12 w-12 place-items-center rounded-full bg-white/90 text-tinta opacity-0 shadow transition group-hover:opacity-100">
                          <Play size={20} className="ml-0.5" />
                        </span>
                      </span>
                    </>
                  ) : (
                    <div className="grid h-full place-items-center text-tinta-3">
                      <div className="flex flex-col items-center gap-1.5">
                        {enCurso ? <Loader2 size={26} className="animate-spin" /> : <Film size={28} />}
                        <span className="text-xs">{enCurso ? `${s.mensaje} (${s.progreso}%)` : s.estado === "revision" ? "Listo para montar · abrir" : "Sin video todavia · abrir"}</span>
                      </div>
                    </div>
                  )}
                  {enCurso && (
                    <span className="latido absolute left-3 top-3 rounded-full bg-acento px-2.5 py-0.5 text-xs font-semibold text-sobre-acento">
                      trabajando
                    </span>
                  )}
                  {v && (
                    <span className="absolute bottom-2 right-2 rounded-md bg-black/70 px-1.5 py-0.5 text-xs text-white">
                      {(s.videos || []).length > 1 ? `${s.videos.length} formatos · ` : ""}{mmss(v.duracion)}
                    </span>
                  )}
                </button>
                <Link href={`/fabrica/${s.id}`} className="block flex-1 p-4">
                  <h3 className="line-clamp-1 font-semibold" title={s.titulo}>{s.titulo}</h3>
                  {(s.saga || (s.opciones.episodio || 1) > 1) && (
                    <p className="mt-1 text-xs font-semibold text-acento">
                      Episodio {s.opciones.episodio || 1}{s.saga_nombre ? ` · ${s.saga_nombre}` : ""}
                    </p>
                  )}
                  <p className="mt-1 text-xs text-tinta-3">
                    {cat?.estilos.find((x) => x.id === s.opciones.estilo)?.nombre || s.opciones.estilo} · {s.opciones.formatos.join(" · ")}
                    {" · "}{new Date(s.actualizado * 1000).toLocaleString()}
                  </p>
                  {s.estado === "error" && <p className="mt-1 line-clamp-2 text-xs text-error">{s.error}</p>}
                </Link>
                <div className="flex flex-wrap items-center gap-0.5 border-t border-linea px-1.5 py-1.5">
                  {ocupado === s.id ? (
                    <span className="flex items-center gap-2 px-2 py-1.5 text-xs text-tinta-3">
                      <Loader2 size={14} className="animate-spin" /> Un momento…
                    </span>
                  ) : (
                    <>
                      <Accion icono={<Play size={14} />} texto="Ver" disabled={!v} onClick={() => setViendo(s)} />
                      <Accion icono={<Download size={14} />} texto="Descargar" disabled={!v}
                        href={v ? fabrica.urlVideo(s.id, v.formato, true) : undefined} />
                      <Accion icono={<SquarePen size={14} />} texto="Editar" soloIcono derecha href={`/fabrica/${s.id}`} />
                      <Accion icono={<ListPlus size={14} />} texto="Siguiente episodio" soloIcono disabled={enCurso || s.estado === "error"} onClick={() => setEpisodios(s)} />
                      {s.saga && s.estado === "revision" && (
                        <Accion icono={<Clapperboard size={14} />} texto="Montar toda la saga" soloIcono onClick={() => montarSaga(s)} />
                      )}
                      <Accion icono={<Copy size={14} />} texto="Duplicar" soloIcono disabled={enCurso} onClick={() => duplicar(s)} />
                      <Accion icono={<Pencil size={14} />} texto="Renombrar" soloIcono onClick={() => renombrar(s)} />
                      <Accion icono={<Eraser size={14} />} texto="Liberar espacio (cache de escenas)" soloIcono disabled={enCurso} onClick={() => liberar(s)} />
                      <Accion icono={<Trash2 size={14} />} texto="Borrar" soloIcono peligro disabled={enCurso} onClick={() => borrar(s)} />
                    </>
                  )}
                </div>
              </li>
            );
          })}
        </ul>
      )}
      <Paginacion {...paginas} />

      {viendo && <Reproductor s={viendo} onCerrar={() => setViendo(null)} />}
      {episodios && <SiguientesEpisodios s={episodios} onCerrar={() => setEpisodios(null)} onHacer={siguiente} />}
    </main>
  );
}

// Siguiente episodio: uno (como antes) o una tanda que Claude planea de una vez (guiones en orden, luego voz y render)
function SiguientesEpisodios({ s, onCerrar, onHacer }: {
  s: ResumenFabrica; onCerrar: () => void;
  onHacer: (s: ResumenFabrica, cuantos: number, idea: string, final: boolean, sinParar: boolean) => void;
}) {
  const [cuantos, setCuantos] = useState(3);
  const [idea, setIdea] = useState("");
  const [final, setFinal] = useState(false);
  const [sinParar, setSinParar] = useState(true);
  const n = (s.opciones.episodio || 1) + 1;
  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-black/50 p-4" onClick={onCerrar}>
      <div className="w-full max-w-md rounded-2xl border border-linea bg-tarjeta p-5 shadow-xl" onClick={(e) => e.stopPropagation()}>
        <div className="mb-3 flex items-start justify-between gap-3">
          <div>
            <h3 className="font-display text-lg font-semibold">Siguientes episodios</h3>
            <p className="text-xs text-tinta-3">Siguen a «{s.titulo}»</p>
          </div>
          <button onClick={onCerrar} className="boton boton-fantasma !p-1.5" title="Cerrar"><X size={16} /></button>
        </div>
        {s.saga_despues && (
          <p className="mb-3 rounded-xl bg-hundido p-3 text-xs text-tinta-2"><b>Habia quedado pendiente:</b> {s.saga_despues}</p>
        )}
        <Campo etiqueta="Cuantos episodios" ayuda={cuantos > 1
          ? `Del ${n} al ${n + cuantos - 1}. Claude planea la tanda en una llamada corta; luego hace todos los guiones en orden y despues la voz y el render de cada uno.`
          : `Solo el episodio ${n}.`}>
          <input type="number" min={1} max={10} value={cuantos} className="campo w-24"
            onChange={(e) => setCuantos(Math.min(10, Math.max(1, Number(e.target.value) || 1)))} />
        </Campo>
        <Campo etiqueta="Que pasa (opcional)" ayuda="Vacio = lo decide Claude siguiendo la historia." className="mt-3">
          <textarea value={idea} onChange={(e) => setIdea(e.target.value)} rows={3} className="campo w-full"
            placeholder="Ej.: encuentran un barco y llegan a una isla que parece segura" />
        </Campo>
        {cuantos > 1 && (
          <label className="mt-3 flex items-center gap-2 text-sm">
            <input type="checkbox" checked={final} onChange={(e) => setFinal(e.target.checked)} />
            El ultimo episodio cierra la historia (si no, queda abierta para otra tanda)
          </label>
        )}
        <label className="mt-2 flex items-center gap-2 text-sm">
          <input type="checkbox" checked={sinParar} onChange={(e) => setSinParar(e.target.checked)} />
          Hacer todo sin parar: cada episodio sale ya montado (no espera a que revises ni le des a Montar)
        </label>
        <div className="mt-5 flex justify-end gap-2">
          <button onClick={onCerrar} className="boton boton-linea">Cancelar</button>
          <button onClick={() => onHacer(s, cuantos, idea.trim(), final, sinParar)} className="boton boton-acento">
            <ListPlus size={15} /> {cuantos > 1 ? `Hacer ${cuantos} episodios` : "Hacer el episodio"}
          </button>
        </div>
      </div>
    </div>
  );
}

// El video que se ve en la tarjeta: el vertical si lo hay (es el formato de la Fabrica), si no el primero.
function principal(videos: VideoFabrica[]) {
  return videos.find((v) => v.formato === "9:16") || videos[0] || null;
}

function Reproductor({ s, onCerrar }: { s: ResumenFabrica; onCerrar: () => void }) {
  const [formato, setFormato] = useState<FormatoFabrica>(principal(s.videos)!.formato);
  const v = s.videos.find((x) => x.formato === formato)!;
  useEffect(() => {
    const tecla = (e: KeyboardEvent) => e.key === "Escape" && onCerrar();
    window.addEventListener("keydown", tecla);
    return () => window.removeEventListener("keydown", tecla);
  }, [onCerrar]);
  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-black/75 p-4" onClick={onCerrar}>
      <div className="flex max-h-[92vh] w-full max-w-3xl flex-col" onClick={(e) => e.stopPropagation()}>
        <div className="mb-3 flex items-center justify-between gap-3 text-white">
          <h3 className="truncate font-display text-lg font-semibold">{s.titulo}</h3>
          <div className="flex shrink-0 gap-2">
            {s.videos.length > 1 && s.videos.map((x) => (
              <button key={x.formato} onClick={() => setFormato(x.formato)}
                className={`boton !py-1.5 text-xs ${x.formato === formato ? "boton-acento" : "!bg-white/15 text-white hover:!bg-white/25"}`}>{x.formato}</button>
            ))}
            <a href={fabrica.urlVideo(s.id, formato, true)} className="boton boton-acento !py-1.5 text-xs"><Download size={14} /> Descargar</a>
            <Link href={`/fabrica/${s.id}`} className="boton !bg-white/15 !py-1.5 text-xs text-white hover:!bg-white/25"><SquarePen size={14} /> Editar</Link>
            <button onClick={onCerrar} className="boton !bg-white/15 !p-2 text-white hover:!bg-white/25" title="Cerrar"><X size={16} /></button>
          </div>
        </div>
        <video key={formato} src={fabrica.urlVideo(s.id, formato, false, Math.round(v.creado))} controls autoPlay
          className="max-h-[80vh] w-full rounded-xl bg-black object-contain" />
      </div>
    </div>
  );
}
