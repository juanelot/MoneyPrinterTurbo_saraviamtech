"use client";

import { useState } from "react";
import { ChevronLeft, ChevronRight } from "lucide-react";

/** Parte una lista en paginas (Mis videos, Fabrica, Clip Studio). Si la lista se achica, no se queda en una pagina vacia. */
export function usePaginas<T>(lista: T[] | null | undefined, porPagina = 12) {
  const [pagina, setPagina] = useState(1);
  const total = Math.max(1, Math.ceil((lista?.length || 0) / porPagina));
  const actual = Math.min(pagina, total);
  return {
    pagina: actual, total, setPagina, cuantos: lista?.length || 0,
    items: (lista || []).slice((actual - 1) * porPagina, actual * porPagina),
  };
}

/** Botones de pagina: anterior, numeros (con … si son muchas) y siguiente. Nada si cabe en una. */
export default function Paginacion({ pagina, total, cuantos, setPagina }: {
  pagina: number; total: number; cuantos: number; setPagina: (n: number) => void;
}) {
  if (total <= 1) return null;
  const ir = (n: number) => {
    setPagina(Math.min(total, Math.max(1, n)));
    window.scrollTo({ top: 0, behavior: "smooth" });
  };
  const numeros: (number | "…")[] = [];
  for (let n = 1; n <= total; n++) {
    if (n === 1 || n === total || Math.abs(n - pagina) <= 1) numeros.push(n);
    else if (numeros[numeros.length - 1] !== "…") numeros.push("…");
  }
  return (
    <nav className="mt-6 flex flex-wrap items-center justify-center gap-1 text-sm" aria-label="Paginas">
      <button className="boton boton-fantasma !px-2 !py-1.5" disabled={pagina === 1} onClick={() => ir(pagina - 1)} title="Anterior">
        <ChevronLeft size={16} />
      </button>
      {numeros.map((n, i) => n === "…" ? (
        <span key={`p${i}`} className="px-1.5 text-tinta-3">…</span>
      ) : (
        <button key={n} onClick={() => ir(n)} aria-current={n === pagina ? "page" : undefined}
          className={`boton !min-w-9 !px-2.5 !py-1.5 ${n === pagina ? "boton-acento justify-center" : "boton-fantasma"}`}>
          {n}
        </button>
      ))}
      <button className="boton boton-fantasma !px-2 !py-1.5" disabled={pagina === total} onClick={() => ir(pagina + 1)} title="Siguiente">
        <ChevronRight size={16} />
      </button>
      <span className="ml-2 text-xs text-tinta-3">{cuantos} en total</span>
    </nav>
  );
}
