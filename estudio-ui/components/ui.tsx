"use client";

import type { EstadoEtapa } from "@/lib/api";

export const NOMBRE_ESTADO: Record<EstadoEtapa, string> = {
  ok: "Al dia",
  obsoleta: "Desactualizada",
  pendiente: "Sin generar",
  error: "Error",
  ejecutando: "Trabajando",
};

const CLASE_ESTADO: Record<EstadoEtapa, string> = {
  ok: "bg-ok-suave text-ok",
  obsoleta: "bg-aviso-suave text-aviso",
  pendiente: "bg-hundido text-tinta-3",
  error: "bg-error-suave text-error",
  ejecutando: "bg-acento-suave text-acento latido",
};

export function ChipEstado({ estado }: { estado: EstadoEtapa }) {
  return (
    <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold ${CLASE_ESTADO[estado]}`}>
      {NOMBRE_ESTADO[estado]}
    </span>
  );
}

export function Campo({ etiqueta, ayuda, children, className = "" }: {
  etiqueta: string; ayuda?: string; children: React.ReactNode; className?: string;
}) {
  return (
    <label className={`block ${className}`}>
      <span className="etiqueta">{etiqueta}</span>
      <div className="mt-1.5">{children}</div>
      {ayuda && <span className="mt-1 block text-xs text-tinta-3">{ayuda}</span>}
    </label>
  );
}

export function Tarjeta({ titulo, extra, children, className = "" }: {
  titulo?: string; extra?: React.ReactNode; children: React.ReactNode; className?: string;
}) {
  return (
    <section className={`rounded-2xl border border-linea bg-tarjeta p-5 ${className}`}>
      {(titulo || extra) && (
        <div className="mb-4 flex items-center justify-between gap-3">
          {titulo && <h3 className="font-display text-lg font-semibold">{titulo}</h3>}
          {extra}
        </div>
      )}
      {children}
    </section>
  );
}

export function Segmentado<T extends string>({ valor, opciones, onChange }: {
  valor: T; opciones: { v: T; t: string }[]; onChange: (v: T) => void;
}) {
  return (
    <div className="inline-flex flex-wrap rounded-full border border-linea bg-hundido p-1">
      {opciones.map((o) => (
        <button
          key={o.v}
          type="button"
          onClick={() => onChange(o.v)}
          className={`rounded-full px-3.5 py-1.5 text-sm font-medium transition ${
            valor === o.v ? "bg-tarjeta text-tinta shadow-sm" : "text-tinta-2 hover:text-tinta"
          }`}
        >
          {o.t}
        </button>
      ))}
    </div>
  );
}

export function Deslizador({ valor, min, max, paso, onChange, formato }: {
  valor: number; min: number; max: number; paso: number; onChange: (v: number) => void;
  formato?: (v: number) => string;
}) {
  return (
    <div className="flex items-center gap-3">
      <input type="range" className="flex-1" min={min} max={max} step={paso} value={valor}
        onChange={(e) => onChange(parseFloat(e.target.value))} />
      <span className="w-14 text-right text-sm tabular-nums text-tinta-2">{formato ? formato(valor) : valor}</span>
    </div>
  );
}

export function AvisoError({ texto }: { texto: string | null | undefined }) {
  if (!texto) return null;
  return <p className="whitespace-pre-wrap rounded-xl bg-error-suave p-3 text-sm text-error">{texto}</p>;
}

// Boton de las tarjetas de video (Mis videos, Fabrica): icono y, en pantallas anchas, texto.
export function Accion({ icono, texto, onClick, href, disabled, soloIcono, peligro, derecha }: {
  icono: React.ReactNode; texto: string; onClick?: () => void; href?: string;
  disabled?: boolean; soloIcono?: boolean; peligro?: boolean; derecha?: boolean;
}) {
  const clase = `boton boton-fantasma !gap-1.5 !px-2 !py-1.5 text-xs ${peligro ? "hover:!text-error" : ""} ${derecha ? "ml-auto" : ""}`;
  const contenido = <>{icono}{!soloIcono && <span className="hidden sm:inline">{texto}</span>}</>;
  if (disabled) return <span className={`${clase} pointer-events-none opacity-35`} title={texto}>{contenido}</span>;
  if (href) return <a href={href} className={clase} title={texto}>{contenido}</a>;
  return <button onClick={onClick} className={clase} title={texto}>{contenido}</button>;
}
