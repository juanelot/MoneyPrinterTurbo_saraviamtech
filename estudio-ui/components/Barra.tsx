"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import {
  Clapperboard, CopyPlus, Factory, Film, Library, Menu, ScrollText, Settings, Scissors, TrendingUp, X,
} from "lucide-react";
import { MARCA } from "@/lib/marca";

type Item = { href: string; texto: string; icono: React.ReactNode; hijos?: Item[] };

const ITEMS: Item[] = [
  { href: "/", texto: "Mis videos", icono: <Film size={17} /> },
  { href: "/maestros", texto: "Prompts maestros", icono: <ScrollText size={17} /> },
  { href: "/clips", texto: "Clip Studio", icono: <Scissors size={17} /> },
  {
    href: "/fabrica", texto: "Fabrica", icono: <Factory size={17} />, hijos: [
      { href: "/fabrica/biblioteca", texto: "Biblioteca de dibujos", icono: <Library size={15} /> },
      { href: "/fabrica/ideas", texto: "Ideas virales", icono: <TrendingUp size={15} /> },
      { href: "/fabrica/clonar", texto: "Clonar video", icono: <CopyPlus size={15} /> },
      { href: "/fabrica/banco", texto: "Banco de clips", icono: <Clapperboard size={15} /> },
    ],
  },
];

// Mis videos tambien abarca el editor de un proyecto (/p/...).
function activo(ruta: string, href: string) {
  if (href === "/") return ruta === "/" || ruta.startsWith("/p/");
  return ruta === href || ruta.startsWith(href + "/");
}

function Enlace({ item, ruta, sub }: { item: Item; ruta: string; sub?: boolean }) {
  // En la Fabrica, el padre solo se marca si no hay un hijo activo.
  const si = item.hijos
    ? activo(ruta, item.href) && !item.hijos.some((h) => activo(ruta, h.href))
    : activo(ruta, item.href);
  return (
    <Link
      href={item.href}
      className={`flex items-center gap-2.5 rounded-xl px-3 transition ${sub ? "py-1.5 text-[13px]" : "py-2 text-sm font-medium"} ${
        si ? "bg-hundido text-tinta" : "text-tinta-2 hover:bg-hundido/60 hover:text-tinta"
      }`}
    >
      <span className={si ? "text-acento" : "text-tinta-3"}>{item.icono}</span>
      <span className="truncate">{item.texto}</span>
    </Link>
  );
}

function Contenido({ ruta }: { ruta: string }) {
  return (
    <div className="flex h-full flex-col">
      <div className="bg-marca h-0.5 w-full shrink-0" />
      <Link href="/" className="flex items-center gap-2.5 px-5 py-5" aria-label={MARCA.nombre}>
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src={MARCA.logo.claro} alt={MARCA.nombre} className="h-7 w-auto dark:hidden" />
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src={MARCA.logo.oscuro} alt={MARCA.nombre} className="hidden h-7 w-auto dark:block" />
        <span className="rounded-full border border-linea px-2 py-0.5 text-[10px] font-semibold uppercase tracking-[0.14em] text-tinta-2">
          Studio
        </span>
      </Link>
      <nav className="flex-1 space-y-0.5 overflow-y-auto px-3">
        {ITEMS.map((item) => (
          <div key={item.href}>
            <Enlace item={item} ruta={ruta} />
            {item.hijos && (
              <div className="mb-1 ml-5 mt-0.5 space-y-0.5 border-l border-linea pl-2">
                {item.hijos.map((h) => <Enlace key={h.href} item={h} ruta={ruta} sub />)}
              </div>
            )}
          </div>
        ))}
      </nav>
      <div className="border-t border-linea p-3">
        <Enlace item={{ href: "/configuracion", texto: "Configuracion", icono: <Settings size={17} /> }} ruta={ruta} />
      </div>
    </div>
  );
}

export default function Barra() {
  const ruta = usePathname() || "/";
  const [abierto, setAbierto] = useState(false);

  return (
    <>
      {/* Escritorio: barra lateral fija */}
      <aside className="fixed inset-y-0 left-0 z-30 hidden w-60 border-r border-linea bg-papel md:block">
        <Contenido ruta={ruta} />
      </aside>

      {/* Movil: barra arriba con boton de menu */}
      <header className="sticky top-0 z-30 flex h-12 items-center gap-3 border-b border-linea bg-papel/85 px-3 backdrop-blur md:hidden">
        <button className="boton boton-fantasma !p-2" onClick={() => setAbierto(true)} aria-label="Abrir menu">
          <Menu size={18} />
        </button>
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src={MARCA.logo.claro} alt={MARCA.nombre} className="h-6 w-auto dark:hidden" />
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src={MARCA.logo.oscuro} alt={MARCA.nombre} className="hidden h-6 w-auto dark:block" />
      </header>
      {abierto && (
        <div className="fixed inset-0 z-40 md:hidden" onClick={() => setAbierto(false)}>
          <div className="absolute inset-0 bg-black/40" />
          <aside className="absolute inset-y-0 left-0 w-64 border-r border-linea bg-papel shadow-xl" onClick={(e) => {
            e.stopPropagation();
            if ((e.target as HTMLElement).closest("a")) setAbierto(false);
          }}>
            <button className="boton boton-fantasma absolute right-2 top-3 !p-2" onClick={() => setAbierto(false)} aria-label="Cerrar menu">
              <X size={18} />
            </button>
            <Contenido ruta={ruta} />
          </aside>
        </div>
      )}
    </>
  );
}
