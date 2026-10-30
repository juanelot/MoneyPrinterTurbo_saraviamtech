// Escena CAPTURA: algo de una pantalla que todos reconocen (un tuit, un titular, notificaciones del movil, un chat,
// una busqueda). Va con colores de app (claros), no los del estilo, para que parezca de verdad.
// ESCENA = { forma: "tuit" | "noticia" | "notificacion" | "chat" | "busqueda", nombre, usuario, contenido, cifra,
//            a (cuando pasa lo principal), mensajes: [{texto, mio, a}] }
F.montar(() => {
  const E = F.E;
  F.fondo();
  const z = F.zona, c = F.corto;
  const a = Math.max(0, E.a ?? 0.3);
  const ui = "font-family:'Inter','Segoe UI',Arial,sans-serif;color:#0f1419;";
  const caja = F.crear("div");
  caja.style.cssText = `position:absolute;left:${z.x}px;top:${z.y}px;width:${z.w}px;height:${z.h}px;display:flex;flex-direction:column;` +
    `justify-content:center;align-items:center;gap:${c * 0.025}px;`;
  const tarjeta = (padre = caja) => {
    const t = F.crear("div", "", padre);
    t.style.cssText = `${ui}background:#fff;border-radius:${c * 0.035}px;box-shadow:0 ${c * 0.02}px ${c * 0.06}px rgba(0,0,0,0.35);` +
      `padding:${c * 0.04}px;width:100%;box-sizing:border-box;`;
    return t;
  };
  const avatar = (padre, nombre, tam) => {
    const av = F.crear("div", "", padre);
    av.textContent = (nombre || "?").trim().charAt(0).toUpperCase();
    av.style.cssText = `width:${tam}px;height:${tam}px;border-radius:50%;flex:none;display:flex;align-items:center;justify-content:center;` +
      `background:var(--acento);color:#fff;font-weight:800;font-size:${tam * 0.5}px;`;
    return av;
  };
  const entra = (el, t) => F.tl.fromTo(el, { opacity: 0, y: c * 0.06, scale: 0.94 }, { opacity: 1, y: 0, scale: 1, duration: 0.45, ease: "back.out(1.7)", immediateRender: true }, t);

  if (E.forma === "tuit") {
    const t = tarjeta();
    const cab = F.crear("div", "", t);
    cab.style.cssText = `display:flex;align-items:center;gap:${c * 0.025}px;margin-bottom:${c * 0.03}px;`;
    avatar(cab, E.nombre, c * 0.12);
    const quien = F.crear("div", "", cab);
    quien.innerHTML = `<div style="font-weight:800;font-size:${c * 0.05}px">${F.escapar(E.nombre)} <span style="color:#1d9bf0">✔</span></div>` +
      `<div style="color:#536471;font-size:${c * 0.04}px">@${F.escapar((E.usuario || E.nombre || "").replace(/^@/, "").replace(/\s+/g, "").toLowerCase())}</div>`;
    const txt = F.crear("div", "", t);
    txt.innerHTML = F.marcar(E.contenido);
    txt.style.cssText = "font-weight:500;line-height:1.3;";
    F.ajustar(txt, z.w - c * 0.08, z.h * 0.45, c * 0.07);
    const pie = F.crear("div", "", t);
    pie.style.cssText = `display:flex;gap:${c * 0.06}px;margin-top:${c * 0.035}px;color:#536471;font-size:${c * 0.042}px;font-weight:600;`;
    pie.innerHTML = `<span>💬 ${Math.max(1, Math.round(F.aNumero(E.cifra || "1000").n / 9))}</span><span>🔁 ${Math.max(1, Math.round(F.aNumero(E.cifra || "1000").n / 4))}</span>`;
    const likes = F.crear("span", "", pie);
    likes.style.color = "#f91880";
    entra(t, 0);
    F.contar(likes, E.cifra || "1000", a, 1.4, "❤ ");
    F.tl.fromTo(likes, { scale: 1 }, { keyframes: [{ scale: 1.35, duration: 0.15 }, { scale: 1, duration: 0.35 }] }, a);
  } else if (E.forma === "noticia") {
    const t = tarjeta();
    t.style.padding = "0";
    t.style.overflow = "hidden";
    const medio = F.crear("div", "", t);
    medio.textContent = E.nombre || "ÚLTIMA HORA";
    medio.style.cssText = `background:#c8102e;color:#fff;font-weight:900;letter-spacing:0.08em;text-transform:uppercase;` +
      `font-size:${c * 0.045}px;padding:${c * 0.025}px ${c * 0.04}px;`;
    const cuerpo = F.crear("div", "", t);
    cuerpo.style.cssText = `padding:${c * 0.04}px;`;
    const titular = F.crear("div", "", cuerpo);
    titular.innerHTML = F.enPalabras(E.contenido);
    titular.style.cssText = "font-family:'Playfair Display',Georgia,serif;font-weight:800;line-height:1.12;";
    F.ajustar(titular, z.w - c * 0.08, z.h * 0.5, c * 0.085);
    for (const w of [0.95, 0.8, 0.6]) {
      const l = F.crear("div", "", cuerpo);
      l.style.cssText = `height:${c * 0.018}px;width:${w * 100}%;background:#e6e6e6;border-radius:9px;margin-top:${c * 0.025}px;`;
    }
    entra(t, 0);
    // al decirlo, el titular se subraya con rotulador
    const resalte = `linear-gradient(transparent 58%, color-mix(in srgb, var(--acento) 55%, transparent) 58%)`;
    titular.querySelectorAll(".pal").forEach((p, k) => {
      p.style.backgroundImage = resalte;
      p.style.backgroundRepeat = "no-repeat";
      F.tl.fromTo(p, { backgroundSize: "0% 100%" }, { backgroundSize: "100% 100%", duration: 0.12, ease: "none", immediateRender: true }, a + k * 0.06);
    });
  } else if (E.forma === "busqueda") {
    const t = tarjeta();
    t.style.cssText += `border-radius:999px;display:flex;align-items:center;gap:${c * 0.03}px;padding:${c * 0.035}px ${c * 0.05}px;`;
    const lupa = F.crear("div", "", t);
    lupa.textContent = "🔍";
    lupa.style.fontSize = c * 0.06 + "px";
    const txt = F.crear("div", "", t);
    txt.style.cssText = `flex:1;min-width:0;font-weight:500;white-space:nowrap;overflow:hidden;`;
    const todo = E.contenido || "";
    txt.textContent = todo;
    F.ajustar(txt, txt.clientWidth - c * 0.04, c * 0.12, c * 0.065);   // deja sitio al cursor
    txt.textContent = "";
    const cursor = F.crear("span", "", t);
    cursor.textContent = "|";
    cursor.style.cssText = `font-weight:300;font-size:${c * 0.06}px;color:#1a73e8;margin-left:-${c * 0.02}px;`;
    entra(t, 0);
    // se escribe letra a letra desde el principio hasta que se dice
    const o = { n: 0 };
    const fin = Math.max(0.6, a);
    F.tl.to(o, { n: todo.length, duration: Math.max(0.5, fin - 0.2), ease: "none", onUpdate: () => { txt.textContent = todo.slice(0, Math.round(o.n)); } }, 0.2);
    F.alPintar((tt) => { cursor.style.opacity = Math.floor(tt * 2.5) % 2 ? 0 : 1; });
    // resultados que aparecen debajo
    for (let k = 0; k < 3; k++) {
      const r = tarjeta();
      r.style.cssText += `padding:${c * 0.03}px ${c * 0.04}px;border-radius:${c * 0.025}px;`;
      r.innerHTML = `<div style="height:${c * 0.03}px;width:${70 - k * 12}%;background:#1a0dab33;border-radius:9px"></div>` +
        `<div style="height:${c * 0.02}px;width:90%;background:#e6e6e6;border-radius:9px;margin-top:${c * 0.02}px"></div>`;
      entra(r, fin + 0.15 + k * 0.12);
    }
  } else {
    // notificacion o chat: van llegando de una en una
    const chat = E.forma === "chat";
    const mensajes = (E.mensajes || []).slice(0, chat ? 5 : 3);
    if (chat) {
      const cab = F.crear("div", "", caja);
      cab.style.cssText = `${ui}width:100%;display:flex;align-items:center;gap:${c * 0.025}px;background:#075e54;color:#fff;` +
        `border-radius:${c * 0.03}px;padding:${c * 0.025}px ${c * 0.035}px;box-sizing:border-box;`;
      avatar(cab, E.nombre, c * 0.09);
      const n = F.crear("div", "", cab);
      n.innerHTML = `<div style="font-weight:800;font-size:${c * 0.048}px">${F.escapar(E.nombre || "Chat")}</div>` +
        `<div style="font-size:${c * 0.032}px;opacity:0.8">en línea</div>`;
      entra(cab, 0);
    }
    const alto = z.h * (chat ? 0.78 : 0.95) / Math.max(mensajes.length, 1);
    mensajes.forEach((m, k) => {
      const t = Math.max(0, m.a ?? 0.3 + k * 0.9);
      if (chat) {
        const fila = F.crear("div", "", caja);
        fila.style.cssText = `width:100%;display:flex;justify-content:${m.mio ? "flex-end" : "flex-start"};`;
        const b = F.crear("div", "", fila);
        b.innerHTML = F.marcar(m.texto);
        b.style.cssText = `${ui}max-width:82%;background:${m.mio ? "#d9fdd3" : "#fff"};border-radius:${c * 0.03}px;` +
          `${m.mio ? "border-top-right-radius" : "border-top-left-radius"}:0;padding:${c * 0.02}px ${c * 0.03}px;font-weight:500;line-height:1.25;` +
          `box-shadow:0 ${c * 0.006}px ${c * 0.015}px rgba(0,0,0,0.25);`;
        F.ajustar(b, z.w * 0.82, alto * 0.85, c * 0.055);
        F.tl.fromTo(b, { opacity: 0, scale: 0.5, transformOrigin: m.mio ? "100% 100%" : "0% 100%" }, { opacity: 1, scale: 1, duration: 0.35, ease: "back.out(2)", immediateRender: true }, t);
      } else {
        const n = tarjeta();
        n.style.cssText += `background:rgba(245,245,247,0.96);display:flex;gap:${c * 0.03}px;align-items:center;padding:${c * 0.03}px;`;
        const ic = F.crear("div", "", n);
        ic.textContent = "🔔";
        ic.style.cssText = `width:${c * 0.1}px;height:${c * 0.1}px;border-radius:${c * 0.025}px;background:var(--acento);flex:none;` +
          `display:flex;align-items:center;justify-content:center;font-size:${c * 0.055}px;`;
        const txt = F.crear("div", "", n);
        txt.style.cssText = "flex:1;min-width:0;";
        txt.innerHTML = `<div style="display:flex;justify-content:space-between;font-size:${c * 0.034}px;color:#6e6e73;font-weight:600;text-transform:uppercase">` +
          `<span>${F.escapar(E.nombre || "Aviso")}</span><span>ahora</span></div>`;
        const cuerpo = F.crear("div", "", txt);
        cuerpo.innerHTML = F.marcar(m.texto);
        cuerpo.style.cssText = "font-weight:600;line-height:1.2;margin-top:0.15em;";
        F.ajustar(cuerpo, cuerpo.clientWidth, alto * 0.6, c * 0.05);
        F.tl.fromTo(n, { opacity: 0, y: -c * 0.15 }, { opacity: 1, y: 0, duration: 0.45, ease: "back.out(1.6)", immediateRender: true }, t);
      }
    });
  }
  F.deriva(caja);
});
