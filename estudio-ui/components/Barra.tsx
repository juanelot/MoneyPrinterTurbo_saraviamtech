import Link from "next/link";
import { MARCA } from "@/lib/marca";

export default function Barra() {
  return (
    <header className="sticky top-0 z-30 border-b border-linea bg-papel/85 backdrop-blur">
      <div className="bg-marca h-0.5 w-full" />
      <div className="mx-auto flex h-14 max-w-6xl items-center gap-3 px-4">
        <Link href="/" className="flex items-center gap-2.5" aria-label={MARCA.nombre}>
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={MARCA.logo.claro} alt={MARCA.nombre} className="h-7 w-auto dark:hidden" />
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={MARCA.logo.oscuro} alt={MARCA.nombre} className="hidden h-7 w-auto dark:block" />
          <span className="rounded-full border border-linea px-2 py-0.5 text-[11px] font-semibold uppercase tracking-[0.14em] text-tinta-2">
            Studio
          </span>
        </Link>
        <nav className="ml-auto flex items-center gap-1 text-sm">
          <Link href="/" className="boton boton-fantasma">Mis videos</Link>
          <Link href="/maestros" className="boton boton-fantasma">Prompts maestros</Link>
          <Link href="/clips" className="boton boton-fantasma">Clip Studio</Link>
          <Link href="/fabrica" className="boton boton-fantasma">Fabrica</Link>
        </nav>
      </div>
    </header>
  );
}
