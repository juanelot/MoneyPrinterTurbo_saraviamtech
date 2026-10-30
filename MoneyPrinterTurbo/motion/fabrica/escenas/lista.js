// Escena LISTA: un top o una enumeracion. Cada elemento entra cuando se nombra, con su numero, su icono y su texto.
// ESCENA = { titulo?, numerar: bool, items: [{texto, src? | bandera?, a}], variante? }
// Variantes (Python las reparte para que no se repitan): 0 filas (la que suena resaltada, las de antes se apagan),
// 1 de una en una (cada elemento llena la pantalla y empuja al anterior; abajo, puntos de progreso),
// 2 rejilla de dos columnas (de 3 a 6 elementos; si no, filas).
F.montar(() => {
  const E = F.E;
  const items = E.items || [];
  const V = E.variante === 2 && (items.length < 3 || items.length > 6) ? 0 : (E.variante || 0);
  F.fondo();
  const arriba = F.cabecera(E.titulo, 0);
  const alto = F.zona.h - arriba;
  const caja = F.crear("div");
  caja.style.cssText = `position:absolute;left:${F.zona.x}px;top:${F.zona.y + arriba}px;width:${F.zona.w}px;height:${alto}px;`;
  const conIcono = items.some((x) => x.src || x.bandera);
  const cuando = (x, i) => Math.max(0, x.a ?? 0.3 + i * 0.6);

  if (V === 1) {
    // de una en una: el elemento ocupa el centro; al nombrar el siguiente, el anterior sube y se va
    const puntos = F.crear("div", "", caja);
    const pt = F.corto * 0.022;
    puntos.style.cssText = `position:absolute;left:0;right:0;bottom:0;display:flex;justify-content:center;gap:${pt}px;`;
    const libre = alto - pt * 3;
    items.forEach((x, i) => {
      const a = cuando(x, i);
      const sig = items[i + 1] ? cuando(items[i + 1], i + 1) : null;
      const el = F.crear("div", "", caja);
      el.style.cssText = `position:absolute;left:0;top:0;width:100%;height:${libre}px;display:flex;flex-direction:column;` +
        `align-items:center;justify-content:center;text-align:center;gap:${F.corto * 0.03}px;`;
      if (E.numerar) {
        const n = F.crear("div", "", el);
        n.textContent = i + 1;
        n.style.cssText = `font-family:var(--f-dato);font-weight:var(--peso-titulo);font-size:${F.corto * 0.16}px;line-height:1;color:var(--acento);`;
      }
      const ic = conIcono ? F.icono(el, x, (x.bandera ? 0.6 : 1) * Math.min(libre * 0.4, F.corto * 0.42)) : null;
      const t = F.crear("div", "titulo", el);
      t.innerHTML = F.marcar(x.texto);
      t.style.width = "100%";
      F.ajustar(t, F.zona.w, libre * (conIcono ? 0.32 : 0.55), F.corto * 0.1);
      F.tl.fromTo(el, { opacity: 0, y: F.corto * 0.12, scale: 0.92 }, { opacity: 1, y: 0, scale: 1, duration: 0.45, ease: "back.out(1.6)", immediateRender: true }, a);
      if (sig != null) F.tl.to(el, { opacity: 0, y: -F.corto * 0.1, scale: 0.94, duration: 0.3, ease: "power2.in" }, Math.max(a + 0.3, sig - 0.25));
      F.rebote(ic, a + 0.1);
      F.flotar(ic, a, i);
      const p = F.crear("div", "", puntos);
      p.style.cssText = `width:${pt}px;height:${pt}px;border-radius:50%;background:color-mix(in srgb, var(--tinta) 25%, transparent);`;
      F.tl.to(p, { backgroundColor: F.v("acento"), scale: 1.4, duration: 0.25 }, a);
      if (sig != null) F.tl.to(p, { scale: 1, duration: 0.25 }, sig);
    });
    F.deriva(caja);
    return;
  }

  if (V === 2) {
    // rejilla: tarjetas con el icono arriba y el texto debajo
    const cols = F.vertical || items.length === 4 ? 2 : 3;
    const filasN = Math.ceil(items.length / cols);
    const hueco = F.corto * 0.03;
    const anchoT = (F.zona.w - hueco * (cols - 1)) / cols;
    const altoT = Math.min((alto - hueco * (filasN - 1)) / filasN, anchoT * 1.25);
    caja.style.cssText += `display:grid;grid-template-columns:repeat(${cols}, ${anchoT}px);gap:${hueco}px;align-content:center;justify-content:center;`;
    const foco = items.map((x, i) => {
      const r = F.crear("div", "tarjeta", caja);
      r.style.cssText += `position:relative;height:${altoT}px;display:flex;flex-direction:column;align-items:center;justify-content:center;` +
        `gap:${altoT * 0.05}px;text-align:center;padding:${altoT * 0.06}px;`;
      if (E.numerar) {
        const n = F.crear("div", "", r);
        n.textContent = i + 1;
        n.style.cssText = `position:absolute;left:${altoT * 0.07}px;top:${altoT * 0.04}px;font-family:var(--f-dato);font-weight:var(--peso-titulo);` +
          `font-size:${altoT * 0.16}px;color:var(--acento);`;
      }
      const ic = conIcono ? F.icono(r, x, (x.bandera ? 0.6 : 1) * altoT * 0.4) : null;
      const t = F.crear("div", "", r);
      t.innerHTML = F.marcar(x.texto);
      t.style.cssText = "font-family:var(--f-texto);font-weight:800;line-height:1.1;";
      F.ajustar(t, anchoT * 0.88, altoT * (conIcono ? 0.4 : 0.8), altoT * (conIcono ? 0.17 : 0.22));
      const a = cuando(x, i);
      F.tl.fromTo(r, { opacity: 0, scale: 0.6, rotation: i % 2 ? 4 : -4 }, { opacity: 1, scale: 1, rotation: 0, duration: 0.45, ease: "back.out(2)", immediateRender: true }, a);
      F.rebote(ic, a + 0.1);
      F.flotar(ic, a, i);
      return { el: r, a };
    });
    F.enfocar(foco, F.D - 0.8);
    F.deriva(caja);
    return;
  }

  caja.style.cssText += "display:flex;flex-direction:column;justify-content:center;";
  const fila = Math.min(alto / Math.max(items.length, 1), F.corto * (F.vertical ? 0.25 : 0.16));
  const icono = fila * 0.56;
  const filas = items.map((x, i) => {
    const r = F.crear("div", "tarjeta", caja);
    r.style.cssText += `position:relative;height:${fila * 0.86}px;margin:${fila * 0.07}px 0;display:flex;align-items:center;` +
      `gap:${fila * 0.12}px;padding:0 ${fila * 0.18}px;`;
    if (E.numerar) {
      const n = F.crear("div", "", r);
      n.textContent = i + 1;
      n.style.cssText = `font-family:var(--f-dato);font-weight:var(--peso-titulo);font-size:${fila * 0.46}px;color:var(--acento);min-width:1em;text-align:center;`;
    }
    let ic = null;
    if (conIcono) {
      const hueco = F.crear("div", "", r);
      hueco.style.cssText = `width:${icono * 1.15}px;display:flex;justify-content:center;flex:none;`;
      ic = F.icono(hueco, x, x.bandera ? icono * 0.6 : icono);
    }
    const t = F.crear("div", "", r);
    t.innerHTML = F.marcar(x.texto);
    t.style.cssText = "flex:1;min-width:0;font-family:var(--f-texto);font-weight:800;line-height:1.1;";
    F.ajustar(t, t.clientWidth, fila * 0.75, fila * 0.32);
    const a = cuando(x, i);
    F.entrar(r, a);
    F.rebote(ic, a + 0.1);
    F.flotar(ic, a, i);
    return { el: r, a };
  });
  // la ultima nombrada manda: las de antes se apagan
  F.enfocar(filas);
  F.deriva(caja);
});
