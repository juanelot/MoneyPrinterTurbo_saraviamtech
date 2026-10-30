// Escena LINEA DE TIEMPO: fechas en orden sobre una linea que se va dibujando; cada hito entra cuando se dice
// su fecha. En vertical y cuadrado la linea baja por la izquierda; en horizontal cruza de lado a lado.
// ESCENA = { titulo?, hitos: [{fecha, texto, src? | bandera?, a}] }
F.montar(() => {
  const E = F.E;
  F.fondo();
  const arriba = F.cabecera(E.titulo, 0);
  const hitos = E.hitos || [];
  const n = Math.max(hitos.length, 1);
  const x0 = F.zona.x, y0 = F.zona.y + arriba, W = F.zona.w, H = F.zona.h - arriba;
  const horizontal = !F.vertical && !F.cuadrado;
  const grosor = F.corto * 0.008;
  const caja = F.crear("div");
  caja.style.cssText = `position:absolute;left:${x0}px;top:${y0}px;width:${W}px;height:${H}px;`;
  const linea = F.crear("div", "", caja);
  const margen = horizontal ? W / n / 2 : H / n / 2;
  linea.style.cssText = horizontal
    ? `position:absolute;left:${margen}px;right:${margen}px;top:${H / 2 - grosor / 2}px;height:${grosor}px;`
    : `position:absolute;top:${margen}px;bottom:${margen}px;left:${F.corto * 0.06}px;width:${grosor}px;`;
  linea.style.cssText += `background:var(--tinta-suave);border-radius:${grosor}px;transform-origin:${horizontal ? "0 50%" : "50% 0"};`;
  const primera = Math.max(0, hitos[0]?.a ?? 0.3);
  const ultima = Math.max(primera + 0.5, hitos[n - 1]?.a ?? primera + 2);
  F.tl.fromTo(linea, horizontal ? { scaleX: 0 } : { scaleY: 0 }, { scaleX: 1, scaleY: 1, duration: ultima - primera + 0.4, ease: "power1.inOut", immediateRender: true }, Math.max(0, primera - 0.3));

  const paso = (horizontal ? W : H) / n;
  const punto = F.corto * 0.035;
  const foco = [];
  hitos.forEach((h, i) => {
    const centro = paso * (i + 0.5);
    const p = F.crear("div", "", caja);
    p.style.cssText = `position:absolute;width:${punto}px;height:${punto}px;border-radius:50%;background:var(--acento);` +
      `box-shadow:0 0 0 ${punto * 0.25}px var(--fondo);` +
      (horizontal ? `left:${centro - punto / 2}px;top:${H / 2 - punto / 2}px;` : `left:${F.corto * 0.06 + grosor / 2 - punto / 2}px;top:${centro - punto / 2}px;`);
    const t = F.crear("div", "", caja);
    // en horizontal, uno arriba y otro abajo de la linea para que quepan
    const alto = horizontal ? H / 2 - punto * 1.5 : paso * 0.9;
    const ancho = horizontal ? paso * 0.95 : W - F.corto * 0.14;
    t.style.cssText = "position:absolute;display:flex;align-items:center;gap:0.4em;" + (horizontal
      ? `left:${centro - ancho / 2}px;width:${ancho}px;flex-direction:column;justify-content:${i % 2 ? "flex-start" : "flex-end"};` +
        `${i % 2 ? `top:${H / 2 + punto * 1.5}px` : `top:0`};height:${alto}px;text-align:center;`
      : `left:${F.corto * 0.14}px;width:${ancho}px;top:${centro - alto / 2}px;height:${alto}px;`);
    const ic = (h.src || h.bandera) ? F.icono(t, h, Math.min(alto * 0.55, F.corto * 0.17) * (h.bandera ? 0.6 : 1)) : null;
    if (ic && horizontal && i % 2 === 0) t.appendChild(ic);   // arriba de la linea: el icono va pegado a ella
    const textos = F.crear("div", "", t);
    textos.style.cssText = "min-width:0;";
    if (ic && horizontal && i % 2 === 0) t.insertBefore(textos, ic);
    const fecha = F.crear("div", "", textos);
    fecha.textContent = h.fecha;
    // con muchos hitos el hueco es bajo: la fecha se achica y el texto ocupa solo lo que queda (nunca pisa al siguiente)
    const tamFecha = Math.min(F.corto * 0.09, alto * (horizontal ? 0.3 : 0.42));
    fecha.style.cssText = `font-family:var(--f-dato);font-weight:var(--peso-titulo);color:var(--acento);line-height:1;font-size:${tamFecha}px;`;
    const desc = F.crear("div", "", textos);
    desc.innerHTML = F.marcar(h.texto);
    desc.style.cssText = "font-family:var(--f-texto);font-weight:700;line-height:1.15;margin-top:0.15em;";
    const libre = Math.max(alto * 0.25, (horizontal ? alto * 0.7 : alto * 0.92) - tamFecha * 1.2);
    F.ajustar(desc, ancho - (ic && !horizontal ? F.corto * 0.16 : 0), libre, Math.min(F.corto * 0.06, libre * 0.55));
    const a = Math.max(0, h.a ?? 0.3 + i * 0.8);
    F.tl.fromTo(p, { scale: 0 }, { scale: 1, duration: 0.4, ease: "back.out(3)", immediateRender: true }, a);
    F.entrar([fecha, desc], a + 0.05, 0.1);
    F.rebote(ic, a + 0.15);
    F.flotar(ic, a, i);
    foco.push({ el: t, a });
  });
  F.enfocar(foco, F.D - 0.8);
  F.deriva(caja);
});
