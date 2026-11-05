"use client";

// Crear un presentador propio: Nano Banana lo dibuja desde una descripcion o desde una foto (3 opciones para elegir;
// solo en el PC con Flow) o se sube una imagen ya hecha (PNG con transparencia o sobre verde croma). Al terminar queda en la lista de presentadores.
import { useEffect, useState } from "react";
import { Camera, Loader2, Sparkles, Upload, X } from "lucide-react";
import { presentadores, type FotoPresentador } from "@/lib/api";

export default function NuevoPresentador({ onCreado, onCerrar }: { onCreado: (id: string) => void; onCerrar: () => void }) {
  const [nombre, setNombre] = useState("");
  const [descripcion, setDescripcion] = useState("");
  const [verde, setVerde] = useState(false);
  const [trabajando, setTrabajando] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [foto, setFoto] = useState<FotoPresentador | null>(null);

  // el dibujo desde foto va en segundo plano: se pregunta cada 4 s hasta que termina
  useEffect(() => {
    if (foto?.estado !== "trabajando") return;
    const t = setTimeout(() => {
      presentadores.estadoFoto(foto.id).then(setFoto).catch((e) => { setError(String((e as Error).message || e)); setFoto(null); });
    }, 4000);
    return () => clearTimeout(t);
  }, [foto]);

  async function hacer(fn: () => Promise<{ id: string }>) {
    setTrabajando(true);
    setError(null);
    try {
      const p = await fn();
      if (p.id) onCreado("propio:" + p.id);
    } catch (e) { setError(String((e as Error).message || e)); }
    setTrabajando(false);
  }

  return (
    <div className="mt-2 rounded-xl border border-linea bg-hundido p-3">
      <div className="mb-2 flex items-center justify-between">
        <p className="etiqueta">Nuevo presentador</p>
        <button type="button" className="boton boton-fantasma !px-2 !py-1" onClick={onCerrar}><X size={14} /></button>
      </div>
      <input className="campo" placeholder="Nombre (p. ej. Juan)" value={nombre} maxLength={40} onChange={(e) => setNombre(e.target.value)} />
      <textarea className="campo mt-2 min-h-16" value={descripcion} onChange={(e) => setDescripcion(e.target.value)}
        placeholder="Como es: hombre joven, pelo rizado negro, barba corta, gafas redondas, sudadera mostaza…" />
      <div className="mt-2 flex flex-wrap items-center gap-2">
        <button type="button" className="boton boton-acento !py-1.5 text-sm" disabled={trabajando || !descripcion.trim()}
          onClick={() => hacer(() => presentadores.crear(nombre, descripcion))}>
          {trabajando ? <Loader2 size={14} className="animate-spin" /> : <Sparkles size={14} />} Dibujar con Nano Banana
        </button>
        <label className={`boton boton-linea !py-1.5 text-sm ${trabajando ? "pointer-events-none opacity-50" : "cursor-pointer"}`}>
          <Upload size={14} /> Subir imagen
          <input type="file" accept="image/png,image/webp,image/jpeg" hidden onChange={(e) => {
            const f = e.target.files?.[0];
            if (f) hacer(() => presentadores.subir(f, nombre || f.name.replace(/\.[^.]+$/, ""), verde));
          }} />
        </label>
        <label className={`boton boton-linea !py-1.5 text-sm ${trabajando ? "pointer-events-none opacity-50" : "cursor-pointer"}`}
          title="Sube una foto de frente (tuya o de alguien que lo permita): Nano Banana dibuja 3 opciones">
          <Camera size={14} /> Desde foto
          <input type="file" accept="image/png,image/webp,image/jpeg" hidden onChange={(e) => {
            const f = e.target.files?.[0];
            e.target.value = "";
            if (f) hacer(async () => { if (foto) await presentadores.descartarFoto(foto.id).catch(() => {}); setFoto(await presentadores.desdeFoto(f)); return { id: "" }; });
          }} />
        </label>
        <label className="flex items-center gap-1.5 text-xs text-tinta-2">
          <input type="checkbox" checked={verde} onChange={(e) => setVerde(e.target.checked)} /> la imagen tiene fondo verde
        </label>
      </div>
      {foto && (
        <div className="mt-3">
          <p className="etiqueta mb-1">
            {foto.estado === "trabajando"
              ? <><Loader2 size={12} className="mr-1 inline animate-spin" />Dibujando {foto.opciones.length + 1} de {foto.total}… (~1 min cada una)</>
              : foto.estado === "error" && !foto.opciones.length ? "No salio ninguna opcion" : "Elige una opcion"}
          </p>
          {foto.error && <p className="mb-1 text-xs text-error">{foto.error}</p>}
          <div className="grid grid-cols-3 gap-2">
            {foto.opciones.map((n) => (
              <button key={n} type="button" disabled={trabajando || foto.estado === "trabajando"} className="overflow-hidden rounded-lg border border-linea hover:border-acento disabled:opacity-50"
                onClick={() => hacer(() => presentadores.elegirFoto(foto.id, n, nombre))}>
                <img src={presentadores.urlOpcion(foto.id, n)} alt={`Opcion ${n}`} className="w-full bg-hundido object-contain" />
              </button>
            ))}
          </div>
          <button type="button" className="boton boton-fantasma mt-1 !px-2 !py-1 text-xs" disabled={trabajando}
            onClick={() => { presentadores.descartarFoto(foto.id).catch(() => {}); setFoto(null); }}>Descartar</button>
        </div>
      )}
      <p className="mt-2 text-xs text-tinta-3">
        Desde foto tarda ~3 min (3 opciones; la foto se borra al elegir). Dibujar tarda ~1 min y solo funciona en el PC con Flow. Claude ubica sus ojos y su boca para animarlo; queda guardado
        para todos tus videos.
      </p>
      {error && <p className="mt-2 text-xs text-error">{error}</p>}
    </div>
  );
}
