// Escena BARRAS: comparar cantidades. Cada barra crece cuando se dice su nombre, con su icono y su cifra.
// ESCENA = { titulo?, barras: [{etiqueta, valor (numero), texto ("1,2 bill."), color, src? | bandera?, a}], variante? }
// Variantes (Python las reparte para que no se repitan): 0 barras tumbadas, 1 columnas que suben (hasta 5).
F.montar(() => {
  const E = F.E;
  F.fondo();
  const arriba = F.cabecera(E.titulo, 0);
  const barras = E.barras || [];
  const max = Math.max(...barras.map((b) => b.valor), 1e-9);
  if (E.variante === 1 && barras.length >= 2 && barras.length <= 5) return columnas(E, barras, max, arriba);
  const caja = F.crear("div");
  const alto = F.zona.h - arriba;
  const ancho = F.vertical ? F.zona.w : F.zona.w * 0.72;
  caja.style.cssText = `position:absolute;left:${F.zona.x + (F.zona.w - ancho) / 2}px;top:${F.zona.y + arriba}px;width:${ancho}px;height:${alto}px;` +
    "display:flex;flex-direction:column;justify-content:center;";
  const fila = Math.min(alto / Math.max(barras.length, 1), F.corto * (F.vertical ? 0.2 : 0.16));
  const icono = fila * 0.62;
  const conIcono = barras.some((b) => b.src || b.bandera);
  const lineas = [], filas = [];
  let letra = fila;
  barras.forEach((b, i) => {
    const r = F.crear("div", "", caja);
    r.style.cssText = `height:${fila}px;display:flex;align-items:center;gap:${fila * 0.18}px;`;
    let ic = null;
    if (conIcono) {
      const hueco = F.crear("div", "", r);
      hueco.style.cssText = `width:${icono * 1.5}px;display:flex;justify-content:center;flex:none;`;
      ic = F.icono(hueco, b, b.bandera ? icono * 0.66 : icono);
    }
    const derecha = F.crear("div", "", r);
    derecha.style.cssText = "flex:1;min-width:0;";
    const textos = F.crear("div", "", derecha);
    textos.style.cssText = `display:flex;justify-content:space-between;align-items:baseline;gap:0.5em;font-size:${fila * 0.32}px;margin-bottom:${fila * 0.05}px;`;
    const nombre = F.crear("div", "", textos);
    nombre.innerHTML = F.marcar(b.etiqueta);
    nombre.style.cssText = "font-family:var(--f-texto);font-weight:800;white-space:nowrap;";
    const cifra = F.crear("div", "", textos);
    cifra.textContent = b.texto || F.formato(b.valor, 0);
    cifra.style.cssText = `font-family:var(--f-dato);font-weight:var(--peso-titulo);font-size:1.35em;color:${F.color(b.color)};white-space:nowrap;`;
    // nombre y cifra en una linea: si no caben, la letra baja (nunca se corta el nombre)
    lineas.push(textos);
    letra = Math.min(letra, F.ajustar(textos, derecha.clientWidth, fila * 0.62, fila * 0.32));
    const pista = F.crear("div", "", derecha);
    pista.style.cssText = `height:${fila * 0.3}px;border-radius:${fila * 0.15}px;background:color-mix(in srgb, var(--tinta) 12%, transparent);overflow:hidden;`;
    const barra = F.crear("div", "", pista);
    barra.style.cssText = `height:100%;width:${Math.max(2, (b.valor / max) * 100)}%;border-radius:inherit;background:${F.color(b.color)};transform-origin:0 50%;`;

    const a = Math.max(0, b.a ?? 0.3 + i * 0.5);
    F.tl.fromTo(r, { opacity: 0, x: -F.corto * 0.04 }, { opacity: 1, x: 0, duration: 0.4, ease: "power3.out", immediateRender: true }, a);
    F.tl.fromTo(barra, { scaleX: 0 }, { scaleX: 1, duration: 0.9, ease: "power3.out", immediateRender: true }, a + 0.1);
    F.tl.fromTo(cifra, { opacity: 0, scale: 0.6 }, { opacity: 1, scale: 1, duration: 0.4, ease: "back.out(2)", immediateRender: true }, a + 0.45);
    F.rebote(ic, a);
    F.flotar(ic, a, i);
    filas.push({ el: r, a });
  });
  lineas.forEach((t) => { t.style.fontSize = letra + "px"; });   // todas las filas con la misma letra
  F.enfocar(filas, F.D - 1);   // al final se ven todas para comparar
  F.deriva(caja);
});

// Columnas: cada una sube desde la base cuando se nombra; la cifra encima, el icono y el nombre debajo.
function columnas(E, barras, max, arriba) {
  const z = F.zona, alto = z.h - arriba, n = barras.length;
  const caja = F.crear("div");
  caja.style.cssText = `position:absolute;left:${z.x}px;top:${z.y + arriba}px;width:${z.w}px;height:${alto}px;`;
  const hueco = z.w * 0.05;
  const ancho = (z.w - hueco * (n - 1)) / n;
  const conIcono = barras.some((b) => b.src || b.bandera);
  const pie = alto * (conIcono ? 0.3 : 0.14);       // icono + nombre bajo la base
  const cabeza = alto * 0.12;                        // la cifra encima de la columna mas alta
  const util = alto - pie - cabeza;
  const base = F.crear("div", "", caja);
  base.style.cssText = `position:absolute;left:0;right:0;top:${cabeza + util}px;height:${F.corto * 0.006}px;background:var(--tinta-suave);border-radius:9px;`;
  const nombres = [], cifras = [], foco = [];
  barras.forEach((b, i) => {
    const x = i * (ancho + hueco);
    const h = Math.max(F.corto * 0.01, (b.valor / max) * util);
    const col = F.crear("div", "", caja);
    col.style.cssText = `position:absolute;left:${x}px;top:${cabeza + util - h}px;width:${ancho}px;height:${h}px;background:${F.color(b.color)};` +
      `border-radius:${ancho * 0.12}px ${ancho * 0.12}px 0 0;transform-origin:50% 100%;box-shadow:0 0.3em 1em rgba(0,0,0,0.2);`;
    const cifra = F.crear("div", "", caja);
    cifra.textContent = b.texto || F.formato(b.valor, 0);
    cifra.style.cssText = `position:absolute;left:${x - hueco / 2}px;width:${ancho + hueco}px;top:${cabeza + util - h - cabeza}px;height:${cabeza}px;` +
      `display:flex;align-items:flex-end;justify-content:center;font-family:var(--f-dato);font-weight:var(--peso-titulo);color:${F.color(b.color)};white-space:nowrap;`;
    cifras.push([cifra, F.ajustar(cifra, ancho + hueco, cabeza, cabeza * 0.8)]);
    const abajo = F.crear("div", "", caja);
    abajo.style.cssText = `position:absolute;left:${x - hueco / 2}px;width:${ancho + hueco}px;top:${cabeza + util + F.corto * 0.015}px;height:${pie}px;` +
      `display:flex;flex-direction:column;align-items:center;gap:${F.corto * 0.01}px;text-align:center;`;
    const ic = conIcono ? F.icono(abajo, b, Math.min(pie * 0.5, ancho * 0.8) * (b.bandera ? 0.6 : 1)) : null;
    const nombre = F.crear("div", "", abajo);
    nombre.innerHTML = F.marcar(b.etiqueta);
    nombre.style.cssText = "font-family:var(--f-texto);font-weight:800;line-height:1.05;";
    nombres.push([nombre, F.ajustar(nombre, ancho + hueco, pie * (conIcono ? 0.4 : 0.9), F.corto * 0.05)]);
    const a = Math.max(0, b.a ?? 0.3 + i * 0.5);
    F.tl.fromTo(col, { scaleY: 0 }, { scaleY: 1, duration: 0.9, ease: "power3.out", immediateRender: true }, a);
    F.tl.fromTo(abajo, { opacity: 0, y: F.corto * 0.03 }, { opacity: 1, y: 0, duration: 0.4, ease: "power3.out", immediateRender: true }, a);
    F.tl.fromTo(cifra, { opacity: 0, y: h * 0.8 }, { opacity: 1, y: 0, duration: 0.9, ease: "power3.out", immediateRender: true }, a);
    F.rebote(ic, a);
    F.flotar(ic, a, i);
    foco.push({ el: [col, cifra, abajo], a });
  });
  // misma letra en todos los nombres y todas las cifras
  const letra = Math.min(...nombres.map((x) => x[1]));
  nombres.forEach(([el]) => { el.style.fontSize = letra + "px"; });
  const tc = Math.min(...cifras.map((x) => x[1]));
  cifras.forEach(([el]) => { el.style.fontSize = tc + "px"; });
  F.enfocar(foco, F.D - 1);
  F.deriva(caja);
}
