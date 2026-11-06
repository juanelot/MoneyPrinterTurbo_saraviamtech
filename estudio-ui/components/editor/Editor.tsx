"use client";

// Editor (paso propio, entre Ajuste y Video), multipista: Medios + vista previa +
// inspector arriba y la linea de tiempo abajo.
//   - Pista principal y voz: lo de Ajuste (cortes, clips, inicio de cada clip).
//     Se guarda en los parametros de Ajuste y se aplica solo (sin Claude).
//   - Capas, textos, audios, musica y donde va cada pista (principal, voz y
//     subtitulos por tramos, cada una por su lado): parametros del render
//     (render.capas, principal_desde, voz_tramos, subs_tramos, musica_*). Se ven
//     al momento y se montan tal cual.

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  AudioLines, Combine, Copy, Film, Link2, Mic, Sparkles, Image as ImagenIcono, Loader2, Magnet, Maximize2, Music2, Pin, PinOff, Redo2, Scissors,
  Search, Trash2, Type, Undo2, Upload, Wand2, ZoomIn, ZoomOut,
} from "lucide-react";
import type { PanelProps } from "../Proyecto";
import { Segmentado } from "../ui";
import {
  api, listarMusica, mini, mmss, url, type AjusteClip, type AudioProyecto, type DatosEditor, type Plano, type Recurso,
} from "@/lib/api";
import { FormGrafico, IdeasGraficos } from "./Graficos";
import LineaTiempo, { TIPO_ARRASTRE, TIPO_AUDIO, type Soltado } from "./LineaTiempo";
import Reproductor, { type Seleccion } from "./Reproductor";
import { crearReloj, useTiempo, type Reloj } from "./reloj";
import {
  NOMBRE_AJUSTE, PLANO_MIN_S, ajusteClip, ajustePorDefecto, cambiarClip, carrilLibre, inicioClip, intercambiar, moverClip, moverCorte,
  colocacion, finTramos, frasesConTexto, nombreClip, ponerParche, nuevoId, partir, partirCapa, partirTramo, planoEn, quitar, unir,
  type Capa, type Colocacion, type Edicion, type Estado, type Extras, type Parche, type PistaTramos,
} from "./modelo";

const APLICAR_TRAS_MS = 1200;
const PX_MIN = 1, PX_MAX = 400;

interface Todo { base: Estado; capas: Capa[]; extras: Extras }

export default function Editor({ id, vista, p, set, ejecutar, ocupado, elegirClip }: PanelProps & {
  elegirClip: (plano: Plano, alElegir: (r: Recurso | null) => void) => void;
}) {
  const et = vista.etapas.asignacion;
  const a = p("asignacion");
  const r = p("render");
  const recursos = useMemo(() => vista.etapas.recursos.salida?.recursos || [], [vista.etapas.recursos.salida]);
  const porId = useMemo(() => new Map(recursos.map((x) => [x.id, x])), [recursos]);
  const modoEscenas = a.modo === "escenas";
  const modoDef = ajustePorDefecto(modoEscenas && Array.isArray(p("escenas").fijas), r.voz_continua !== false);

  const [datos, setDatos] = useState<DatosEditor | null>(null);
  const [error, setError] = useState("");
  const reloj = useMemo<Reloj>(() => crearReloj(), []);
  const [base, setBase] = useState<Estado | null>(null);
  const [capas, setCapas] = useState<Capa[]>(() => ((r.capas as Capa[]) || []).filter((c) => c && c.id));
  const [extras, setExtras] = useState<Extras>(() => extrasDe(r));
  const [historia, setHistoria] = useState<Todo[]>([]);
  const [futuro, setFuturo] = useState<Todo[]>([]);
  const [sel, setSel] = useState<Seleccion | null>(null);
  const [nuevoGrafico, setNuevoGrafico] = useState(false);
  const [modoGrafico, setModoGrafico] = useState<"mano" | "ideas">("mano");
  const [px, setPx] = useState(0);
  const [iman, setIman] = useState(true);
  // Mover juntas la principal, la voz y los subtitulos (como antes) o cada una por su lado.
  const [juntas, setJuntasEstado] = useState(() => { try { return localStorage.getItem("editor-juntas") === "1"; } catch { return false; } });
  const setJuntas = (v: boolean) => { setJuntasEstado(v); try { localStorage.setItem("editor-juntas", v ? "1" : "0"); } catch { /* sin almacenamiento */ } };
  // `cambios` cuenta las ediciones de Ajuste; `lanzado` es la ultima que ya se mando a aplicar.
  const [cambios, setCambios] = useState(0);
  const [lanzado, setLanzado] = useState(0);
  const sucio = cambios > 0 && lanzado < cambios;
  const esperando = cambios > 0;
  const temporizador = useRef<ReturnType<typeof setTimeout> | null>(null);

  const vozHecha = vista.etapas.voz.terminado;
  useEffect(() => {
    api.editor(id).then(setDatos).catch((e) => setError(String(e.message)));
  }, [id, vozHecha]);

  // Lo que devuelve el servidor manda, en cuanto termina de aplicar TODOS los cambios.
  const salida = et.salida?.planos;
  const listo = !ocupado && et.estado === "ok";
  useEffect(() => {
    if (!salida || (esperando && (sucio || !listo))) return;
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setBase({ planos: salida, ed: edicionDe(a) });
    setCambios(0);
    setLanzado(0);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [salida, esperando, sucio, listo]);

  const D = datos?.duracion || (base?.planos.length ? base.planos[base.planos.length - 1].fin : 0);
  const sinVoz = !!datos?.sin_voz;
  // Se puede regrabar una parte con TTS (no con una grabacion propia).
  const vozElegida = String(p("voz").voz ?? "es-ES-AlvaroNeural-Male");
  const regrabable = !sinVoz && !vozElegida.startsWith("propia:") && vozElegida !== "ninguna";
  const col = useMemo(() => colocacion(extras, D, sinVoz), [extras, D, sinVoz]);
  const total = Math.max(col.P + D, finTramos(col.voz), finTramos(col.subs), ...capas.map((c) => c.fin), 0.1);
  const pxAjustado = useCallback(() => Math.max(PX_MIN, Math.min(PX_MAX, 1500 / Math.max(1, total))), [total]);
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    if (D && !px) setPx(Math.max(10, pxAjustado()));
  }, [D, px, pxAjustado]);

  const aplicar = useCallback(() => {
    if (temporizador.current) clearTimeout(temporizador.current);
    temporizador.current = null;
    const hasta = cambios;
    // Se marca como lanzado cuando el servidor ya tiene el trabajo (o ya lo termino):
    // antes, la asignacion vieja seguiria "al dia" y el editor volveria atras.
    ejecutar("asignacion").finally(() => setLanzado(hasta));
  }, [ejecutar, cambios]);

  useEffect(() => {
    if (!sucio || ocupado) return;
    temporizador.current = setTimeout(aplicar, APLICAR_TRAS_MS);
    return () => { if (temporizador.current) clearTimeout(temporizador.current); };
  }, [sucio, ocupado, base, aplicar]);

  // Los cortes valen para ESTA voz: se guardan con su duracion (si la voz cambia, el servidor los ignora).
  const duracionVoz = useRef(0);
  useEffect(() => { duracionVoz.current = datos?.duracion || 0; }, [datos]);

  const guardarBase = useCallback((ed: Edicion, antes: Edicion) => {
    if (JSON.stringify(ed.limites) !== JSON.stringify(antes.limites)) {
      set("asignacion", "limites", ed.limites);
      set("asignacion", "limites_voz", ed.limites ? duracionVoz.current : null);
    }
    const distinto = (x: unknown, y: unknown) => JSON.stringify(x) !== JSON.stringify(y);
    if (distinto(ed.fijados, antes.fijados)) set("asignacion", "fijados", ed.fijados);
    if (distinto(ed.inicio_clip, antes.inicio_clip)) set("asignacion", "inicio_clip", ed.inicio_clip);
    if (distinto(ed.ajuste, antes.ajuste)) set("asignacion", "ajuste", ed.ajuste);
  }, [set]);

  /** Pasa a un estado nuevo (de cualquiera de las tres partes) y lo guarda. */
  const pasarA = useCallback((nuevo: Todo, antes: Todo) => {
    if (nuevo.base !== antes.base) {
      // Solo cuenta como cambio de Ajuste si cambio lo que se guarda (no la copia del servidor).
      if (JSON.stringify(nuevo.base.ed) !== JSON.stringify(antes.base.ed)) {
        guardarBase(nuevo.base.ed, antes.base.ed);
        setCambios((c) => c + 1);
      }
      setBase(nuevo.base);
    }
    if (nuevo.capas !== antes.capas) {
      set("render", "capas", nuevo.capas);
      setCapas(nuevo.capas);
    }
    if (nuevo.extras !== antes.extras) {
      for (const k of Object.keys(nuevo.extras) as (keyof Extras)[]) {
        if (nuevo.extras[k] !== antes.extras[k]) set("render", k, nuevo.extras[k]);
      }
      setExtras(nuevo.extras);
    }
  }, [guardarBase, set]);

  const actual = useMemo<Todo | null>(() => (base ? { base, capas, extras } : null), [base, capas, extras]);
  const cambiarTodo = useCallback((parcial: Partial<Todo>) => {
    if (!actual) return;
    const nuevo = { ...actual, ...parcial };
    setHistoria((h) => [...h.slice(-99), actual]);
    setFuturo([]);
    pasarA(nuevo, actual);
  }, [actual, pasarA]);
  const cambiar = useCallback((b: Estado | null) => { if (b) cambiarTodo({ base: b }); }, [cambiarTodo]);
  const capasVivas = useRef(capas);
  useEffect(() => { capasVivas.current = capas; }, [capas]);
  const cambiarCapas = useCallback((c: Capa[] | null) => { if (c) cambiarTodo({ capas: c }); }, [cambiarTodo]);
  const cambiarExtras = useCallback((e: Partial<Extras>) => cambiarTodo({ extras: { ...extras, ...e } }), [cambiarTodo, extras]);
  // Se guardan las tres siempre: desde aqui ya no dependen de voz_retraso.
  const cambiarCol = useCallback((c: Colocacion) =>
    cambiarExtras({ principal_desde: c.P, voz_tramos: c.voz, subs_tramos: c.subs }), [cambiarExtras]);
  const quitarTramo = useCallback((pista: PistaTramos, k: number) =>
    cambiarCol({ ...col, [pista]: col[pista].filter((_, n) => n !== k) }), [cambiarCol, col]);

  const deshacer = useCallback(() => {
    if (!historia.length || !actual) return;
    const previo = historia[historia.length - 1];
    setHistoria((h) => h.slice(0, -1));
    setFuturo((f) => [...f, actual]);
    pasarA(previo, actual);
  }, [historia, actual, pasarA]);
  const rehacer = useCallback(() => {
    if (!futuro.length || !actual) return;
    const sig = futuro[futuro.length - 1];
    setFuturo((f) => f.slice(0, -1));
    setHistoria((h) => [...h, actual]);
    pasarA(sig, actual);
  }, [futuro, actual, pasarA]);

  const palabras = useMemo(() => datos?.palabras || [], [datos]);
  const capaSel = sel?.tipo === "capa" ? capas.find((c) => c.id === sel.id) || null : null;

  const dividir = useCallback(() => {
    if (!base) return;
    if (capaSel) {
      cambiarCapas(partirCapa(capas, capaSel.id, reloj.t));
      return;
    }
    if (sel?.tipo === "voz" || sel?.tipo === "subs") {
      const p = partirTramo(col[sel.tipo], reloj.t);
      if (p) {
        cambiarCol({ ...col, [sel.tipo]: p.tramos });
        setSel({ tipo: sel.tipo, k: p.k });
      }
      return;
    }
    const tv = reloj.t - col.P;
    const i = planoEn(base.planos, tv);
    const nuevo = partir(base, i, tv, palabras);
    if (!nuevo) return;
    cambiar(nuevo);
    setSel({ tipo: "plano", i: i + 1 });
  }, [base, capaSel, capas, reloj, sel, col, palabras, cambiar, cambiarCapas, cambiarCol]);

  const borrar = useCallback(() => {
    if (!base || !sel) return;
    if (sel.tipo === "capa") {
      cambiarCapas(capas.filter((c) => c.id !== sel.id));
      setSel(null);
    } else if (sel.tipo === "plano") {
      cambiar(quitar(base, sel.i));
      setSel({ tipo: "plano", i: Math.max(0, sel.i - 1) });
    } else if (sel.tipo === "musica") {
      set("render", "musica", "");
    } else if (sel.tipo === "subs" && sel.n != null) {
      cambiarExtras({ subs_texto: { ...extras.subs_texto, [String(sel.n)]: "" } }); // quitar solo esa frase
    } else if ((sel.tipo === "voz" && !sinVoz) || sel.tipo === "subs") {
      quitarTramo(sel.tipo, sel.k);
      setSel(null);
    }
  }, [base, sel, capas, cambiar, cambiarCapas, set, sinVoz, quitarTramo, cambiarExtras, extras.subs_texto]);

  const duplicar = useCallback(() => {
    if (!capaSel) return;
    const d = capaSel.fin - capaSel.inicio;
    const c = { ...capaSel, id: nuevoId(), inicio: capaSel.fin, fin: capaSel.fin + d };
    c.carril = carrilLibre(capas, c.tipo, c.inicio, c.fin, capaSel.carril);
    cambiarCapas([...capas, c]);
    setSel({ tipo: "capa", id: c.id });
  }, [capaSel, capas, cambiarCapas]);

  const anadirTexto = useCallback(() => {
    const a0 = reloj.t, b0 = Math.min(a0 + 3, Math.max(total, a0 + 3));
    const c: Capa = { id: nuevoId(), tipo: "texto", carril: carrilLibre(capas, "texto", a0, b0), inicio: a0, fin: b0,
      texto: "Tu texto", tam: 96, color: "#FFFFFF", fondo: true, x: 0.5, y: 0.22 };
    cambiarCapas([...capas, c]);
    setSel({ tipo: "capa", id: c.id });
  }, [reloj, total, capas, cambiarCapas]);

  const soltar = useCallback((s: Soltado) => {
    let c: Capa;
    if (s.tipo === "video" && s.recurso) {
      const rec = porId.get(s.recurso);
      const dur = rec?.tipo === "video" ? Math.min(rec.duracion || 5, 8) : 3;
      c = { id: nuevoId(), tipo: "video", recurso: s.recurso, carril: 0, inicio: s.t, fin: s.t + dur, modo: "completa",
        volumen: rec?.tipo === "video" ? 1 : 0, offset: 0, x: 0.75, y: 0.28, escala: 0.4 };
    } else if (s.tipo === "audio" && s.archivo) {
      const dur = s.dur ? Math.min(s.dur, 15) : 10;
      c = { id: nuevoId(), tipo: "audio", archivo: s.archivo, carril: 0, inicio: s.t, fin: s.t + dur, volumen: 1, offset: 0 };
    } else return;
    c.carril = carrilLibre(capas, c.tipo, c.inicio, c.fin, s.carril);
    cambiarCapas([...capas, c]);
    setSel({ tipo: "capa", id: c.id });
  }, [porId, capas, cambiarCapas]);

  const ponerRecurso = useCallback((i: number, rid: string) => {
    const rec = porId.get(rid);
    if (base && rec) cambiar(cambiarClip(base, i, rec));
    setSel({ tipo: "plano", i });
  }, [base, porId, cambiar]);

  // Atajos de teclado (no mientras se escribe en un campo).
  useEffect(() => {
    const tecla = (e: KeyboardEvent) => {
      const el = e.target as HTMLElement;
      if (el.closest("input:not([type=range]):not([type=checkbox]), textarea, select, [contenteditable]")) return;
      const k = e.key.toLowerCase();
      const ctrl = e.ctrlKey || e.metaKey;
      if (e.key === " ") {
        e.preventDefault();
        if (reloj.sonando) reloj.parar(); else reloj.tocar();
      } else if (ctrl && (k === "y" || (k === "z" && e.shiftKey))) {
        e.preventDefault();
        rehacer();
      } else if (ctrl && k === "z") {
        e.preventDefault();
        deshacer();
      } else if (ctrl && k === "d") {
        e.preventDefault();
        duplicar();
      } else if ((k === "s" || k === "b") && !ctrl) {
        dividir();
      } else if (k === "t" && !ctrl) {
        anadirTexto();
      } else if (e.key === "Delete" || e.key === "Backspace") {
        e.preventDefault();
        borrar();
      } else if ((e.key === "ArrowRight" || e.key === "ArrowLeft") && base) {
        e.preventDefault();
        if (e.shiftKey) {
          reloj.ir(reloj.t + (e.key === "ArrowRight" ? 1 / 30 : -1 / 30));
          return;
        }
        const R = col.P;
        const i = planoEn(base.planos, reloj.t - R) + (e.key === "ArrowRight" ? 1 : -1);
        const x = base.planos[Math.max(0, Math.min(base.planos.length - 1, i))];
        reloj.ir(x.inicio + R);
        setSel({ tipo: "plano", i: x.i });
      } else if (k === "+" || k === "=") {
        setPx((v) => Math.min(PX_MAX, v * 1.25));
      } else if (k === "-") {
        setPx((v) => Math.max(PX_MIN, v * 0.8));
      }
    };
    window.addEventListener("keydown", tecla);
    return () => window.removeEventListener("keydown", tecla);
  }, [reloj, deshacer, rehacer, dividir, borrar, duplicar, anadirTexto, base, col.P]);

  useEffect(() => () => reloj.parar(), [reloj]);

  if (error) return <p className="rounded-xl bg-error-suave p-3 text-sm text-error">No se pudo abrir el editor: {error}</p>;
  if (!base || !datos) {
    return <div className="grid place-items-center rounded-2xl border border-linea bg-tarjeta py-24 text-tinta-3"><Loader2 className="animate-spin" /></div>;
  }

  const planos = base.planos;
  const selPlano = sel?.tipo === "plano" ? planos[sel.i] : null;
  const cancion = (r.musica as string) ?? "random";
  const usos = new Map<string, number>();
  planos.forEach((x) => x.recurso && usos.set(x.recurso, (usos.get(x.recurso) || 0) + 1));
  capas.forEach((c) => c.recurso && usos.set(c.recurso, (usos.get(c.recurso) || 0) + 1));
  const zoomLog = Math.log(px || 10);

  return (
    <div className="space-y-3">
      <div className="grid gap-3 xl:grid-cols-[290px_minmax(0,1fr)_380px]">
        <Medios recursos={recursos} usos={usos} id={id} puedePoner={!!selPlano}
          onPoner={(rid) => selPlano && ponerRecurso(selPlano.i, rid)} />
        <div className="order-first rounded-2xl border border-linea bg-tarjeta p-4 xl:order-none">
          <Reproductor id={id} reloj={reloj} total={total} planos={planos} porId={porId} datos={datos} r={r} modoDef={modoDef}
            capas={capas} extras={extras} col={col} sel={sel} alSeleccionar={setSel}
            alCambiarCapa={(cid, cambio) => cambiarCapas(capas.map((x) => (x.id === cid ? { ...x, ...cambio } : x)))}
            alSubtitulos={(pct) => { set("render", "sub_posicion", "custom"); set("render", "sub_posicion_pct", pct); }} />
        </div>
        <div className="max-h-[72vh] overflow-y-auto rounded-2xl border border-linea bg-tarjeta p-4">
          {nuevoGrafico && !sel ? (
            <div className="space-y-3">
              <Segmentado valor={modoGrafico} onChange={(v) => setModoGrafico(v as "mano" | "ideas")}
                opciones={[{ v: "mano", t: "Uno a mano" }, { v: "ideas", t: "Ideas de Claude" }]} />
              {modoGrafico === "ideas" ? (
                <IdeasGraficos id={id} onIr={(t) => reloj.ir(t)}
                  onPoner={(puestos) => {
                    // Las capas de ahora mismo (mientras se creaban se pudo editar otra cosa).
                    let nuevas = [...capasVivas.current];
                    for (const x of puestos) {
                      const a0 = x.inicio, b0 = a0 + x.hecho.duracion;
                      nuevas = [...nuevas, { id: nuevoId(), tipo: "video", carril: carrilLibre(nuevas, "video", a0, b0), inicio: a0, fin: b0,
                        modo: "completa", archivo: x.hecho.archivo, grafico: x.datos, volumen: 0, offset: 0 }];
                    }
                    cambiarCapas(nuevas);
                  }} />
              ) : (<>
              <p className="etiqueta">Nuevo grafico animado · en el {reloj.t.toFixed(1)} s</p>
              <FormGrafico id={id} boton="Crear y poner en el cabezal" onCancelar={() => setNuevoGrafico(false)}
                onListo={(hecho, grafico) => {
                  const a0 = reloj.t, b0 = a0 + hecho.duracion;
                  const c: Capa = { id: nuevoId(), tipo: "video", carril: carrilLibre(capas, "video", a0, b0), inicio: a0, fin: b0,
                    modo: "completa", archivo: hecho.archivo, grafico, volumen: 0, offset: 0 };
                  cambiarCapas([...capas, c]);
                  setNuevoGrafico(false);
                  setSel({ tipo: "capa", id: c.id });
                }} />
              </>)}
            </div>
          ) : selPlano ? (
            <Inspector key={`p${selPlano.i}`} plano={selPlano} estado={base} rec={selPlano.recurso ? porId.get(selPlano.recurso) : undefined}
              reloj={reloj} R={col.P} modoDef={modoDef} conVoz={!datos.sin_voz} r={r}
              onCambiar={cambiar} palabras={palabras} setSel={(i) => setSel({ tipo: "plano", i })}
              retoque={<Retocar key={`r${selPlano.i}-${selPlano.inicio}`} id={id} desde={selPlano.inicio} hasta={selPlano.fin} texto={selPlano.texto}
                regrabable={regrabable} parche={extras.voz_parches.find((y) => y.desde < selPlano.fin && selPlano.inicio < y.hasta) || null}
                onPoner={(x) => cambiarExtras({
                  voz_parches: ponerParche(extras.voz_parches, x),
                  subs_texto: { ...extras.subs_texto, ...frasesConTexto(datos.lineas || [], x.desde, x.hasta, x.texto) },
                })}
                onQuitar={(x) => {
                  const st = { ...extras.subs_texto };
                  Object.keys(frasesConTexto(datos.lineas || [], x.desde, x.hasta, "")).forEach((k) => delete st[k]);
                  cambiarExtras({ voz_parches: extras.voz_parches.filter((y) => y !== x), subs_texto: st });
                }} />}
              onSonido={(modo) => {
                const actualS = { ...((r.sonido_clips as Record<string, string>) || {}) };
                const n = nombreClip(selPlano.nombre);
                if (modo) actualS[n] = modo; else delete actualS[n];
                set("render", "sonido_clips", actualS);
              }}
              onElegir={() => elegirClip(selPlano, (rec) => cambiar(cambiarClip(base, selPlano.i, rec, salida?.[selPlano.i])))} />
          ) : capaSel ? (
            <InspectorCapa key={capaSel.id} id={id} c={capaSel} rec={capaSel.recurso ? porId.get(capaSel.recurso) : undefined}
              onCambiar={(cambio) => cambiarCapas(capas.map((x) => (x.id === capaSel.id ? { ...x, ...cambio } : x)))}
              onBorrar={borrar} onDuplicar={duplicar} />
          ) : sel?.tipo === "musica" ? (
            <InspectorMusica r={r} extras={extras} total={total} set={set} onExtras={cambiarExtras} />
          ) : sel?.tipo === "voz" || sel?.tipo === "subs" ? (
            <InspectorPista pista={sel.tipo} k={sel.k} col={col} D={D} sinVoz={sinVoz} onCol={cambiarCol}
              frase={sel.tipo === "subs" ? sel.n : undefined} lineas={datos.lineas || []} cambios={extras.subs_texto}
              onFrase={(n) => setSel({ tipo: "subs", k: sel.k, n })}
              onTexto={(n, texto) => {
                const st = { ...extras.subs_texto };
                if (texto == null) delete st[String(n)]; else st[String(n)] = texto;
                cambiarExtras({ subs_texto: st });
              }}
              onQuitar={() => { quitarTramo(sel.tipo, sel.k); setSel(null); }} />
          ) : (
            <Ayuda />
          )}
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-1.5 rounded-xl border border-linea bg-tarjeta px-3 py-2">
        <Herramienta titulo="Dividir en el cabezal (S): el plano o la capa elegida" onClick={dividir}><Scissors size={15} /> Dividir</Herramienta>
        <Herramienta titulo="Borrar lo elegido (Supr). Un plano principal pasa su tramo al anterior." onClick={borrar} desactivada={!sel}>
          <Trash2 size={15} /> Borrar
        </Herramienta>
        <Herramienta titulo="Duplicar la capa elegida (Ctrl+D)" onClick={duplicar} desactivada={!capaSel}><Copy size={15} /></Herramienta>
        <Herramienta titulo="Anadir un texto en el cabezal (T)" onClick={anadirTexto}><Type size={15} /> Texto</Herramienta>
        <Herramienta titulo="Graficos animados: uno a mano en el cabezal, o ideas de Claude para todo el video" onClick={() => { setSel(null); setNuevoGrafico(true); }}
          activa={nuevoGrafico && !sel}><Wand2 size={15} /> Grafico</Herramienta>
        <span className="mx-1 h-5 w-px bg-linea" />
        <Herramienta titulo="Deshacer (Ctrl+Z)" onClick={deshacer} desactivada={!historia.length}><Undo2 size={15} /></Herramienta>
        <Herramienta titulo="Rehacer (Ctrl+Y)" onClick={rehacer} desactivada={!futuro.length}><Redo2 size={15} /></Herramienta>
        <span className="mx-1 h-5 w-px bg-linea" />
        <Herramienta titulo={juntas ? "Principal, voz y subtitulos se mueven juntos" : "Principal, voz y subtitulos se mueven cada uno por su lado"}
          onClick={() => setJuntas(!juntas)} activa={juntas}>
          <Link2 size={15} /> Juntas
        </Herramienta>
        <Herramienta titulo={iman ? "Iman activado: pega a bordes, cabezal y huecos entre palabras" : "Iman apagado"}
          onClick={() => setIman((v) => !v)} activa={iman}>
          <Magnet size={15} /> Iman
        </Herramienta>
        <span className="ml-2 text-xs text-tinta-3">
          {planos.length} planos · {capas.length} capas · {mmss(total)}
          {esperando ? " · aplicando cambios…" : et.estado === "ok" ? " · todo aplicado" : ""}
        </span>
        <div className="ml-auto flex items-center gap-2">
          <button className="boton boton-fantasma !p-1.5" title="Alejar (-)" onClick={() => setPx(Math.max(PX_MIN, px * 0.8))}><ZoomOut size={15} /></button>
          <input type="range" className="w-40 accent-[var(--acento)]" min={Math.log(PX_MIN)} max={Math.log(PX_MAX)} step={0.01} value={zoomLog}
            onChange={(e) => setPx(Math.exp(Number(e.target.value)))} title="Zoom de la linea de tiempo (Ctrl + rueda)" />
          <button className="boton boton-fantasma !p-1.5" title="Acercar (+)" onClick={() => setPx(Math.min(PX_MAX, px * 1.25))}><ZoomIn size={15} /></button>
          <button className="boton boton-fantasma !p-1.5" title="Ver todo el video" onClick={() => setPx(pxAjustado())}><Maximize2 size={15} /></button>
        </div>
      </div>

      <LineaTiempo planos={planos} porId={porId} datos={datos} reloj={reloj} total={total} px={px || 20} setPx={setPx}
        sel={sel} alSeleccionar={setSel} cancion={cancion} iman={iman}
        alMoverCorte={(k, t) => cambiar(moverCorte(base, k, t, palabras))}
        alIntercambiar={(i, j) => { cambiar(intercambiar(base, i, j)); setSel({ tipo: "plano", i: j }); }}
        alReordenar={(i, hueco) => {
          const m = moverClip(base, i, hueco);
          if (m) { cambiar(m.estado); setSel({ tipo: "plano", i: m.destino }); }
        }}
        alSoltarRecurso={ponerRecurso} alSoltar={soltar}
        capas={capas} alCambiarCapas={cambiarCapas} extras={extras} alCambiarExtras={cambiarExtras}
        col={col} alCambiarCol={cambiarCol} juntas={juntas} />
    </div>
  );
}

function edicionDe(a: Record<string, unknown>): Edicion {
  return {
    limites: (a.limites as number[]) || null,
    fijados: (a.fijados as Record<string, string>) || {},
    inicio_clip: (a.inicio_clip as Record<string, number>) || {},
    ajuste: (a.ajuste as Record<string, AjusteClip>) || {},
  };
}

function extrasDe(r: Record<string, unknown>): Extras {
  return {
    voz_retraso: Number(r.voz_retraso || 0),
    principal_desde: r.principal_desde == null ? null : Number(r.principal_desde),
    voz_tramos: Array.isArray(r.voz_tramos) ? (r.voz_tramos as Extras["voz_tramos"]) : null,
    subs_tramos: Array.isArray(r.subs_tramos) ? (r.subs_tramos as Extras["subs_tramos"]) : null,
    subs_texto: r.subs_texto && typeof r.subs_texto === "object" ? (r.subs_texto as Record<string, string>) : {},
    voz_parches: Array.isArray(r.voz_parches) ? (r.voz_parches as Parche[]) : [],
    musica_desde: Number(r.musica_desde || 0),
    musica_hasta: r.musica_hasta == null ? null : Number(r.musica_hasta),
    musica_offset: Number(r.musica_offset || 0),
  };
}

function Herramienta({ titulo, onClick, desactivada, activa, children }: {
  titulo: string; onClick: () => void; desactivada?: boolean; activa?: boolean; children: React.ReactNode;
}) {
  return (
    <button title={titulo} disabled={desactivada} onClick={onClick}
      className={`boton !gap-1.5 !px-2.5 !py-1.5 text-sm ${activa ? "bg-acento-suave text-acento" : "boton-fantasma"}`}>
      {children}
    </button>
  );
}

function Ayuda() {
  return (
    <div className="space-y-3 text-sm text-tinta-2">
      <p className="font-display text-lg font-semibold text-tinta">Como se usa</p>
      <p>Pulsa cualquier bloque de la linea de tiempo (plano, capa, texto, audio, voz o musica) para ver sus ajustes aqui.</p>
      <ul className="space-y-1.5 text-xs text-tinta-3">
        <li><b>Arrastra un archivo</b> de Medios a una pista <b>Capa</b> para ponerlo encima (pantalla completa o ventana), a la <b>Principal</b> para cambiar ese clip, o un audio a una pista <b>Audio</b>.</li>
        <li><b>Arrastra un bloque</b> para moverlo (tambien a otra pista del mismo tipo) y <b>sus bordes</b> para recortarlo.</li>
        <li><b>Arrastra un clip</b> de la principal entre dos planos para moverlo alli (los demas se corren) o al centro de otro para intercambiarlos; los cortes siguen a la voz.</li>
        <li><b>Clic en una frase</b> de los subtitulos para corregir su texto o quitarla.</li>
        <li><b>Principal, voz y subtitulos</b> se mueven cada uno por su lado (la principal, desde su asa ⋮ a la izquierda). La voz y los subtitulos se parten con <b>S</b> y cada trozo se mueve, se recorta o se borra solo. Con <b>Juntas</b> se mueven las tres a la vez.</li>
        <li>Lo que pongas despues del final alarga el video.</li>
        <li><b>Espacio</b> reproducir · <b>S</b> dividir · <b>T</b> texto · <b>Supr</b> borrar · <b>Ctrl+D</b> duplicar</li>
        <li><b>Ctrl+Z</b> deshacer · <b>Ctrl+Y</b> rehacer · <b>Shift + ← →</b> fotograma a fotograma</li>
        <li><b>+ / −</b> o <b>Ctrl + rueda</b>: zoom</li>
      </ul>
    </div>
  );
}

function Medios({ recursos, usos, id, puedePoner, onPoner }: {
  recursos: Recurso[]; usos: Map<string, number>; id: string; puedePoner: boolean; onPoner: (rid: string) => void;
}) {
  const [filtro, setFiltro] = useState("");
  const [tipo, setTipo] = useState<"todo" | "video" | "imagen" | "audio">("todo");
  const [viendo, setViendo] = useState<string | null>(null);
  const [audios, setAudios] = useState<AudioProyecto[]>([]);
  const [canciones, setCanciones] = useState<string[]>([]);
  const subida = useRef<HTMLInputElement>(null);
  useEffect(() => {
    api.audios(id).then((x) => setAudios(x.audios)).catch(() => {});
    listarMusica().then(setCanciones);
  }, [id]);
  async function subir(archivos: FileList | null) {
    if (!archivos?.length) return;
    await api.subirAudios(id, [...archivos]);
    setAudios((await api.audios(id)).audios);
  }
  const f = filtro.toLowerCase();
  const lista = recursos.filter((r) => (tipo === "todo" || r.tipo === tipo)
    && (!f || r.nombre.toLowerCase().includes(f) || (r.descripcion || "").toLowerCase().includes(f)));
  return (
    <div className="flex max-h-[72vh] flex-col rounded-2xl border border-linea bg-tarjeta p-3">
      <div className="mb-2 flex items-center justify-between">
        <span className="font-display font-semibold">Medios</span>
        <span className="text-xs text-tinta-3">{recursos.length + audios.length}</span>
      </div>
      <div className="relative mb-2">
        <Search size={13} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-tinta-3" />
        <input className="campo !py-1.5 !pl-7 text-sm" placeholder="Buscar…" value={filtro} onChange={(e) => setFiltro(e.target.value)} />
      </div>
      <div className="mb-2">
        <Segmentado valor={tipo} onChange={setTipo}
          opciones={[{ v: "todo", t: "Todo" }, { v: "video", t: "Video" }, { v: "imagen", t: "Foto" }, { v: "audio", t: "Audio" }]} />
      </div>
      {tipo === "audio" ? (
        <div className="flex-1 space-y-3 overflow-y-auto pr-1">
          <button className="boton boton-linea w-full !py-1.5 text-sm" onClick={() => subida.current?.click()}><Upload size={14} /> Subir audios</button>
          <input ref={subida} type="file" accept="audio/*" multiple hidden onChange={(e) => subir(e.target.files)} />
          <ListaAudios titulo="Del proyecto" items={audios.filter((x) => !f || x.nombre.toLowerCase().includes(f)).map((x) => ({ archivo: x.archivo, nombre: x.nombre, dur: x.duracion }))} />
          <ListaAudios titulo="Canciones" items={canciones.filter((c) => !f || c.toLowerCase().includes(f)).map((c) => ({ archivo: `cancion:${c}`, nombre: c, dur: 0 }))} />
          <p className="text-xs text-tinta-3">Arrastra un audio a una pista <b>Audio</b> de la linea de tiempo.</p>
        </div>
      ) : (
        <ul className="grid flex-1 grid-cols-2 content-start gap-2 overflow-y-auto pr-1">
          {lista.map((r) => (
            <li key={r.id}>
              <div draggable
                onDragStart={(e) => { e.dataTransfer.setData(TIPO_ARRASTRE, r.id); e.dataTransfer.effectAllowed = "copy"; }}
                onDoubleClick={() => puedePoner && onPoner(r.id)}
                onMouseEnter={() => r.tipo === "video" && setViendo(r.id)} onMouseLeave={() => setViendo(null)}
                title={`${r.nombre}${r.descripcion ? `\n${r.descripcion}` : ""}\nArrastralo a una pista Capa (encima) o a la Principal (cambia ese clip)`}
                className="group relative aspect-video cursor-grab overflow-hidden rounded-lg border border-linea bg-hundido hover:border-acento">
                {viendo === r.id ? (
                  <video src={url.original(id, r.id)} muted autoPlay loop playsInline className="h-full w-full object-cover" />
                ) : (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img src={url.miniatura(mini(r))} alt="" draggable={false} className="h-full w-full object-cover" />
                )}
                <span className="absolute left-1 top-1 rounded bg-black/60 p-0.5 text-white">
                  {r.tipo === "video" ? <Film size={10} /> : <ImagenIcono size={10} />}
                </span>
                {r.tipo === "video" && <span className="absolute bottom-1 right-1 rounded bg-black/60 px-1 text-[10px] text-white tabular-nums">{r.duracion.toFixed(1)}s</span>}
                {usos.get(r.id) ? <span className="absolute right-1 top-1 rounded bg-acento px-1 text-[10px] font-semibold text-sobre-acento">×{usos.get(r.id)}</span> : null}
              </div>
              <p className="mt-0.5 truncate text-[11px] text-tinta-3" title={r.nombre}>{r.nombre.split("/").pop()}</p>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function ListaAudios({ titulo, items }: { titulo: string; items: { archivo: string; nombre: string; dur: number }[] }) {
  return (
    <div>
      <p className="etiqueta mb-1">{titulo} ({items.length})</p>
      <ul className="space-y-1">
        {items.map((x) => (
          <li key={x.archivo} draggable
            onDragStart={(e) => { e.dataTransfer.setData(TIPO_AUDIO, `${x.archivo}|${x.dur}`); e.dataTransfer.effectAllowed = "copy"; }}
            className="flex cursor-grab items-center gap-2 rounded-lg border border-linea px-2 py-1.5 text-xs hover:border-acento" title={x.nombre}>
            {x.archivo.startsWith("cancion:") ? <Music2 size={12} className="shrink-0 text-ok" /> : <AudioLines size={12} className="shrink-0 text-ok" />}
            <span className="min-w-0 flex-1 truncate">{x.nombre}</span>
            {x.dur > 0 && <span className="tabular-nums text-tinta-3">{mmss(x.dur)}</span>}
          </li>
        ))}
      </ul>
    </div>
  );
}

function Deslizador({ etiqueta, valor, min, max, paso, formato, onChange, onSoltar }: {
  etiqueta: string; valor: number; min: number; max: number; paso: number; formato?: (v: number) => string;
  onChange: (v: number) => void; onSoltar?: () => void;
}) {
  return (
    <div>
      <div className="flex items-center justify-between">
        <span className="etiqueta">{etiqueta}</span>
        <span className="text-xs tabular-nums text-tinta-2">{formato ? formato(valor) : valor.toFixed(2)}</span>
      </div>
      <input type="range" className="mt-1 w-full accent-[var(--acento)]" min={min} max={max} step={paso} value={valor}
        onChange={(e) => onChange(Number(e.target.value))}
        onPointerUp={(e) => { onSoltar?.(); e.currentTarget.blur(); }} onKeyUp={() => onSoltar?.()} />
    </div>
  );
}

const pct = (v: number) => `${Math.round(v * 100)}%`;

/** Ajustes de una capa. Los deslizadores muestran el valor en vivo y guardan al soltar (un paso de deshacer). */
function InspectorCapa({ id, c, rec, onCambiar, onBorrar, onDuplicar }: {
  id: string; c: Capa; rec?: Recurso; onCambiar: (cambio: Partial<Capa>) => void; onBorrar: () => void; onDuplicar: () => void;
}) {
  // Lo que se esta moviendo (aun sin guardar) encima de la capa guardada.
  const [vivo, setVivo] = useState<Partial<Capa>>({});
  const v: Capa = { ...c, ...vivo };
  const cambiarVivo = (k: keyof Capa, x: unknown) => setVivo((p) => ({ ...p, [k]: x }));
  const guardar = (k: keyof Capa) => () => {
    if (!(k in vivo)) return;
    onCambiar({ [k]: vivo[k] });
    setVivo((p) => { const n = { ...p }; delete n[k]; return n; });
  };
  const titulo = c.grafico ? "Grafico animado" : c.tipo === "video" ? (rec?.tipo === "imagen" ? "Foto encima" : "Video encima") : c.tipo === "texto" ? "Texto" : "Audio";
  return (
    <div className="space-y-4">
      <div className="flex items-start justify-between gap-2">
        <div>
          <p className="etiqueta">{titulo} · pista {c.carril}</p>
          <p className="text-xs tabular-nums text-tinta-3">{c.inicio.toFixed(2)} → {c.fin.toFixed(2)} s · {(c.fin - c.inicio).toFixed(1)} s</p>
        </div>
        <div className="flex gap-1">
          <button className="boton boton-fantasma !p-1.5" title="Duplicar (Ctrl+D)" onClick={onDuplicar}><Copy size={14} /></button>
          <button className="boton boton-fantasma !p-1.5 text-error" title="Borrar (Supr)" onClick={onBorrar}><Trash2 size={14} /></button>
        </div>
      </div>

      {c.grafico && (
        <div className="space-y-2 rounded-xl border border-linea p-3">
          <FormGrafico key={c.archivo} id={id} inicial={c.grafico} duracion={c.fin - c.inicio} boton="Volver a generar"
            onListo={(hecho, grafico) => onCambiar({ archivo: hecho.archivo, grafico, fin: c.inicio + hecho.duracion })} />
          <p className="text-xs text-tinta-3">Si cambias el largo del bloque, «Volver a generar» lo rehace con esa duracion.</p>
        </div>
      )}
      {c.tipo === "video" && (
        <>
          {rec && (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={url.miniatura(mini(rec))} alt="" className="h-24 w-full rounded-lg object-cover" />
          )}
          <Segmentado valor={c.modo || "completa"} onChange={(m) => onCambiar({ modo: m })}
            opciones={[{ v: "completa", t: "Pantalla completa" }, { v: "ventana", t: "Ventana" }]} />
          {c.modo === "ventana" && (
            <>
              <Deslizador etiqueta="Tamano" valor={v.escala ?? 0.4} min={0.1} max={1} paso={0.01} formato={pct}
                onChange={(x) => cambiarVivo("escala", x)} onSoltar={guardar("escala")} />
              <Deslizador etiqueta="Posicion horizontal" valor={v.x ?? 0.5} min={0} max={1} paso={0.01} formato={pct}
                onChange={(x) => cambiarVivo("x", x)} onSoltar={guardar("x")} />
              <Deslizador etiqueta="Posicion vertical" valor={v.y ?? 0.5} min={0} max={1} paso={0.01} formato={pct}
                onChange={(x) => cambiarVivo("y", x)} onSoltar={guardar("y")} />
            </>
          )}
          {rec?.tipo === "video" && (
            <>
              <Deslizador etiqueta="Empieza en el segundo del clip" valor={v.offset ?? 0} min={0} max={Math.max(0, (rec.duracion || 0) - 0.1)} paso={0.1}
                formato={(x) => `${x.toFixed(1)} s`} onChange={(x) => cambiarVivo("offset", x)} onSoltar={guardar("offset")} />
              <Deslizador etiqueta="Volumen del clip" valor={v.volumen ?? 0} min={0} max={2} paso={0.05} formato={pct}
                onChange={(x) => cambiarVivo("volumen", x)} onSoltar={guardar("volumen")} />
            </>
          )}
        </>
      )}

      {c.tipo === "texto" && (
        <>
          <textarea className="campo min-h-[70px]" value={v.texto || ""} onChange={(e) => cambiarVivo("texto", e.target.value)}
            onBlur={guardar("texto")} placeholder="Escribe el texto" />
          <Deslizador etiqueta="Tamano" valor={v.tam ?? 96} min={30} max={260} paso={2} formato={(x) => `${x}`}
            onChange={(x) => cambiarVivo("tam", x)} onSoltar={guardar("tam")} />
          <Deslizador etiqueta="Posicion horizontal" valor={v.x ?? 0.5} min={0} max={1} paso={0.01} formato={pct}
            onChange={(x) => cambiarVivo("x", x)} onSoltar={guardar("x")} />
          <Deslizador etiqueta="Posicion vertical" valor={v.y ?? 0.5} min={0} max={1} paso={0.01} formato={pct}
            onChange={(x) => cambiarVivo("y", x)} onSoltar={guardar("y")} />
          <div className="flex items-center gap-3">
            <label className="flex items-center gap-2 text-sm">
              Color
              <input type="color" className="h-8 w-12 cursor-pointer rounded border border-linea bg-tarjeta" value={c.color || "#FFFFFF"}
                onChange={(e) => onCambiar({ color: e.target.value })} />
            </label>
            <label className="flex items-center gap-2 text-sm">
              <input type="checkbox" checked={c.fondo !== false} onChange={(e) => onCambiar({ fondo: e.target.checked })} /> Caja oscura
            </label>
          </div>
        </>
      )}

      {c.tipo === "audio" && (
        <>
          <p className="truncate text-sm" title={c.archivo}>{(c.archivo || "").replace(/^cancion:|^audios\//, "")}</p>
          <Deslizador etiqueta="Volumen" valor={v.volumen ?? 1} min={0} max={2} paso={0.05} formato={pct}
            onChange={(x) => cambiarVivo("volumen", x)} onSoltar={guardar("volumen")} />
          <Deslizador etiqueta="Empieza en el segundo del audio" valor={v.offset ?? 0} min={0} max={600} paso={0.1}
            formato={(x) => `${x.toFixed(1)} s`} onChange={(x) => cambiarVivo("offset", x)} onSoltar={guardar("offset")} />
        </>
      )}
      <p className="text-xs text-tinta-3">Mueve el bloque en la linea de tiempo para cambiar cuando sale y arrastra sus bordes para recortarlo.</p>
    </div>
  );
}

function InspectorMusica({ r, extras, total, set, onExtras }: {
  r: Record<string, unknown>; extras: Extras; total: number;
  set: PanelProps["set"]; onExtras: (e: Partial<Extras>) => void;
}) {
  const [canciones, setCanciones] = useState<string[]>([]);
  useEffect(() => { listarMusica().then(setCanciones); }, []);
  const [vol, setVol] = useState(Number(r.musica_volumen ?? 0.2));
  const [off, setOff] = useState(extras.musica_offset);
  return (
    <div className="space-y-4">
      <p className="etiqueta">Musica de fondo</p>
      <select className="campo" value={(r.musica as string) ?? "random"} onChange={(e) => set("render", "musica", e.target.value)}>
        <option value="random">Aleatoria</option>
        <option value="">Sin musica</option>
        {canciones.map((c) => <option key={c} value={c}>{c}</option>)}
      </select>
      <Deslizador etiqueta="Volumen" valor={vol} min={0} max={1} paso={0.05} formato={pct}
        onChange={setVol} onSoltar={() => set("render", "musica_volumen", vol)} />
      <Deslizador etiqueta="Entra por el segundo de la cancion" valor={off} min={0} max={300} paso={0.5}
        formato={(x) => `${x.toFixed(1)} s`} onChange={setOff} onSoltar={() => onExtras({ musica_offset: off })} />
      <p className="text-xs tabular-nums text-tinta-2">
        Suena de {extras.musica_desde.toFixed(1)} s a {(extras.musica_hasta ?? total).toFixed(1)} s del video.
      </p>
      <button className="boton boton-linea !py-1.5 text-sm" onClick={() => onExtras({ musica_desde: 0, musica_hasta: null, musica_offset: 0 })}>
        Todo el video
      </button>
      <p className="text-xs text-tinta-3">Arrastra el bloque verde para moverla y sus bordes para recortarla.</p>
    </div>
  );
}

function InspectorPista({ pista, k, col, D, sinVoz, onCol, onQuitar, frase, lineas, cambios, onFrase, onTexto }: {
  pista: PistaTramos; k: number; col: Colocacion; D: number; sinVoz: boolean;
  onCol: (c: Colocacion) => void; onQuitar: () => void;
  frase?: number; lineas: [number, number, string][]; cambios: Record<string, string>;
  onFrase: (n: number) => void; onTexto: (n: number, texto: string | null) => void;
}) {
  const ts = col[pista];
  const x = ts[k];
  const nombre = pista === "voz" ? "Voz" : "Subtitulos";
  const fija = pista === "voz" && sinVoz;
  if (!x) return <p className="text-sm text-tinta-3">{nombre}: ese trozo ya no existe.</p>;
  const dur = x.hasta - x.desde;
  const entera = { desde: 0, hasta: D, en: Math.max(0, x.en - x.desde) };
  return (
    <div className="space-y-3 text-sm">
      {pista === "subs" && frase != null && lineas[frase] && (
        <Frase key={frase} n={frase} total={lineas.length} linea={lineas[frase]} cambio={cambios[String(frase)]}
          onTexto={(t) => onTexto(frase, t)} onIr={onFrase} />
      )}
      <div className="flex items-start justify-between gap-2">
        <p className="etiqueta">{nombre}{ts.length > 1 ? ` · trozo ${k + 1} de ${ts.length}` : ""}</p>
        {!fija && (
          <button className="boton boton-fantasma !p-1.5 text-error" title="Quitar este trozo (Supr)" onClick={onQuitar}><Trash2 size={14} /></button>
        )}
      </div>
      <p>Del segundo <b className="tabular-nums">{x.desde.toFixed(2)}</b> al <b className="tabular-nums">{x.hasta.toFixed(2)}</b> de la voz
        ({dur.toFixed(1)} s); sale en el <b className="tabular-nums">{x.en.toFixed(2)}</b> del video.</p>
      {fija ? (
        <p className="text-xs text-tinta-3">Sin voz propia: lo que suena es el sonido de los clips y va con la pista principal.</p>
      ) : (
        <p className="text-xs text-tinta-3">Arrastra el bloque para moverlo y sus bordes para recortarlo. <b>S</b> lo parte en el cabezal: cada trozo se mueve por su lado (para dejar una pausa, una intro o quitar una parte).</p>
      )}
      <div className="flex flex-wrap gap-1.5">
        {x.en > 0 && !fija && (
          <button className="boton boton-linea !py-1.5 text-sm" onClick={() => onCol({ ...col, [pista]: ts.map((y, n) => (n === k ? { ...y, en: 0 } : y)) })}>Al segundo 0</button>
        )}
        {pista === "subs" && (
          <button className="boton boton-linea !py-1.5 text-sm" title="Los subtitulos quedan como la voz"
            onClick={() => onCol({ ...col, subs: col.voz.map((y) => ({ ...y })) })}>Igual que la voz</button>
        )}
        {(ts.length > 1 || x.desde > 0 || x.hasta < D) && !fija && (
          <button className="boton boton-linea !py-1.5 text-sm" title="Vuelve a ser un solo bloque entero" onClick={() => onCol({ ...col, [pista]: [entera] })}>Entera otra vez</button>
        )}
        <button className="boton boton-linea !py-1.5 text-sm" title="La principal, la voz y los subtitulos vuelven a empezar a la vez, enteros"
          onClick={() => onCol({ P: entera.en, voz: [{ ...entera }], subs: [{ ...entera }] })}>Alinear las tres</button>
      </div>
    </div>
  );
}

/** Corregir una frase de los subtitulos: el texto cambia, sus tiempos no (van con la voz). */
function Frase({ n, total, linea, cambio, onTexto, onIr }: {
  n: number; total: number; linea: [number, number, string]; cambio?: string;
  onTexto: (texto: string | null) => void; onIr: (n: number) => void;
}) {
  const [a, b, original] = linea;
  const [texto, setTexto] = useState(cambio ?? original);
  const guardar = () => {
    const limpio = texto.split(/\s+/).filter(Boolean).join(" ");
    if (limpio === (cambio ?? original)) return;
    onTexto(limpio === original ? null : limpio);
  };
  const quitada = cambio != null && !cambio.trim();
  return (
    <div className="space-y-2 rounded-xl border border-acento/40 bg-acento-suave/30 p-3">
      <div className="flex items-center justify-between gap-2">
        <p className="etiqueta">Frase {n + 1} de {total} · {a.toFixed(1)}–{b.toFixed(1)} s de la voz</p>
        <div className="flex gap-1">
          <button className="boton boton-fantasma !px-2 !py-0.5" disabled={n === 0} title="Frase anterior" onClick={() => { guardar(); onIr(n - 1); }}>‹</button>
          <button className="boton boton-fantasma !px-2 !py-0.5" disabled={n >= total - 1} title="Frase siguiente" onClick={() => { guardar(); onIr(n + 1); }}>›</button>
        </div>
      </div>
      {quitada ? (
        <p className="text-xs text-tinta-3">Quitada: no sale en el video. <span className="line-through">{original}</span></p>
      ) : (
        <textarea className="campo min-h-[64px]" value={texto} onChange={(e) => setTexto(e.target.value)} onBlur={guardar}
          onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); e.currentTarget.blur(); } }} />
      )}
      <div className="flex flex-wrap gap-1.5">
        {!quitada && <button className="boton boton-linea !px-2.5 !py-1 text-xs" onClick={() => onTexto("")}><Trash2 size={12} /> Quitar esta frase</button>}
        {cambio != null && <button className="boton boton-linea !px-2.5 !py-1 text-xs" onClick={() => onTexto(null)}>Volver al original</button>}
      </div>
      {cambio != null && !quitada && <p className="text-xs text-tinta-3">Original: {original}</p>}
      <p className="text-xs text-tinta-3">Enter guarda. Las palabras se reparten dentro de la frase; el tiempo sigue al de la voz.</p>
    </div>
  );
}

/** Cambiar lo que dice un plano: Claude propone textos que caben en su hueco (o se escribe uno)
 *  y se regraba solo esa parte con la voz del proyecto. Nada mas se mueve. */
function Retocar({ id, desde, hasta, texto, regrabable, parche, onPoner, onQuitar }: {
  id: string; desde: number; hasta: number; texto: string; regrabable: boolean; parche: Parche | null;
  onPoner: (x: Parche) => void; onQuitar: (x: Parche) => void;
}) {
  const [abierto, setAbierto] = useState(false);
  const [nuevo, setNuevo] = useState(parche?.texto ?? texto);
  const [pedido, setPedido] = useState("");
  const [opciones, setOpciones] = useState<string[]>([]);
  const [ocupado, setOcupado] = useState<"" | "ideas" | "grabar">("");
  const [aviso, setAviso] = useState("");
  const caben = Math.max(1, Math.round((hasta - desde) * 2.5));
  if (!regrabable) {
    return <p className="text-xs text-tinta-3">Con una narracion propia no se puede regrabar una parte (cambia la voz a una de Microsoft).</p>;
  }
  async function ideas() {
    setOcupado("ideas"); setAviso("");
    try {
      const r = await api.reescribirParte(id, { desde, hasta, texto: parche?.texto ?? texto, pedido });
      setOpciones(r.opciones);
    } catch (e) { setAviso(String((e as Error).message)); } finally { setOcupado(""); }
  }
  async function grabar() {
    setOcupado("grabar"); setAviso("");
    try {
      const r = await api.grabarParte(id, { desde, hasta, texto: nuevo });
      if (!r.cabe) setAviso(`Es demasiado largo para este hueco (${(hasta - desde).toFixed(1)} s): quita unas ${r.sobran} palabras.`);
      else { onPoner({ desde: r.desde, hasta: r.hasta, archivo: r.archivo, texto: r.texto }); setAbierto(false); }
    } catch (e) { setAviso(String((e as Error).message)); } finally { setOcupado(""); }
  }
  return (
    <div className="space-y-2 border-t border-linea pt-3">
      <div className="flex items-center justify-between gap-2">
        <span className="etiqueta">Lo que dice</span>
        {!abierto && <button className="boton boton-linea !px-2.5 !py-1 text-xs" onClick={() => setAbierto(true)}><Mic size={12} /> Cambiar lo que dice</button>}
      </div>
      {parche && (
        <div className="rounded-lg bg-aviso/15 p-2 text-xs">
          <p><b>Regrabado:</b> «{parche.texto}»</p>
          <button className="mt-1 text-acento underline" onClick={() => onQuitar(parche)}>Volver a la voz original</button>
        </div>
      )}
      {abierto && (
        <div className="space-y-2">
          <textarea className="campo min-h-[64px] text-sm" value={nuevo} onChange={(e) => setNuevo(e.target.value)} />
          <p className="text-xs text-tinta-3">Caben unas {caben} palabras ({(hasta - desde).toFixed(1)} s). Lo demas del video no se mueve.</p>
          <div className="flex gap-1.5">
            <input className="campo !py-1 text-xs" placeholder="Pedido a Claude (opcional): mas gancho, mas corto…" value={pedido}
              onChange={(e) => setPedido(e.target.value)} />
            <button className="boton boton-linea shrink-0 !px-2.5 !py-1 text-xs" disabled={!!ocupado} onClick={ideas}>
              {ocupado === "ideas" ? <Loader2 size={12} className="animate-spin" /> : <Sparkles size={12} />} Ideas
            </button>
          </div>
          {opciones.length > 0 && (
            <ul className="space-y-1">
              {opciones.map((o) => (
                <li key={o}>
                  <button data-idea className={`w-full rounded-lg border px-2 py-1.5 text-left text-xs hover:border-acento ${o === nuevo ? "border-acento bg-acento-suave" : "border-linea"}`}
                    onClick={() => setNuevo(o)}>{o}</button>
                </li>
              ))}
            </ul>
          )}
          {aviso && <p className="rounded-lg bg-error-suave p-2 text-xs text-error">{aviso}</p>}
          <div className="flex gap-1.5">
            <button className="boton boton-acento !px-3 !py-1.5 text-xs" disabled={!!ocupado || !nuevo.trim()} onClick={grabar}>
              {ocupado === "grabar" ? <Loader2 size={12} className="animate-spin" /> : <Mic size={12} />} Grabar y poner
            </button>
            <button className="boton boton-fantasma !px-3 !py-1.5 text-xs" onClick={() => setAbierto(false)}>Cancelar</button>
          </div>
        </div>
      )}
    </div>
  );
}

function Inspector({ plano: x, estado, rec, reloj, R, modoDef, conVoz, r, palabras, onCambiar, onElegir, onSonido, setSel, retoque }: {
  retoque: React.ReactNode;
  plano: Plano; estado: Estado; rec?: Recurso; reloj: Reloj; R: number; modoDef: AjusteClip; conVoz: boolean;
  r: Record<string, unknown>; palabras: [number, number, string][];
  onCambiar: (e: Estado | null) => void; onElegir: () => void; onSonido: (modo: string | null) => void;
  setSel: (i: number) => void;
}) {
  const t = useTiempo(reloj) - R;
  const dur = x.fin - x.inicio;
  const esVideo = x.tipo === "video";
  const dr = x.dur_recurso || rec?.duracion || 0;
  const [inicio, setInicio] = useState(x.offset || 0);
  const corto = esVideo && dr > 0 && inicio + dur > dr + 0.05;
  const dentro = t > x.inicio + PLANO_MIN_S && t < x.fin - PLANO_MIN_S;
  const sonidos = (r.sonido_clips as Record<string, string>) || {};
  const sonido = sonidos[nombreClip(x.nombre)];

  return (
    <div className="space-y-4">
      <div className="flex items-start justify-between gap-2">
        <div>
          <p className="etiqueta">{x.escena ? `Escena ${x.escena}` : `Plano ${x.i + 1}`} de {estado.planos.length}</p>
          <p className="text-xs tabular-nums text-tinta-3">{mmss(x.inicio + R)} → {mmss(x.fin + R)} · {dur.toFixed(1)} s</p>
        </div>
        {x.fijado && <span className="inline-flex items-center gap-1 rounded-full bg-acento-suave px-2 py-0.5 text-xs text-acento"><Pin size={10} /> fijado</span>}
      </div>
      <p className="max-h-24 overflow-y-auto text-sm">{x.texto || <span className="text-tinta-3">(sin texto)</span>}</p>
      {conVoz && retoque}

      <div className="flex gap-3">
        <button onClick={onElegir} className="relative h-20 w-32 shrink-0 overflow-hidden rounded-lg bg-hundido" title="Cambiar clip">
          {rec && (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={url.miniatura(mini(rec))} alt="" className="h-full w-full object-cover" />
          )}
        </button>
        <div className="min-w-0 flex-1 space-y-1.5">
          <p className="truncate text-xs text-tinta-2" title={rec?.nombre}>{rec?.nombre}{esVideo && dr ? ` · ${dr.toFixed(1)} s` : ""}</p>
          <div className="flex flex-wrap gap-1.5">
            <button className="boton boton-linea !px-2.5 !py-1 text-xs" onClick={onElegir}>Cambiar clip</button>
            {x.fijado && (
              <button className="boton boton-fantasma !px-2.5 !py-1 text-xs" onClick={() => onCambiar(cambiarClip(estado, x.i, null))}>
                <PinOff size={12} /> Soltar
              </button>
            )}
          </div>
        </div>
      </div>

      {esVideo && dr > 0 && (
        <Deslizador etiqueta={`Empieza en el segundo${x.inicio_elegido ? "" : " (automatico)"}`} valor={inicio} min={0} max={Math.max(0, dr - 0.1)} paso={0.1}
          formato={(v) => `${v.toFixed(1)} s`} onChange={setInicio} onSoltar={() => onCambiar(inicioClip(estado, x.i, inicio))} />
      )}
      {esVideo && x.inicio_elegido && (
        <button className="text-xs text-acento underline" onClick={() => onCambiar(inicioClip(estado, x.i, null))}>Volver a automatico</button>
      )}

      {corto && (
        <div>
          <span className="etiqueta">El clip es mas corto que el plano</span>
          <div className="mt-1.5">
            <Segmentado valor={x.ajuste || modoDef} onChange={(v) => onCambiar(ajusteClip(estado, x.i, v))}
              opciones={(["repetir", "congelar", "lento"] as AjusteClip[]).map((v) => ({ v, t: NOMBRE_AJUSTE[v] + (v === modoDef && !x.ajuste ? " ·" : "") }))} />
          </div>
          <p className="mt-1 text-xs text-tinta-3">Repetir vuelve a empezar el clip; Congelar deja su ultimo fotograma; Mas lento lo estira hasta un 25 % y congela lo que falte.</p>
        </div>
      )}

      {esVideo && conVoz && (
        <div>
          <span className="etiqueta">Sonido de este clip bajo la voz</span>
          <div className="mt-1.5">
            <Segmentado valor={sonido || "defecto"} onChange={(v) => onSonido(v === "defecto" ? null : v)}
              opciones={[{ v: "defecto", t: "Por defecto" }, { v: "completo", t: "Completo" }, { v: "solo_fuerte", t: "Solo fuertes" }, { v: "silencio", t: "Silencio" }]} />
          </div>
        </div>
      )}

      <div className="flex flex-wrap gap-1.5 border-t border-linea pt-3">
        <button className="boton boton-linea !px-2.5 !py-1 text-xs" disabled={!dentro}
          title={dentro ? "Dividir este plano donde esta el cabezal (S)" : "Pon el cabezal dentro del plano"}
          onClick={() => { onCambiar(partir(estado, x.i, t, palabras)); setSel(x.i + 1); }}>
          <Scissors size={12} /> Dividir aqui
        </button>
        <button className="boton boton-linea !px-2.5 !py-1 text-xs" disabled={x.i === 0}
          onClick={() => { onCambiar(unir(estado, x.i - 1)); setSel(x.i - 1); }}>
          <Combine size={12} /> Unir con el anterior
        </button>
        <button className="boton boton-linea !px-2.5 !py-1 text-xs" disabled={x.i >= estado.planos.length - 1}
          onClick={() => onCambiar(unir(estado, x.i))}>
          <Combine size={12} /> Unir con el siguiente
        </button>
      </div>
    </div>
  );
}
