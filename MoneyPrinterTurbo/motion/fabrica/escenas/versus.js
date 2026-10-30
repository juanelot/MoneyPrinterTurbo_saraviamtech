// Escena VERSUS: dos cosas frente a frente (paises, empresas, epocas...). Cada lado entra cuando se nombra, con
// su icono, su nombre y un dato; el "VS" del medio entra como un sello.
// ESCENA = { titulo?, lados: [{nombre, dato?, color, src? | bandera?, a}, {...}], vs: segundo del sello, variante? }
// Variantes (Python las reparte para que no se repitan): 0 dos tarjetas (en vertical arriba y abajo),
// 1 pantalla partida en diagonal con el color de cada lado, 2 duelo: los dos iconos en circulos lado a lado.
F.montar(() => {
  const E = F.E;
  const V = E.variante || 0;
  const lados = (E.lados || []).slice(0, 2);
  const cuando = (l, i) => Math.max(0, l.a ?? 0.3 + i * 1.2);
  const sello = (x, y, tam) => {
    const vs = F.crear("div", "golpe");
    vs.textContent = "VS";
    vs.style.cssText += `font-size:${tam}px;width:${tam * 2}px;left:${x - tam}px;top:${y - tam * 0.5}px;z-index:6;`;
    F.tl.fromTo(vs, { opacity: 0, scale: 2, rotation: -12 }, { opacity: 1, scale: 1, rotation: -6, duration: 0.32, ease: "power4.out", immediateRender: true },
      Math.max(0, E.vs ?? 1));
  };
  const textos = (padre, l, ancho, alto, centro, tamNombre = 0.09) => {
    const caja = F.crear("div", "", padre);
    caja.style.cssText = `text-align:${centro ? "center" : "left"};min-width:0;`;
    const nombre = F.crear("div", "titulo", caja);
    nombre.textContent = l.nombre;
    nombre.style.color = F.color(l.color);
    F.ajustar(nombre, ancho, alto * 0.45, F.corto * tamNombre);
    if (l.dato) {
      const dato = F.crear("div", "", caja);
      dato.innerHTML = F.marcar(l.dato);
      dato.style.cssText = "font-family:var(--f-texto);font-weight:700;color:var(--tinta);margin-top:0.25em;line-height:1.15;";
      F.ajustar(dato, ancho, alto * 0.5, F.corto * 0.05);
    }
    return { caja, nombre };
  };

  if (V === 1) {
    // pantalla partida: cada lado tine su mitad (arriba/abajo en vertical, izquierda/derecha en horizontal) con un
    // corte en diagonal; el titulo va en una pastilla arriba
    F.fondo();
    const W = F.W, H = F.H, apilado = F.vertical;
    const inclina = (apilado ? H : W) * 0.04;
    lados.forEach((l, i) => {
      const mitad = F.crear("div", "");
      const c = F.color(l.color);
      mitad.style.cssText = `position:absolute;inset:0;background:linear-gradient(${apilado ? 180 : 90}deg, color-mix(in srgb, ${c} 55%, var(--fondo)) 0%, color-mix(in srgb, ${c} 30%, var(--fondo)) 100%);`;
      const m = apilado ? H / 2 : W / 2;
      mitad.style.clipPath = apilado
        ? (i === 0 ? `polygon(0 0,100% 0,100% ${m - inclina}px,0 ${m + inclina}px)` : `polygon(0 ${m + inclina}px,100% ${m - inclina}px,100% 100%,0 100%)`)
        : (i === 0 ? `polygon(0 0,${m + inclina}px 0,${m - inclina}px 100%,0 100%)` : `polygon(${m + inclina}px 0,100% 0,100% 100%,${m - inclina}px 100%)`);
      // el hueco util de cada mitad dentro de la zona segura
      const z = F.zona;
      const arribaT = E.titulo ? F.corto * 0.14 : 0;
      const hz = apilado
        ? { x: z.x, y: i === 0 ? z.y + arribaT : H / 2 + inclina, w: z.w, h: i === 0 ? H / 2 - inclina - z.y - arribaT : z.y + z.h - H / 2 - inclina }
        : { x: i === 0 ? z.x : W / 2 + inclina, y: z.y + arribaT, w: z.w / 2 - inclina, h: z.h - arribaT };
      const dentro = F.crear("div", "", mitad);
      dentro.style.cssText = `position:absolute;left:${hz.x}px;top:${hz.y}px;width:${hz.w}px;height:${hz.h}px;display:flex;` +
        `flex-direction:${apilado ? "row" : "column"};align-items:center;justify-content:center;gap:${F.corto * 0.04}px;`;
      const icono = Math.min(hz.h * (apilado ? 0.75 : 0.45), hz.w * 0.42);
      const ic = F.icono(F.crear("div", "", dentro), l, l.bandera ? icono * 0.6 : icono);
      textos(dentro, l, apilado ? hz.w - icono * 1.3 : hz.w * 0.95, hz.h * (apilado ? 0.9 : 0.45), !apilado, 0.11);
      const a = cuando(l, i);
      const fuera = apilado ? { y: (i ? 1 : -1) * H * 0.5 } : { x: (i ? 1 : -1) * W * 0.5 };
      F.tl.fromTo(mitad, { ...fuera, opacity: 0.4 }, { x: 0, y: 0, opacity: 1, duration: 0.5, ease: "power4.out", immediateRender: true }, a);
      F.rebote(ic, a + 0.15);
      F.flotar(ic, a, i * 2);
    });
    if (E.titulo) {
      const t = F.crear("div", "titulo");
      t.innerHTML = F.marcar(E.titulo);
      t.style.cssText += `position:absolute;z-index:6;left:50%;top:${F.zona.y}px;max-width:${F.zona.w}px;text-align:center;` +
        `background:var(--panel);border-radius:999px;padding:0.2em 0.8em;box-shadow:0 0.2em 0.8em rgba(0,0,0,0.3);white-space:nowrap;`;
      F.ajustar(t, F.zona.w, F.corto * 0.11, F.corto * 0.065);
      gsap.set(t, { xPercent: -50 });
      F.entrar(t, 0);
    }
    sello(F.W / 2, F.H / 2, F.corto * 0.15);
    return;
  }

  F.fondo();
  const arriba = F.cabecera(E.titulo, 0);
  const alto = F.zona.h - arriba;
  const caja = F.crear("div");

  if (V === 2) {
    // duelo: los dos iconos en circulos del color de su lado, siempre lado a lado; nombre y dato debajo
    const hueco = F.corto * 0.08;
    const ancho = (F.zona.w - hueco) / 2;
    const circulo = Math.min(ancho * 0.92, alto * 0.5);
    caja.style.cssText = `position:absolute;left:${F.zona.x}px;top:${F.zona.y + arriba}px;width:${F.zona.w}px;height:${alto}px;` +
      `display:flex;gap:${hueco}px;align-items:center;`;
    let centro = 0;
    lados.forEach((l, i) => {
      const col = F.crear("div", "", caja);
      col.style.cssText = `width:${ancho}px;display:flex;flex-direction:column;align-items:center;gap:${F.corto * 0.03}px;`;
      const aro = F.crear("div", "", col);
      const c = F.color(l.color);
      aro.style.cssText = `width:${circulo}px;height:${circulo}px;border-radius:50%;display:flex;align-items:center;justify-content:center;` +
        `background:color-mix(in srgb, ${c} 22%, var(--panel));border:${F.corto * 0.012}px solid ${c};box-shadow:0 0.3em 1.2em rgba(0,0,0,0.3);`;
      const ic = F.icono(aro, l, circulo * (l.bandera ? 0.42 : 0.68));
      textos(col, l, ancho, alto - circulo - F.corto * 0.03, true, 0.075);
      const a = cuando(l, i);
      F.tl.fromTo(col, { opacity: 0, scale: 0.5, x: (i ? 1 : -1) * F.corto * 0.15 }, { opacity: 1, scale: 1, x: 0, duration: 0.5, ease: "back.out(1.8)", immediateRender: true }, a);
      F.rebote(ic, a + 0.15);
      F.flotar(ic, a, i * 2);
      centro = F.zona.y + arriba + (alto - col.offsetHeight) / 2 + circulo / 2;
    });
    sello(F.zona.x + F.zona.w / 2, centro, F.corto * 0.1);
    F.deriva(caja);
    return;
  }

  const apilado = F.vertical;
  caja.style.cssText = `position:absolute;left:${F.zona.x}px;top:${F.zona.y + arriba}px;width:${F.zona.w}px;height:${alto}px;` +
    `display:flex;flex-direction:${apilado ? "column" : "row"};gap:${F.corto * 0.05}px;`;
  const ancho = apilado ? F.zona.w : (F.zona.w - F.corto * 0.05) / 2;
  const largo = apilado ? (alto - F.corto * 0.05) / 2 : alto;
  lados.forEach((l, i) => {
    const p = F.crear("div", "tarjeta", caja);
    p.style.cssText += `position:relative;flex:1;display:flex;flex-direction:${apilado ? "row" : "column"};align-items:center;` +
      `justify-content:center;gap:${F.corto * 0.03}px;padding:${F.corto * 0.03}px;border:${F.corto * 0.008}px solid ${F.color(l.color)};`;
    const icono = Math.min(largo * (apilado ? 0.7 : 0.42), ancho * 0.45);
    const ic = F.icono(F.crear("div", "", p), l, l.bandera ? icono * 0.6 : icono);
    const anchoTexto = apilado ? ancho - icono * 1.2 - F.corto * 0.1 : ancho - F.corto * 0.08;
    textos(p, l, anchoTexto, largo * 0.62, !apilado);
    const a = cuando(l, i);
    F.tl.fromTo(p, apilado ? { opacity: 0, x: (i ? 1 : -1) * F.corto * 0.12 } : { opacity: 0, y: F.corto * 0.08 },
      { opacity: 1, x: 0, y: 0, duration: 0.5, ease: "power3.out", immediateRender: true }, a);
    F.rebote(ic, a + 0.1);
    F.flotar(ic, a, i * 2);
  });
  sello(F.zona.x + F.zona.w / 2, F.zona.y + arriba + alto / 2, F.corto * 0.13);
  F.deriva(caja);
});
