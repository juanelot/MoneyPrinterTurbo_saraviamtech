"use client";

import { useMemo, useState } from "react";
import { Mic, Upload } from "lucide-react";
import type { PanelProps } from "../Proyecto";
import { AvisoError, Campo, Deslizador, Segmentado, Tarjeta } from "../ui";
import { AZURE_VOICES } from "@/lib/voces";
import { mmss, url, vozPropia } from "@/lib/api";

export default function PanelVoz({ id, vista, p, set, ejecutar, ocupado, recargar }: PanelProps) {
  const et = vista.etapas.voz;
  const v = p("voz");
  const voz = (v.voz as string) || "es-ES-AlvaroNeural-Male";
  const [idioma, setIdioma] = useState(() => voz.split("-").slice(0, 2).join("-"));
  const idiomas = useMemo(() => Array.from(new Set(AZURE_VOICES.map((x) => x.lang))).sort(), []);
  const voces = AZURE_VOICES.filter((x) => x.lang === idioma);
  const [tipo, setTipo] = useState<"microsoft" | "propia">(voz.startsWith("propia:") ? "propia" : "microsoft");
  // Escenas de duracion fija (proyecto creado desde un prompt maestro): permiten quitar la voz.
  const fijas = (p("escenas").fijas as { duracion_s?: number }[] | undefined) || [];
  const sinVoz = () => {
    set("voz", "tramos", fijas.map((f) => Number(f.duracion_s) || 8));
    set("voz", "voz", "ninguna");
  };

  if (voz === "ninguna") {
    const tramos = (v.tramos as number[]) || [];
    return (
      <div className="grid gap-5 lg:grid-cols-[1fr_1.3fr]">
        <Tarjeta titulo="Sin voz">
          <p className="text-sm text-tinta-2">
            Este video no lleva narracion: suena el audio de los propios clips (ASMR, efectos o dialogos generados en Flow),
            con {tramos.length} escenas de duracion fija ({mmss(tramos.reduce((a, b) => a + b, 0))} en total).
          </p>
          <p className="mt-2 text-xs text-tinta-3">
            Si los clips hablan, al montar Whisper los transcribe: se recorta el silencio al inicio y al final de cada
            clip y funcionan los subtitulos y los estilos editorial e intenso.
          </p>
          <div className="mt-4 flex flex-wrap gap-2">
            <button className="boton boton-acento" disabled={ocupado} onClick={() => ejecutar("voz")}>
              {et.salida ? "Rehacer la pista" : "Preparar la pista"}
            </button>
            <button className="boton boton-linea" disabled={ocupado}
              title="Escribe antes el guion en el paso Guion"
              onClick={() => set("voz", "voz", "es-MX-JorgeNeural-Male")}>
              <Mic size={15} /> Prefiero narrarlo
            </button>
          </div>
          <p className="mt-2 text-xs text-tinta-3">Para narrarlo, escribe el guion en el paso Guion y luego elige aqui una voz.</p>
        </Tarjeta>
        <AvisoError texto={et.error} />
      </div>
    );
  }

  return (
    <div className="grid gap-5 lg:grid-cols-[1fr_1.3fr]">
      <Tarjeta titulo="Voz">
        <div className="space-y-4">
          <Segmentado
            valor={tipo}
            opciones={[{ v: "microsoft", t: "Microsoft" }, { v: "propia", t: "Mi audio" },
              ...(fijas.length ? [{ v: "ninguna" as const, t: "Sin voz" }] : [])]}
            onChange={(t) => {
              if (t === "ninguna") return sinVoz();
              setTipo(t);
              if (t === "microsoft" && !voz.startsWith("es-") && voz.includes(":")) set("voz", "voz", "es-ES-AlvaroNeural-Male");
            }}
          />
          {tipo === "microsoft" ? (
            <>
              <div className="grid grid-cols-2 gap-3">
                <Campo etiqueta="Idioma">
                  <select className="campo" value={idioma} onChange={(e) => setIdioma(e.target.value)}>
                    {idiomas.map((l) => <option key={l} value={l}>{l}</option>)}
                  </select>
                </Campo>
                <Campo etiqueta="Locutor">
                  <select className="campo" value={voz} onChange={(e) => set("voz", "voz", e.target.value)}>
                    {!voces.some((x) => x.value === voz) && <option value={voz}>{voz}</option>}
                    {voces.map((x) => (
                      <option key={x.value} value={x.value}>
                        {x.value.split("-")[2].replace("Neural", "")} · {x.gender === "Female" ? "mujer" : "hombre"}
                      </option>
                    ))}
                  </select>
                </Campo>
              </div>
            </>
          ) : (
            <AudioPropio id={id} voz={voz} nombre={(v.propia_nombre as string) || ""} ocupado={ocupado}
              subido={async () => { await recargar(); await ejecutar("voz"); }} />
          )}
          {tipo === "propia" && (
            <Campo etiqueta="Quitar silencios largos">
              <Segmentado valor={String(Number(v.quitar_silencios) || 0)} onChange={(x) => set("voz", "quitar_silencios", Number(x) || null)}
                opciones={[{ v: "0", t: "No" }, { v: "1", t: "Pausas de 1 s" }, { v: "0.6", t: "0,6 s" }, { v: "0.35", t: "0,35 s (rapido)" }]} />
              <p className="mt-1.5 text-xs text-tinta-3">
                Las pausas mas largas que eso se acortan antes de sincronizar (el video queda mas agil). Pulsa «Volver a sincronizar» para aplicarlo.
              </p>
            </Campo>
          )}
          {tipo !== "propia" && (
            <Campo etiqueta="Velocidad">
              <Deslizador valor={Number(v.velocidad) || 1} min={0.7} max={1.5} paso={0.05}
                onChange={(x) => set("voz", "velocidad", x)} formato={(x) => `${x.toFixed(2)}×`} />
            </Campo>
          )}
          <div className="border-t border-linea pt-4">
            <p className="etiqueta mb-2">Planos</p>
            <p className="mb-3 text-xs text-tinta-3">
              La narracion se corta en planos por sus pausas; cada plano lleva un recurso.
            </p>
            <Campo etiqueta="Duracion minima de un plano">
              <Deslizador valor={Number(v.plano_min_s) || 2.5} min={1} max={8} paso={0.5}
                onChange={(x) => set("voz", "plano_min_s", x)} formato={(x) => `${x}s`} />
            </Campo>
            <Campo etiqueta="Duracion maxima de un plano" className="mt-3">
              <Deslizador valor={Number(v.plano_max_s) || 6} min={2} max={15} paso={0.5}
                onChange={(x) => set("voz", "plano_max_s", x)} formato={(x) => `${x}s`} />
            </Campo>
          </div>
          <button className="boton boton-linea" disabled={ocupado} onClick={() => ejecutar("voz")}>
            {voz.startsWith("propia:")
              ? (et.salida ? "Volver a sincronizar" : "Sincronizar audio")
              : (et.salida ? "Volver a sintetizar" : "Sintetizar voz")}
          </button>
        </div>
      </Tarjeta>

      <div className="space-y-4">
        <AvisoError texto={et.error} />
        {et.salida ? (
          <>
            <Tarjeta titulo="Escuchar" extra={<span className="text-sm text-tinta-3">{mmss(et.salida.duracion)}</span>}>
              <audio controls className="w-full" src={url.archivo(id, et.salida.audio, et.terminado)} />
              {et.salida.texto_de && (
                <p className="mt-3 text-xs text-tinta-3">
                  {et.salida.texto_de === "guion"
                    ? `Subtitulos con el texto del guion (${Math.round((et.salida.coincidencia || 0) * 100)}% de las palabras se oyen igual) y los tiempos de tu audio.`
                    : "Subtitulos con lo que entendio Whisper (no habia guion o no coincidia con el audio)."}
                </p>
              )}
            </Tarjeta>
            <Tarjeta titulo={`${et.salida.planos.length} planos`}>
              <ol className="max-h-[420px] space-y-1.5 overflow-auto pr-1">
                {et.salida.planos.map((x) => (
                  <li key={x.i} className="flex gap-3 rounded-lg px-2 py-1.5 text-sm hover:bg-hundido">
                    <span className="w-20 shrink-0 tabular-nums text-xs text-tinta-3">
                      {mmss(x.inicio)} · {(x.fin - x.inicio).toFixed(1)}s
                    </span>
                    <span>{x.texto}</span>
                  </li>
                ))}
              </ol>
            </Tarjeta>
          </>
        ) : (
          <Tarjeta><p className="text-tinta-2">Elige la voz y sintetiza para escucharla y ver los planos.</p></Tarjeta>
        )}
      </div>
    </div>
  );
}

function AudioPropio({ id, voz, nombre, ocupado, subido }: {
  id: string; voz: string; nombre: string; ocupado: boolean; subido: () => Promise<void>;
}) {
  const [subiendo, setSubiendo] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const tiene = voz.startsWith("propia:");

  async function subir(f: File | undefined) {
    if (!f) return;
    setSubiendo(true);
    setError(null);
    try {
      await vozPropia(id, f);
      await subido();
    } catch (e) {
      setError(String((e as Error).message || e));
    } finally {
      setSubiendo(false);
    }
  }

  return (
    <div className="space-y-3">
      <AvisoError texto={error} />
      <p className="text-xs text-tinta-3">
        Sube la narracion ya grabada (tu voz, o la que hiciste con Clonar-voz). Whisper saca el tiempo de cada palabra
        para los subtitulos y los planos. Si el guion coincide con lo que se oye, los subtitulos usan el texto del guion.
      </p>
      {tiene && (
        <>
          <p className="text-sm text-tinta-2">Audio actual: <b>{nombre || voz.slice(7)}</b></p>
          <audio controls className="w-full" src={url.archivo(id, `voz_propia/${voz.slice(7)}`)} />
        </>
      )}
      <label className={`boton boton-linea cursor-pointer !py-1.5 text-sm ${subiendo || ocupado ? "pointer-events-none opacity-60" : ""}`}>
        <Upload size={14} /> {subiendo ? "Subiendo…" : tiene ? "Cambiar audio" : "Subir audio"}
        <input type="file" accept="audio/*,.wav,.mp3,.m4a,.ogg,.opus,.flac,.webm" className="hidden"
          onChange={(e) => { subir(e.target.files?.[0]); e.target.value = ""; }} />
      </label>
      <p className="text-xs text-tinta-3">Al subirlo se sincroniza solo (unos 8 s por minuto de audio).</p>
    </div>
  );
}
