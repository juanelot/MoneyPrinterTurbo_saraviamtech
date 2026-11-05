// Nucleo de la Fabrica: lo comparten todas las escenas (HyperFrames + GSAP).
// Python deja en datos.js: window.CFG = {W, H, D} y window.ESCENA = datos de la escena, con los tiempos ya en
// segundos DE LA ESCENA (0 = su primer fotograma). Cada escena llama a F.montar(() => { ... }) y dentro crea sus
// elementos y anade tweens a F.tl. Todo lo que dependa del tiempo se pinta con F.alPintar(fn) (fn recibe t).
(() => {
  const { W, H, D } = window.CFG;
  const E = window.ESCENA || {};
  const css = getComputedStyle(document.body);
  const v = (nombre) => css.getPropertyValue("--" + nombre).trim();
  const corto = Math.min(W, H);
  const vertical = H / W > 1.3;
  const cuadrado = !vertical && W / H < 1.3;
  // Zona segura: lo importante va dentro. Abajo quedan los subtitulos y, en vertical, los botones de la app a la derecha.
  // Con presentador (abajo a la derecha) los subtitulos van arriba a la izquierda y el contenido queda entre los dos.
  const zona = E.presentador
    ? (vertical ? { x: W * 0.07, y: H * 0.235, w: W * 0.86, h: H * 0.36 }
      : cuadrado ? { x: W * 0.06, y: H * 0.27, w: W * 0.58, h: H * 0.62 }
      : { x: W * 0.05, y: H * 0.27, w: W * 0.6, h: H * 0.66 })
    : vertical ? { x: W * 0.07, y: H * 0.13, w: W * 0.8, h: H * 0.54 }
    : cuadrado ? { x: W * 0.07, y: H * 0.08, w: W * 0.86, h: H * 0.62 }
    : { x: W * 0.06, y: H * 0.08, w: W * 0.88, h: H * 0.64 };
  const pintores = [];
  const tl = gsap.timeline({ paused: true, onUpdate: () => pintores.forEach((p) => p(tl.time())) });
  const escena = document.getElementById("escena");

  const crear = (etiqueta, clase, padre = escena) => {
    const el = document.createElement(etiqueta);
    if (clase) el.className = clase;
    padre.appendChild(el);
    return el;
  };
  const escapar = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);
  // *palabra* sale en el color de acento
  const marcar = (texto) => escapar(texto).replace(/\*(.+?)\*/g, '<span class="acento">$1</span>');
  // El texto palabra a palabra (cada una en su span .pal, para animarlas); *varias palabras* siguen en acento.
  const enPalabras = (texto) => {
    let dentro = false;
    return String(texto ?? "").split(/\s+/).filter(Boolean).map((w) => {
      const abre = w.startsWith("*"), cierra = w.replace(/[.,;:!?¿¡…"]+$/, "").endsWith("*");
      const acento = dentro || abre;
      if (abre) dentro = true;
      if (cierra) dentro = false;
      return `<span class="pal${acento ? " acento" : ""}" style="display:inline-block">${escapar(w.replace(/\*/g, ""))}</span>`;
    }).join(" ");
  };

  // Achica la letra hasta que el texto quepa en ancho x alto.
  const ajustar = (el, ancho, alto, max, min = max * 0.35) => {
    let tam = max;
    el.style.fontSize = tam + "px";
    while (tam > min && (el.scrollWidth > ancho + 1 || el.scrollHeight > alto + 1)) {
      tam *= 0.94;
      el.style.fontSize = tam + "px";
    }
    return tam;
  };

  // Entrada segun el estilo (--entrada): subir, pop, sello, barrido o parpadeo. Siempre 2-3 propiedades a la vez, nunca lineal.
  const entrar = (el, t, retardo = 0.06) => {
    const tipo = v("entrada") || "subir";
    t = Math.max(0, t);
    if (tipo === "barrido") {
      // se descubre de izquierda a derecha (el recorte deja sitio a las sombras)
      tl.fromTo(el, { clipPath: "inset(-30% 110% -30% -10%)", x: "-0.08em" },
        { clipPath: "inset(-30% -10% -30% -10%)", x: 0, duration: 0.55, ease: "power3.inOut", stagger: retardo, immediateRender: true }, t);
      return;
    }
    if (tipo === "parpadeo") {
      // se enciende como un tubo o una pantalla vieja
      tl.set(el, { opacity: 0 }, 0);
      tl.to(el, { keyframes: { opacity: [0, 1, 0.15, 1, 0.55, 1], skewX: [14, 0, -7, 0, 0, 0] }, duration: 0.45, ease: "none", stagger: retardo }, t);
      return;
    }
    const desde = tipo === "pop" ? { opacity: 0, scale: 0.55, y: "0.15em", duration: 0.42, ease: "back.out(2.2)" }
      : tipo === "sello" ? { opacity: 0, scale: 1.7, rotation: -6, duration: 0.3, ease: "power4.out" }
      : { opacity: 0, y: "0.45em", scale: 0.96, duration: 0.45, ease: "power3.out" };
    tl.from(el, { ...desde, stagger: retardo, immediateRender: true }, t);
  };

  const formato = (n, dec) => new Intl.NumberFormat("es-ES", { minimumFractionDigits: dec, maximumFractionDigits: dec }).format(n);
  const aNumero = (s) => {
    const crudo = String(s ?? "").replace(/[^\d.,-]/g, "");
    const dec = /[.,]\d{1,2}$/.test(crudo) ? crudo.split(/[.,]/).pop().length : 0;
    const n = Number(crudo.replace(/[.,](?=\d{3}(\D|$))/g, "").replace(",", ".")) || 0;
    return { n, dec };
  };
  // Un numero que cuenta desde 0 entre t y t + dur.
  const contar = (el, texto, t, dur = 1.2, antes = "", despues = "") => {
    const { n, dec } = aNumero(texto);
    const o = { x: 0 };
    const poner = () => { el.textContent = antes + formato(o.x, dec) + despues; };
    poner();
    tl.to(o, { x: n, duration: dur, ease: "power3.out", onUpdate: poner }, Math.max(0, t));
  };

  // Fondo de las escenas sin mapa: degradado del estilo (o su textura pintada, textura.webp) + el dibujo de
  // --textura, con un movimiento lento que nunca se para.
  const fondo = () => {
    const f = crear("div", "fx-fondo", document.getElementById("root"));
    f.style.background = `radial-gradient(ellipse at 50% 38%, ${v("fondo")} 0%, ${v("fondo-2")} 100%)`;
    if (window.CFG.textura) {
      imagen("textura.webp");
      const img = crear("div", "fx-capa", f);
      img.style.cssText += "background:url(textura.webp) center/cover;";
    }
    const textura = v("textura");
    const paso = Math.round(corto * (textura === "puntos" ? 0.022 : 0.06));
    if (textura === "rejilla" || textura === "puntos") {
      const r = crear("div", "fx-capa", f);
      const dibujo = textura === "rejilla"
        ? `linear-gradient(${v("tinta")}14 1px,transparent 1px),linear-gradient(90deg,${v("tinta")}14 1px,transparent 1px)`
        : `radial-gradient(circle, ${v("tinta")}22 28%, transparent 31%)`;
      r.style.cssText += `inset:-${paso * 2}px;background-image:${dibujo};background-size:${paso}px ${paso}px;`;
      tl.to(r, { x: paso, y: paso * 0.5, duration: D, ease: "none" }, 0);
    }
    tl.fromTo(f, { scale: 1.06 }, { scale: 1, duration: D, ease: "none" }, 0);
    return f;
  };

  // Textura pintada del estilo encima de un mapa (papel envejecido, pizarra...), mezclada para que se vea el mapa.
  const texturaMapa = (padre) => {
    const alfa = Number(v("textura-mapa") || 0);
    if (!window.CFG.textura || !alfa) return;
    imagen("textura.webp");
    const capa = crear("div", "fx-capa", padre);
    capa.style.cssText += `background:url(textura.webp) center/cover;opacity:${alfa};mix-blend-mode:${v("mezcla-mapa") || "multiply"};`;
  };

  // Grano (ruido fijo que se desplaza cada fotograma) y vineta, por encima de todo.
  const acabado = () => {
    if (E.clip) return;   // sobre verde croma (clip de video detras): sin vineta ni grano, que ensuciarian el recorte
    const root = document.getElementById("root");
    const vineta = crear("div", "fx-capa", root);
    vineta.style.cssText += `z-index:8;background:radial-gradient(ellipse at center, rgba(0,0,0,0) 52%, rgba(0,0,0,${v("vineta") || 0.4}) 100%);`;
    if (v("textura") === "lineas") {
      // lineas de barrido de pantalla vieja, quietas (moverlas cada fotograma inflaria el video)
      const lineas = crear("div", "fx-capa", root);
      const paso = Math.max(3, Math.round(corto / 270));
      lineas.style.cssText += `z-index:8;background:repeating-linear-gradient(0deg, rgba(0,0,0,0.22) 0 ${paso / 2}px, transparent ${paso / 2}px ${paso}px);`;
    }
    const grano = Number(v("grano") || 0);
    if (grano > 0) {
      const c = document.createElement("canvas");
      c.width = c.height = 192;
      const g = c.getContext("2d");
      const img = g.createImageData(192, 192);
      let s = 7;
      for (let i = 0; i < img.data.length; i += 4) {
        s = (s * 16807) % 2147483647;
        const n = s % 256;
        img.data[i] = img.data[i + 1] = img.data[i + 2] = n;
        img.data[i + 3] = 255;
      }
      g.putImageData(img, 0, 0);
      const capa = crear("div", "fx-capa", root);
      // grano grueso que cambia 10 veces por segundo (como el de pelicula): si cambiara cada fotograma el video pesaria 5 veces mas
      capa.style.cssText += `z-index:9;opacity:${grano};mix-blend-mode:overlay;background-image:url(${c.toDataURL()});background-size:${Math.round(corto * 0.36)}px;`;
      pintores.push((t) => {
        const f = Math.floor(t * 10);
        capa.style.backgroundPosition = `${(f * 73) % 191}px ${(f * 151) % 191}px`;
      });
    }
  };

  // Subtitulos palabra por palabra (grupos de hasta 3, la que suena resaltada). ESCENA.subtitulos = [[t0, t1, palabra], ...]
  const subtitulos = () => {
    const lista = E.subtitulos || [];
    if (!lista.length) return;
    if (E.presentador) return subtitulosArriba(lista);
    const caja = crear("div", "subs", document.getElementById("root"));
    const tam = corto * (vertical ? 0.068 : 0.062);
    caja.style.cssText += `font-size:${tam}px;top:${H * (vertical ? 0.735 : cuadrado ? 0.8 : 0.83)}px;`;
    const grupos = [];
    let actual = [];
    lista.forEach((w, i) => {
      actual.push(w);
      const sig = lista[i + 1];
      if (actual.length >= 3 || /[.,;:!?…]$/.test(w[2]) || !sig || sig[0] - w[1] > 0.45) {
        grupos.push(actual);
        actual = [];
      }
    });
    let ultimo = "";
    pintores.push((t) => {
      let g = null;
      for (let k = grupos.length - 1; k >= 0; k--) {
        if (t >= grupos[k][0][0] - 0.05) { g = grupos[k]; break; }
      }
      let html = "";
      if (g && t <= g[g.length - 1][1] + 0.5) {
        let activa = 0;
        g.forEach((w, j) => { if (t >= w[0] - 0.03) activa = j; });
        html = g.map((w, j) => `<span class="${j === activa ? "sub-activa" : ""}">${escapar(w[2])}</span>`).join(" ");
      }
      if (html !== ultimo) {
        caja.innerHTML = html;
        ultimo = html;
      }
    });
  };

  // Con presentador: frase entera arriba a la izquierda (hasta ~3 lineas); cada palabra sale en gris claro y se
  // pone de tinta cuando se dice (en 0,2 s). Bloque normal, no flex: si no las palabras pierden los espacios.
  const subtitulosArriba = (lista) => {
    const caja = crear("div", "subs-arriba", document.getElementById("root"));
    const tam = corto * (vertical ? 0.0575 : 0.042);
    caja.style.cssText = `position:absolute;z-index:6;left:${W * (vertical ? 0.111 : 0.05)}px;top:${H * (vertical ? 0.102 : 0.07)}px;` +
      `width:${W * (vertical ? 0.787 : 0.6)}px;font-size:${tam}px;line-height:1.14;font-family:var(--f-subs);font-weight:500;` +
      `color:var(--tinta);text-align:left;`;
    const grupos = [];
    let actual = [];
    lista.forEach((w, i) => {
      actual.push(w);
      const sig = lista[i + 1];
      if (actual.length >= 9 || (actual.length >= 4 && /[.;:!?…]$/.test(w[2])) || !sig || sig[0] - w[1] > 0.6) {
        grupos.push(actual);
        actual = [];
      }
    });
    const gris = "color-mix(in srgb, var(--tinta) 30%, var(--fondo))";
    let ultimo = "";
    pintores.push((t) => {
      let g = null;
      for (let k = grupos.length - 1; k >= 0; k--) {
        if (t >= grupos[k][0][0] - 0.05) { g = grupos[k]; break; }
      }
      let html = "";
      if (g && t <= g[g.length - 1][1] + 0.6) {
        html = g.map((w) => {
          const x = Math.min(1, Math.max(0, (t - w[0]) / 0.2));
          const color = x >= 1 ? "var(--tinta)" : x <= 0 ? gris : `color-mix(in srgb, var(--tinta) ${Math.round(30 + 70 * x)}%, var(--fondo))`;
          return `<span style="color:${color}">${escapar(w[2].replace(/[.]$/, ""))}</span>`;
        }).join(" ");
      }
      if (html !== ultimo) {
        caja.innerHTML = html;
        ultimo = html;
      }
    });
  };

  // Lo que va encima de cualquier escena: el indicador fijo (una cifra que acompana todo el video, arriba) y el
  // cierre de marca (el nombre del canal al final del ultimo plano).
  // ESCENA.indicador = {nombre, antes, despues, desde (null: entra ahora), hasta, a}; ESCENA.marca = {texto, a}
  const encima = () => {
    const root = document.getElementById("root");
    const I = E.indicador;
    let indicador = null;
    if (I) {
      const el = indicador = crear("div", "indicador", root);
      const tam = corto * 0.04;
      el.style.cssText += `font-size:${tam}px;left:50%;top:${H * (vertical ? 0.055 : 0.03)}px;`;
      gsap.set(el, { xPercent: -50 });
      const nombre = crear("span", "indicador-nombre", el);
      nombre.textContent = I.nombre;
      const cifra = crear("span", "indicador-cifra", el);
      const { dec } = aNumero(String(I.hasta));
      const o = { x: I.desde ?? 0 };
      const poner = () => { cifra.textContent = (I.antes || "") + formato(o.x, dec) + (I.despues || ""); };
      poner();
      const a = Math.max(0, I.a || 0);
      if (I.desde == null) {
        tl.fromTo(el, { opacity: 0, y: -tam }, { opacity: 1, y: 0, duration: 0.4, ease: "back.out(2)", immediateRender: true }, a);
      }
      if (I.desde !== I.hasta) {
        tl.to(o, { x: I.hasta, duration: 0.9, ease: "power3.out", onUpdate: poner }, a);
        tl.fromTo(cifra, { scale: 1 }, { keyframes: [{ scale: 1.25, duration: 0.15 }, { scale: 1, duration: 0.35 }] }, a);
      }
    }
    if (E.marca) {
      // cierre: cuando acaba la voz, un velo del color del fondo tapa la escena y la marca sale sola en el centro
      // (asi nunca pisa textos, banderas ni dibujos)
      const a = Math.max(0, E.marca.a);
      const velo = crear("div", "fx-capa", root);
      velo.style.cssText += `z-index:7;background:${v("fondo")};`;
      tl.fromTo(velo, { opacity: 0 }, { opacity: 0.92, duration: 0.35, ease: "power2.out", immediateRender: true }, a);
      const el = crear("div", "marca", root);
      el.textContent = E.marca.texto;
      el.style.cssText += `font-size:${corto * 0.075}px;left:50%;top:${H * 0.45}px;`;
      gsap.set(el, { xPercent: -50, yPercent: -50 });
      tl.fromTo(el, { opacity: 0, scale: 0.6 }, { opacity: 1, scale: 1, duration: 0.45, ease: "back.out(2.2)", immediateRender: true }, a + 0.15);
      if (indicador) tl.to(indicador, { opacity: 0, duration: 0.3 }, a);
    }
  };

  // Ritmo: la entrada de la escena (transicion desde el corte) y los golpes (acercon + sacudida) en los momentos
  // fuertes. Se mueve #escena entero; los subtitulos y el indicador quedan quietos.
  // ESCENA.transicion = "zoom" | "barrido" | "destello" | "giro" | null; ESCENA.impactos = [segundos]
  const ritmo = () => {
    if (E.clip) return;   // sobre verde croma moverlo destaparia el fondo (el recorte fallaria)
    const tr = E.transicion;
    const fin = { scale: 1, xPercent: 0, rotation: 0, opacity: 1, filter: "blur(0px)", duration: 0.34, ease: "power3.out", immediateRender: true };
    if (tr === "zoom") tl.fromTo(escena, { scale: 1.2, filter: "blur(10px)" }, fin, 0);
    else if (tr === "barrido") tl.fromTo(escena, { xPercent: E.lado === -1 ? -28 : 28, opacity: 0.35, filter: "blur(14px)" }, fin, 0);
    else if (tr === "giro") tl.fromTo(escena, { rotation: -7, scale: 1.15, filter: "blur(6px)" }, fin, 0);
    else if (tr === "destello") {
      const luz = crear("div", "fx-capa", document.getElementById("root"));
      luz.style.cssText += "z-index:9;background:#fff;";
      tl.fromTo(luz, { opacity: 0.8 }, { opacity: 0, duration: 0.3, ease: "power2.out", immediateRender: true }, 0);
    }
    if (tr === "puntos") tintaPuntos(0, false);
    if (E.salida === "puntos") tintaPuntos(D - 0.45, true);
    for (const t of E.impactos || []) {
      if (t < 0.4) continue;   // pegado a la entrada no se nota
      tl.to(escena, { keyframes: [{ scale: 1.06, duration: 0.06, ease: "power2.out" }, { scale: 1, duration: 0.3, ease: "power2.inOut" }] }, t);
      tl.to(escena, { x: corto * 0.012, duration: 0.04, repeat: 5, yoyo: true, ease: "none" }, t);
    }
  };

  // Cortinilla de puntos de tinta: 13x23 puntos que crecen del centro hacia fuera hasta tapar la pantalla (al final
  // de una escena, crece = true) y se encogen al empezar la siguiente. 0,45 s cada mitad.
  const tintaPuntos = (t, crece) => {
    const cols = vertical ? 13 : 23, filas = vertical ? 23 : 13;
    const capa = crear("div", "fx-capa", document.getElementById("root"));
    capa.style.cssText += "z-index:9;";
    const paso = Math.max(W / cols, H / filas), tam = paso * 1.5;
    const puntos = [];
    for (let f = 0; f < filas; f++) {
      for (let c = 0; c < cols; c++) {
        const p = crear("div", "", capa);
        const x = (c + 0.5) * W / cols, y = (f + 0.5) * H / filas;
        p.style.cssText = `position:absolute;left:${x - tam / 2}px;top:${y - tam / 2}px;width:${tam}px;height:${tam}px;` +
          `border-radius:50%;background:var(--tinta);transform:scale(${crece ? 0 : 1});`;
        puntos.push([p, Math.hypot(c - (cols - 1) / 2, f - (filas - 1) / 2)]);
      }
    }
    const lejos = Math.max(...puntos.map((q) => q[1]));
    for (const [p, d] of puntos) {
      const r = (crece ? d : lejos - d) / lejos * 0.2;
      tl.fromTo(p, { scale: crece ? 0 : 1 }, { scale: crece ? 1 : 0, duration: 0.25, ease: crece ? "power2.in" : "power2.out", immediateRender: true }, Math.max(0, t + r));
    }
  };

  // Extras encima de cualquier escena (fuera de #escena: no se mueven con la transicion): un emoji que salta en una
  // esquina, un sello que cae de golpe o una flecha que se dibuja hacia el centro con su texto.
  // ESCENA.extras = [{tipo: "emoji" | "sello" | "flecha", emoji?, texto?, a}]
  const extras = () => {
    const root = document.getElementById("root");
    (E.extras || []).forEach((x, k) => {
      const a = Math.max(0, x.a ?? 0.5);
      if (x.tipo === "emoji") {
        const el = crear("div", "", root);
        el.textContent = x.emoji;
        const tam = corto * 0.17, der = k % 2 === 0;
        el.style.cssText = `position:absolute;z-index:6;font-size:${tam}px;line-height:1;top:${zona.y + zona.h * 0.02}px;` +
          (der ? `right:${W - zona.x - zona.w}px;` : `left:${zona.x}px;`) +
          `font-family:"Segoe UI Emoji","Noto Color Emoji","Apple Color Emoji",sans-serif;filter:drop-shadow(0 0.05em 0.08em rgba(0,0,0,0.45));`;
        tl.fromTo(el, { opacity: 0, scale: 0, rotation: der ? 30 : -30 }, { opacity: 1, scale: 1, rotation: der ? 8 : -8, duration: 0.45, ease: "back.out(3)", immediateRender: true }, a);
        const vueltas = Math.floor((D - a - 0.5) / 0.5);
        if (vueltas > 0) tl.to(el, { y: -tam * 0.1, duration: 0.5, repeat: vueltas, yoyo: true, ease: "sine.inOut" }, a + 0.45);
      } else if (x.tipo === "sello") {
        const el = crear("div", "", root);
        el.textContent = x.texto;
        // con presentador va en el hueco libre de abajo a la izquierda, junto a el (en la zona taparia el titulo o la cifra)
        const plano = v("sello-fuente");   // el estilo puede pedir su letra y un sello plano (sin fondo ni sombra)
        el.style.cssText = `position:absolute;z-index:6;white-space:nowrap;` +
          (E.presentador ? (vertical ? `left:${W * 0.2}px;top:${H * 0.74}px;` : `left:${W * 0.72}px;top:${H * 0.16}px;`) : `left:${W / 2}px;top:${zona.y + zona.h * 0.6}px;`) +
          `font-family:${plano || '"Montserrat",sans-serif'};font-weight:900;text-transform:uppercase;letter-spacing:0.04em;color:${v("acento") && plano ? v("acento") : "#e8312f"};` +
          `border:${plano ? "5px" : "0.09em"} solid currentColor;border-radius:0.12em;padding:0.05em 0.35em;` +
          (plano ? "background:transparent;" : "background:rgba(255,255,255,0.88);box-shadow:0 0.1em 0.4em rgba(0,0,0,0.35);");
        ajustar(el, E.presentador ? W * 0.3 : zona.w * 0.85, corto * 0.2, corto * (E.presentador ? 0.09 : 0.12));
        gsap.set(el, { xPercent: -50, yPercent: -50 });
        tl.fromTo(el, { opacity: 0, scale: 2.6, rotation: -4 }, { opacity: 1, scale: 1, rotation: plano ? -6 : -11, duration: 0.24, ease: "power4.in", immediateRender: true }, a);
      } else if (x.tipo === "flecha") {
        // de abajo a la derecha hacia el centro de la zona, con el texto en la cola
        const s = corto * 0.34;
        const caja = crear("div", "", root);
        caja.style.cssText = `position:absolute;z-index:6;width:${s}px;height:${s}px;left:${zona.x + zona.w - s * 0.95}px;top:${zona.y + zona.h - s * 0.85}px;`;
        const ns = "http://www.w3.org/2000/svg";
        const svg = document.createElementNS(ns, "svg");
        svg.setAttribute("viewBox", "0 0 100 100");
        svg.style.cssText = "width:100%;height:100%;overflow:visible;filter:drop-shadow(0 0.4vmin 0.5vmin rgba(0,0,0,0.45));";
        caja.appendChild(svg);
        const trazo = (d) => {
          const p = document.createElementNS(ns, "path");
          Object.entries({ d, fill: "none", "stroke-width": 7, "stroke-linecap": "round", "stroke-linejoin": "round", pathLength: 1 })
            .forEach(([k2, v2]) => p.setAttribute(k2, v2));
          p.style.stroke = v("acento") || "#ffd447";
          p.style.strokeDasharray = 1;
          svg.appendChild(p);
          return p;
        };
        const cuerpo = trazo("M 82 88 Q 78 30 18 16");
        const punta = trazo("M 36 6 L 18 16 L 34 30");
        tl.fromTo(cuerpo, { strokeDashoffset: 1 }, { strokeDashoffset: 0, duration: 0.4, ease: "power2.out", immediateRender: true }, a);
        tl.fromTo(punta, { strokeDashoffset: 1 }, { strokeDashoffset: 0, duration: 0.15, ease: "none", immediateRender: true }, a + 0.38);
        if (x.texto) {
          const t = crear("div", "golpe", caja);
          t.textContent = x.texto;
          // a la izquierda de la cola (debajo estan los subtitulos)
          t.style.cssText += `left:${-s * 1.05}px;width:${s}px;top:${s * 0.55}px;text-align:right;color:#fff;-webkit-text-stroke:0.07em #111;`;
          ajustar(t, s, s * 0.4, corto * 0.065);
          tl.fromTo(t, { opacity: 0, scale: 0.6 }, { opacity: 1, scale: 1, duration: 0.3, ease: "back.out(2.5)", immediateRender: true }, a + 0.1);
        }
      }
    });
  };

  // Imagenes (satelite, pegatinas, banderas): la escena no se da por montada hasta que todas han cargado.
  const cargas = [];
  const imagen = (src) => {
    const img = new Image();
    cargas.push(new Promise((ok) => { img.onload = ok; img.onerror = ok; }));
    img.src = src;
    return img;
  };

  // La escena se monta cuando estan las fuentes (para medir textos bien) y la linea de tiempo se registra
  // cuando han cargado sus imagenes.
  const montar = (fn) => {
    // fonts.ready no espera a fuentes que aun no se han pedido (la pagina empieza sin texto): se cargan todas
    // antes de medir, si no los textos se miden con la letra de repuesto y luego no caben (se pisan)
    Promise.all([...document.fonts].map((f) => f.load().catch(() => null))).then(() => document.fonts.ready).then(() => {
      fn();
      return Promise.all(cargas);
    }).then(() => {
      ritmo();
      extras();
      encima();
      if (window.F.presentador) window.F.presentador();
      subtitulos();
      acabado();
      tl.set({}, {}, D);  // que la linea de tiempo dure toda la escena
      window.__timelines = window.__timelines || {};
      window.__timelines.main = tl;
      if (window.__hfForceTimelineRebind) window.__hfForceTimelineRebind();
      pintores.forEach((p) => p(0));
    });
  };

  window.F = { W, H, D, E, v, corto, vertical, cuadrado, zona, tl, escena, crear, escapar, marcar, enPalabras, ajustar, entrar,
               formato, aNumero, contar, fondo, texturaMapa, montar, imagen, alPintar: (fn) => pintores.push(fn) };
})();
