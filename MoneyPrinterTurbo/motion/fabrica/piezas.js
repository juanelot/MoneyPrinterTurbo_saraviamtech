// Piezas de la Fabrica que van encima del mapa: banderas (con ojos o sin ellos), pegatinas (personajes y objetos
// de juguete), medidas ("14 km"), rutas con flecha (y una pegatina que viaja), circulos y la frase de golpe.
// Cada una entra en su segundo `a` y se va en `b` (si lo trae). Las que van pegadas a un sitio usan mapa.pieza:
// el contenedor sigue a la camara y el elemento de dentro es el que se anima.
(() => {
  const { corto } = F;

  // contenedor de tamano 0 en el punto del mapa; el hijo se coloca respecto a el (centrado o de pie)
  const anclado = (mapa, lon, lat, clase, ancla = "centro", dx = 0, dy = 0) => {
    const caja = F.crear("div", "pieza", F.escena);
    const el = F.crear("div", clase, caja);
    el.style.transform = ancla === "pie" ? "translate(-50%, -100%)" : "translate(-50%, -50%)";
    mapa.pieza(caja, lon, lat, dx * corto, dy * corto);
    return { caja, el };
  };

  // entrada con rebote y vaiven suave mientras esta (nunca quieta del todo)
  const vida = (el, a, b, fase = 0) => {
    F.tl.fromTo(el, { scale: 0, rotation: -10 }, { scale: 1, rotation: 0, duration: 0.55, ease: "back.out(2.4)", immediateRender: true }, Math.max(0, a));
    F.alPintar((t) => {
      if (t < a + 0.55) return;
      const s = t - a + fase;
      el.style.translate = `0 ${(Math.sin(s * 2.4) * corto * 0.004).toFixed(2)}px`;
      el.style.rotate = `${(Math.sin(s * 1.7) * 2).toFixed(2)}deg`;
    });
    if (b != null && b < F.D) F.tl.to(el, { scale: 0, duration: 0.3, ease: "back.in(2)" }, b);
  };

  // Bandera (svg de country-flag-icons, 3:2) con borde blanco; con ojos que miran a los lados y parpadean.
  F.bandera = (mapa, { src, lon, lat, a = 0, b, ojos = false, tam = 1, dx = 0, dy = 0 }) => {
    const { el } = anclado(mapa, lon, lat, "bandera", "centro", dx, dy);
    const ancho = corto * 0.12 * tam;
    el.style.cssText += `width:${ancho}px;height:${ancho / 1.5}px;font-size:${corto * 0.05}px;`;
    const img = F.crear("img", "", el);
    img.src = src;
    F.imagen(src);
    if (ojos) {
      const cara = F.crear("div", "ojos", el);
      const pupilas = [0, 1].map(() => F.crear("div", "", F.crear("div", "ojo", cara)));
      const fase = (lon * 7 + lat * 3) % 5;
      F.alPintar((t) => {
        const mira = Math.sin((t + fase) * 0.9) > 0.35 ? 1 : Math.sin((t + fase) * 0.9) < -0.35 ? -1 : 0;
        const parpadeo = ((t + fase) % 3.1) < 0.12;
        for (const p of pupilas) {
          p.style.transform = `translate(${mira * 28}%, 8%)`;
          p.parentElement.style.transform = parpadeo ? "scaleY(0.1)" : "none";
        }
      });
    }
    vida(el, a, b, lon);
    return el;
  };

  // Pegatina de pie sobre su sitio (o al lado: dx/dy en fracciones del lado corto).
  F.pegatina = (mapa, { src, lon, lat, a = 0, b, tam = 1, dx = 0, dy = 0, espejo = false }) => {
    const { el } = anclado(mapa, lon, lat, "pegatina", "pie", dx, dy);
    const img = F.crear("img", "", el);
    img.src = src;
    F.imagen(src);
    img.style.height = corto * 0.26 * tam + "px";
    if (espejo) img.style.transform = "scaleX(-1)";
    el.style.transformOrigin = "50% 100%";
    vida(el, a, b, lat);
    return el;
  };

  // Circulo que late alrededor de un sitio (una ciudad, un estrecho).
  F.circulo = (mapa, { lon, lat, a = 0, b, tam = 1 }) => {
    const { el } = anclado(mapa, lon, lat, "circulo");
    const d = corto * 0.13 * tam;
    el.style.cssText += `width:${d}px;height:${d}px;`;
    F.tl.fromTo(el, { scale: 2.2, opacity: 0 }, { scale: 1, opacity: 1, duration: 0.45, ease: "power3.out", immediateRender: true }, Math.max(0, a));
    F.alPintar((t) => {
      if (t > a + 0.45) el.style.scale = (1 + Math.sin((t - a) * 5) * 0.06).toFixed(3);
    });
    if (b != null && b < F.D) F.tl.to(el, { opacity: 0, duration: 0.3 }, b);
  };

  const fuera = (x, y) => x < -corto || y < -corto || x > F.W + corto || y > F.H + corto;

  // Medida entre dos puntos: linea discontinua con topes que se estira, y el texto encima, en su angulo.
  F.medida = (mapa, { desde, hasta, texto, a = 0, b }) => {
    const o = { p: 0, t: 0 };
    F.tl.to(o, { p: 1, duration: 0.7, ease: "power2.inOut" }, Math.max(0, a));
    F.tl.to(o, { t: 1, duration: 0.35, ease: "back.out(2)" }, Math.max(0, a) + 0.45);
    if (b != null && b < F.D) F.tl.to(o, { p: 0, t: 0, duration: 0.3 }, b);
    const grosor = corto * 0.006, tope = corto * 0.02, letra = corto * 0.055;
    mapa.trazo((aPx) => {
      if (o.p <= 0.001) return "";
      const [x0, y0] = aPx(desde[0], desde[1]);
      const [x1f, y1f] = aPx(hasta[0], hasta[1]);
      if (fuera(x0, y0) && fuera(x1f, y1f)) return "";
      const x1 = x0 + (x1f - x0) * o.p, y1 = y0 + (y1f - y0) * o.p;
      let ang = Math.atan2(y1f - y0, x1f - x0) * 180 / Math.PI;
      const nx = -Math.sin(ang * Math.PI / 180) * tope, ny = Math.cos(ang * Math.PI / 180) * tope;
      if (ang > 90) ang -= 180;
      if (ang < -90) ang += 180;
      const mx = (x0 + x1f) / 2, my = (y0 + y1f) / 2;
      const linea = `stroke="#fff" stroke-width="${grosor}" stroke-linecap="round"`;
      const sombra = `stroke="rgba(0,0,0,0.45)" stroke-width="${grosor * 2.2}" stroke-linecap="round"`;
      let s = `<line x1="${x0}" y1="${y0}" x2="${x1}" y2="${y1}" ${sombra} stroke-dasharray="${grosor * 3} ${grosor * 2.4}"/>`;
      s += `<line x1="${x0}" y1="${y0}" x2="${x1}" y2="${y1}" ${linea} stroke-dasharray="${grosor * 3} ${grosor * 2.4}"/>`;
      s += `<line x1="${x0 - nx}" y1="${y0 - ny}" x2="${x0 + nx}" y2="${y0 + ny}" ${linea}/>`;
      if (o.p > 0.98) s += `<line x1="${x1f - nx}" y1="${y1f - ny}" x2="${x1f + nx}" y2="${y1f + ny}" ${linea}/>`;
      if (o.t > 0.01) {
        s += `<g transform="translate(${mx} ${my}) rotate(${ang}) translate(0 ${-letra * 0.55}) scale(${o.t})">` +
          `<text text-anchor="middle" dominant-baseline="middle" font-family="Montserrat" font-weight="900" font-size="${letra}" ` +
          `fill="#ffd84a" stroke="#1d1a14" stroke-width="${letra * 0.16}" paint-order="stroke">${F.escapar(texto)}</text></g>`;
      }
      return s;
    });
  };

  // Ruta curva de A a B que se dibuja con punta de flecha; una pegatina puede ir montada en la punta.
  F.ruta = (mapa, { desde, hasta, a = 0, dur = 1.6, b, color = "#ffffff", src = null, curva = 0.22 }) => {
    const o = { p: 0, v: 1 };
    F.tl.to(o, { p: 1, duration: dur, ease: "power1.inOut" }, Math.max(0, a));
    if (b != null && b < F.D) F.tl.to(o, { v: 0, duration: 0.3 }, b);
    let viajero = null;
    if (src) {
      viajero = F.crear("div", "pegatina", F.escena);
      viajero.style.cssText += "transform:translate(-50%,-80%);visibility:hidden;";
      const img = F.crear("img", "", viajero);
      img.src = src;
      F.imagen(src);
      img.style.height = corto * 0.15 + "px";
    }
    const grosor = corto * 0.007;
    mapa.trazo((aPx) => {
      if (viajero) viajero.style.visibility = o.p > 0.001 && o.v > 0.01 ? "visible" : "hidden";
      if (o.p <= 0.001 || o.v <= 0.01) return "";
      const [x0, y0] = aPx(desde[0], desde[1]);
      const [x2, y2] = aPx(hasta[0], hasta[1]);
      // control de la curva: a un lado de la recta (siempre hacia arriba de la pantalla)
      const dx = x2 - x0, dy = y2 - y0;
      let nx = -dy, ny = dx;
      if (ny > 0) { nx = -nx; ny = -ny; }
      const cx = (x0 + x2) / 2 + nx * curva, cy = (y0 + y2) / 2 + ny * curva;
      const punto = (u) => [(1 - u) ** 2 * x0 + 2 * (1 - u) * u * cx + u * u * x2, (1 - u) ** 2 * y0 + 2 * (1 - u) * u * cy + u * u * y2];
      const pts = [];
      const n = 48;
      for (let i = 0; i <= n; i++) pts.push(punto((i / n) * o.p));
      const d = "M" + pts.map(([x, y]) => `${x.toFixed(1)},${y.toFixed(1)}`).join("L");
      const [xa, ya] = pts[pts.length - 2], [xb, yb] = pts[pts.length - 1];
      const ang = Math.atan2(yb - ya, xb - xa), f = grosor * 3.2;
      const flecha = `M${xb + Math.cos(ang) * f},${yb + Math.sin(ang) * f}L${xb + Math.cos(ang + 2.4) * f},${yb + Math.sin(ang + 2.4) * f}` +
        `L${xb + Math.cos(ang - 2.4) * f},${yb + Math.sin(ang - 2.4) * f}Z`;
      if (viajero) {
        viajero.style.left = xb + "px";
        viajero.style.top = yb + "px";
        viajero.querySelector("img").style.transform = Math.cos(ang) < 0 ? "scaleX(-1)" : "none";
      }
      return `<g opacity="${o.v}"><path d="${d}" fill="none" stroke="rgba(0,0,0,0.4)" stroke-width="${grosor * 2.2}" stroke-linecap="round"/>` +
        `<path d="${d}" fill="none" stroke="${color}" stroke-width="${grosor}" stroke-linecap="round"/>` +
        (viajero ? "" : `<path d="${flecha}" fill="${color}" stroke="rgba(0,0,0,0.4)" stroke-width="${grosor * 0.5}"/>`) + "</g>";
    });
  };

  // Frase de golpe ("PARA SIEMPRE"): roja con borde blanco, entra como un sello y tiembla un instante.
  F.golpe = ({ texto, a = 0, b }, caja = F.zona) => {
    const el = F.crear("div", "golpe");
    el.textContent = texto;
    el.style.left = caja.x + "px";
    el.style.width = caja.w + "px";
    el.style.top = caja.y + "px";
    F.ajustar(el, caja.w, caja.h * 0.3, corto * 0.15);
    F.tl.fromTo(el, { opacity: 0, scale: 1.9, rotation: -9 }, { opacity: 1, scale: 1, rotation: -4, duration: 0.32, ease: "power4.out", immediateRender: true }, Math.max(0, a));
    F.tl.to(el, { x: corto * 0.008, duration: 0.05, repeat: 5, yoyo: true, ease: "none" }, Math.max(0, a) + 0.32);
    if (b != null && b < F.D) F.tl.to(el, { opacity: 0, scale: 0.8, duration: 0.25 }, b);
    return el;
  };
})();
