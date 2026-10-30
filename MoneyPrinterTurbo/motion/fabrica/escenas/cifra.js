// Escena CIFRA: un numero enorme que cuenta desde 0 cuando se dice, con su etiqueta.
// ESCENA = { numero: "400", antes?: "$", despues?: " km", etiqueta: "de costa perdida", contexto?: "...", a, variante? }
// Variantes (Python las reparte para que no se repitan): 0 centrada, 1 dentro de un anillo que se llena mientras
// cuenta, 2 en bloque a la izquierda con una franja de acento que barre.
F.montar(() => {
  const E = F.E;
  const V = E.variante || 0;
  F.fondo();
  const z = F.zona;
  const izquierda = V === 2;
  const caja = F.crear("div");
  caja.style.cssText = `position:absolute;left:${z.x}px;width:${z.w}px;text-align:${izquierda ? "left" : "center"};`;
  let contexto = null;
  if (E.contexto) {
    contexto = F.crear("div", "", caja);
    contexto.innerHTML = F.marcar(E.contexto);
    contexto.style.cssText = `font-weight:700;font-size:${F.corto * 0.05}px;color:var(--tinta-suave);margin-bottom:0.6em;line-height:1.2;`;
  }
  // anillo: el numero va dentro de un circulo, asi que su ancho es el del hueco del circulo
  const diametro = Math.min(z.w, z.h * (F.vertical ? 0.62 : 0.68));
  let anillo = null, hueco = caja;
  if (V === 1) {
    anillo = F.crear("div", "", caja);
    anillo.style.cssText = `position:relative;width:${diametro}px;height:${diametro}px;margin:0 auto;display:flex;align-items:center;justify-content:center;`;
    hueco = anillo;
  }
  const numero = F.crear("div", "titulo", hueco);
  numero.style.cssText += "font-family:var(--f-dato);color:var(--acento);white-space:nowrap;font-variant-numeric:tabular-nums;position:relative;";
  // se mide con el numero final para que el tamano no cambie mientras cuenta
  const { n, dec } = F.aNumero(E.numero);
  numero.textContent = (E.antes || "") + F.formato(n, dec) + (E.despues || "");
  if (V === 1) F.ajustar(numero, diametro * 0.74, diametro * 0.45, F.corto * 0.32, diametro * 0.08);
  else F.ajustar(numero, z.w, z.h * (izquierda ? 0.34 : 0.4), F.corto * (izquierda ? 0.26 : 0.3));
  let franja = null;
  if (izquierda) {
    franja = F.crear("div", "", caja);
    franja.style.cssText = `height:${F.corto * 0.022}px;width:${z.w * 0.55}px;background:var(--acento);border-radius:${F.corto * 0.011}px;` +
      `margin:${F.corto * 0.02}px 0 ${F.corto * 0.03}px;transform-origin:0 50%;`;
  }
  const etiqueta = F.crear("div", "titulo", caja);
  etiqueta.innerHTML = F.marcar(E.etiqueta || "");
  etiqueta.style.cssText += "margin-top:0.25em;";
  F.ajustar(etiqueta, z.w, z.h * (V === 1 ? 0.2 : 0.25), F.corto * (izquierda ? 0.085 : 0.075));
  caja.style.top = z.y + (z.h - caja.offsetHeight) / 2 + "px";

  // lo que significa ya se ve en el primer fotograma (sin corte en vacio) y se asienta; el numero salta y
  // cuenta cuando se dice
  const a = Math.max(0, E.a ?? 0.15);
  F.tl.fromTo([contexto, etiqueta].filter(Boolean), { y: "0.15em", opacity: 0.75 }, { y: 0, opacity: 1, duration: 0.5, ease: "power3.out", immediateRender: true }, 0);
  F.entrar(numero, Math.max(0, a - 0.2));
  F.contar(numero, E.numero, a, 1.3, E.antes || "", E.despues || "");
  if (anillo) {
    // pista tenue + arco de acento que da la vuelta mientras el numero cuenta
    const ns = "http://www.w3.org/2000/svg";
    const svg = document.createElementNS(ns, "svg");
    svg.setAttribute("viewBox", "0 0 100 100");
    svg.style.cssText = "position:absolute;inset:0;width:100%;height:100%;transform:rotate(-90deg);";
    anillo.prepend(svg);
    const r = 46, largo = 2 * Math.PI * r;
    for (const [color, ancho, ancla] of [["color-mix(in srgb, var(--tinta) 14%, transparent)", 5, false], ["var(--acento)", 6, true]]) {
      const c = document.createElementNS(ns, "circle");
      Object.entries({ cx: 50, cy: 50, r, fill: "none", "stroke-width": ancho, "stroke-linecap": "round" }).forEach(([k, x]) => c.setAttribute(k, x));
      c.style.stroke = color;
      svg.appendChild(c);
      if (ancla) {
        c.style.strokeDasharray = largo;
        F.tl.fromTo(c, { strokeDashoffset: largo }, { strokeDashoffset: 0, duration: 1.3, ease: "power3.out", immediateRender: true }, a);
      }
    }
  }
  if (franja) F.tl.fromTo(franja, { scaleX: 0 }, { scaleX: 1, duration: 0.7, ease: "power3.out", immediateRender: true }, a);
  F.tl.fromTo(caja, { scale: 1 }, { scale: 1.04, duration: F.D, ease: "none", transformOrigin: izquierda ? "0% 50%" : "50% 50%" }, 0);
});
