"use client";

// Galeria de estilos de la Fabrica: cada estilo con una imagen de muestra (la misma escena en todos). Las
// hace el servidor una sola vez (no dependen del motor): mientras falte alguna se vuelve a preguntar.

import { useEffect, useState } from "react";
import { Check, Loader2 } from "lucide-react";
import { fabrica, type GaleriaEstilos as Galeria } from "@/lib/api";

export default function GaleriaEstilos({ valor, onCambio, compacta = false }: {
  valor: string; onCambio: (id: string) => void; compacta?: boolean;
}) {
  const [g, setG] = useState<Galeria | null>(null);

  useEffect(() => {
    let vivo = true;
    let k: ReturnType<typeof setTimeout>;
    const cargar = () => fabrica.estilos().then((x) => {
      if (!vivo) return;
      setG(x);
      if (x.generando) k = setTimeout(cargar, 5000);
    }).catch(() => {});
    cargar();
    return () => { vivo = false; clearTimeout(k); };
  }, []);

  if (!g) return <Loader2 size={16} className="animate-spin text-tinta-3" />;
  return (
    <div>
      <div className={`grid gap-3 ${compacta ? "grid-cols-4" : "grid-cols-3 sm:grid-cols-5"}`}>
        {g.estilos.map((e) => {
          const elegido = e.id === valor;
          return (
            <button key={e.id} type="button" onClick={() => onCambio(e.id)} title={e.descripcion}
              className={`group overflow-hidden rounded-xl border text-left transition ${elegido ? "border-marca ring-2 ring-marca" : "border-linea hover:border-tinta-3"}`}>
              <div className="relative aspect-[9/16] bg-hundido">
                {e.muestra ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img src={fabrica.urlMuestra(e.id, e.muestra)} alt={e.nombre} loading="lazy" className="h-full w-full object-cover" />
                ) : (
                  <div className="flex h-full flex-col items-center justify-center gap-2 p-2 text-center text-xs text-tinta-3">
                    <Loader2 size={16} className="animate-spin" /> Preparando muestra
                  </div>
                )}
                {elegido && <span className="absolute right-1.5 top-1.5 rounded-full bg-marca p-1 text-white"><Check size={12} /></span>}
              </div>
              <p className="truncate px-1.5 py-1.5 text-xs font-semibold">{e.nombre}</p>
            </button>
          );
        })}
      </div>
      {!compacta && <p className="mt-2 text-xs text-tinta-3">{g.estilos.find((e) => e.id === valor)?.descripcion}</p>}
      {g.error && <p className="mt-2 text-xs text-error">{g.error}</p>}
    </div>
  );
}
