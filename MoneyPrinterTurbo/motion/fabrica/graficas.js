// Piezas de las escenas sin mapa (barras, lista, versus, linea de tiempo): el titulo de arriba, el icono de
// cada elemento (pegatina de la biblioteca o bandera) y el vaiven lento que hace que nada este quieto del todo.
(() => {
  const { corto, v } = F;
  // nombre de color del estilo ("rojo", "acento"...) o #hex (mapa.js define lo mismo para los mapas)
  F.color = F.color || ((nombre) => (String(nombre || "").startsWith("#") ? nombre : v(nombre || "acento") || v("acento")));

  // Titulo de la escena arriba de la zona segura; devuelve su alto (lo que queda debajo es para el grafico).
  F.cabecera = (texto, a = 0) => {
    if (!texto) return 0;
    const el = F.crear("div", "titulo");
    el.innerHTML = F.marcar(texto);
    // encima de las tarjetas (con la deriva y los rebotes de los iconos podian taparlo)
    el.style.cssText += `position:absolute;z-index:5;left:${F.zona.x}px;top:${F.zona.y}px;width:${F.zona.w}px;text-align:center;`;
    F.ajustar(el, F.zona.w, F.zona.h * 0.2, corto * 0.085);
    F.entrar(el, a);
    return el.offsetHeight + corto * 0.06;
  };

  // Icono de un elemento dentro de `padre`: { src } (pegatina) o { bandera } (svg 3:2 con borde). alto en px.
  F.icono = (padre, item, alto) => {
    if (item.bandera) {
      const el = F.crear("div", "bandera", padre);
      el.style.cssText += `position:relative;width:${alto * 1.5}px;height:${alto}px;flex:none;`;
      const img = F.crear("img", "", el);
      img.src = item.bandera;
      F.imagen(item.bandera);
      return el;
    }
    if (item.src) {
      const img = F.crear("img", "", padre);
      img.src = item.src;
      F.imagen(item.src);
      img.style.cssText = `height:${alto}px;width:auto;flex:none;filter:drop-shadow(0 ${alto * 0.04}px ${alto * 0.06}px rgba(0,0,0,0.45));`;
      if (item.estado) F.estadoFijo(img, item.estado);
      return img;
    }
    return null;
  };

  // Vaiven suave de un icono una vez ha entrado (como las pegatinas del mapa).
  F.flotar = (el, a, fase = 0) => {
    if (!el) return;
    F.alPintar((t) => {
      if (t < a + 0.5) return;
      const s = t - a + fase;
      el.style.translate = `0 ${(Math.sin(s * 2.4) * corto * 0.004).toFixed(2)}px`;
      el.style.rotate = `${(Math.sin(s * 1.7) * 2).toFixed(2)}deg`;
    });
  };

  // Entrada con rebote de un icono.
  F.rebote = (el, a) => {
    if (!el) return;
    F.tl.fromTo(el, { scale: 0, rotation: -10 }, { scale: 1, rotation: 0, duration: 0.55, ease: "back.out(2.4)", immediateRender: true }, Math.max(0, a));
  };

  // Estados del protagonista: el color (filtro) y el tamano se llevan por separado, asi "gris" despues de "grande"
  // sigue grande. "normal" lo devuelve todo a como es.
  const FILTROS = { normal: [0, 1, 1, 0, 1], gris: [1, 1.05, 1, 0, 1], apagado: [0.85, 0.9, 1, 0, 0.45], brillante: [0, 1.12, 1.4, 1, 1] };
  const TAMANOS = { normal: 1, grande: 1.3, pequeno: 0.6 };
  const rgb = () => {
    const h = (v("acento") || "#ffd54a").replace("#", "");
    return h.length === 6 ? [0, 2, 4].map((i) => parseInt(h.slice(i, i + 2), 16)).join(",") : "255,213,74";
  };
  F.filtro = (estado) => {
    const [g, b, s, brillo] = FILTROS[estado] || FILTROS.normal;
    // el brillo es el color de acento con su transparencia (a 0 no deja borde)
    return `grayscale(${g}) brightness(${b}) saturate(${s}) drop-shadow(0px 0px ${(brillo * corto * 0.03).toFixed(1)}px rgba(${rgb()},${brillo}))`;
  };
  // Estado quieto de un icono (barras, lista, versus...): el protagonista gris frente al de color.
  F.estadoFijo = (el, estado) => {
    if (!el || !FILTROS[estado] || estado === "normal") return;
    el.style.filter = `${el.style.filter || ""} ${F.filtro(estado)}`;
    el.style.opacity = FILTROS[estado][4];
  };

  // Protagonista que cambia de estado: devuelve { caja, cambiar(estado, a) }. `caja` es la capa que se coloca;
  // dentro van el movimiento de un momento (salta, tiembla) y la imagen (con su vaiven).
  F.protagonista = (src, alto, inicio = "normal") => {
    const caja = F.crear("div", "");
    caja.style.cssText = "position:absolute;display:flex;align-items:center;justify-content:center;";
    const mueve = F.crear("div", "", caja);
    mueve.style.cssText = "position:relative;";
    const img = F.icono(mueve, { src }, alto);
    const actual = { filtro: FILTROS[inicio] ? inicio : "normal", tam: TAMANOS[inicio] ? inicio : "normal" };
    gsap.set(mueve, { filter: F.filtro(actual.filtro), opacity: FILTROS[actual.filtro][4], scale: TAMANOS[actual.tam] });
    F.flotar(img, -0.5);
    const copias = [];
    const cambiar = (estado, a) => {
      a = Math.max(0, a);
      if (estado === "salta") {
        F.tl.to(mueve, { keyframes: [{ y: -alto * 0.14, duration: 0.18, ease: "power2.out" }, { y: 0, duration: 0.3, ease: "bounce.out" }] }, a);
      } else if (estado === "tiembla") {
        F.tl.fromTo(mueve, { x: -corto * 0.012 }, { x: corto * 0.012, duration: 0.05, repeat: 7, yoyo: true, ease: "none", clearProps: "x" }, a);
      } else if (estado === "muchos") {
        // dos copias mas pequenas a los lados, con el mismo color que tenga en ese momento
        for (const lado of [-1, 1]) {
          const c = F.crear("div", "", caja);
          c.style.cssText = `position:absolute;left:50%;top:50%;`;
          const ci = F.icono(c, { src }, alto * 0.62);
          ci.style.transform = "translate(-50%,-40%)";
          gsap.set(c, { x: lado * alto * 0.52, filter: F.filtro(actual.filtro), opacity: FILTROS[actual.filtro][4] });
          caja.insertBefore(c, mueve);
          F.rebote(c, a + (lado > 0 ? 0.12 : 0));
          copias.push(c);
        }
      } else if (estado === "se_va") {
        F.tl.to([mueve, ...copias], { scale: 0, opacity: 0, rotation: 12, duration: 0.35, ease: "back.in(1.8)" }, a);
      } else {
        if (FILTROS[estado]) actual.filtro = estado;
        if (TAMANOS[estado]) actual.tam = estado;
        if (estado === "normal") Object.assign(actual, { filtro: "normal", tam: "normal" });
        const [, , , , op] = FILTROS[actual.filtro];
        F.tl.to(mueve, { filter: F.filtro(actual.filtro), opacity: op, scale: TAMANOS[actual.tam], duration: 0.6, ease: "power2.inOut" }, a);
        if (copias.length) F.tl.to(copias, { filter: F.filtro(actual.filtro), opacity: op, duration: 0.6, ease: "power2.inOut" }, a);
        // un pequeno golpe de escala para que el cambio se note
        F.tl.fromTo(img, { scale: 1 }, { keyframes: [{ scale: 1.08, duration: 0.15 }, { scale: 1, duration: 0.3 }] }, a);
      }
    };
    return { caja, cambiar };
  };

  // Foco: solo brilla lo que se esta nombrando; lo de antes se apaga (gris y translucido) cuando entra lo
  // siguiente. items: [{el, a}]. fin: segundo en que todo vuelve a verse entero (para comparar al final) o null.
  F.enfocar = (items, fin = null) => {
    if (!F.E.foco || items.length < 2) return;
    const orden = [...items].sort((x, y) => x.a - y.a);
    for (const x of orden) gsap.set(x.el, { filter: "grayscale(0)" });
    orden.forEach((x, i) => {
      const sig = orden[i + 1];
      if (sig && sig.a - x.a >= 0.25) F.tl.to(x.el, { opacity: 0.4, filter: "grayscale(0.9)", duration: 0.35, ease: "power2.out" }, sig.a);
    });
    if (fin != null && fin > orden[orden.length - 1].a + 0.8) {
      F.tl.to(orden.map((x) => x.el), { opacity: 1, filter: "grayscale(0)", duration: 0.4, ease: "power2.inOut" }, fin);
    }
  };

  // Acercamiento lento de toda la escena.
  F.deriva = (el) => F.tl.fromTo(el, { scale: 1 }, { scale: 1.035, duration: F.D, ease: "none" }, 0);
})();
