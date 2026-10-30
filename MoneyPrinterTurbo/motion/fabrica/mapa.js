// Mapa de la Fabrica: Mercator propio sobre los paises de Natural Earth (datos/paises.js, dominio publico).
// La camara va en coordenadas Mercator {x, y} (0..1 todo el mundo) y zoom z: el mundo mide S * 2^z px de ancho.
// Una "toma" es {bbox: [oeste, sur, este, norte]} (se encuadra sola en la zona libre) o {lon, lat, z}.
// Con satelite (opciones.satelite = [{src, x0, y0, x1, y1}], de lejos a cerca, los prepara Python) se pinta la
// foto en vez del mar y la tierra; los paises van encima translucidos. Rios: datos/rios.js (Natural Earth).
(() => {
  const { W, H, v, corto } = F;
  const P = window.PAISES;
  const S = corto * 0.9;
  const DERIVA = 0.05;  // la camara sigue acercandose despacio cuando ya ha llegado (zoom por segundo); Python usa lo mismo
  const mx = (lon) => (lon + 180) / 360;
  const my = (lat) => {
    const s = Math.sin(Math.max(-85, Math.min(85, lat)) * Math.PI / 180);
    return 0.5 - Math.log((1 + s) / (1 - s)) / (4 * Math.PI);
  };
  // caja de cada pais (para no dibujar lo que no se ve)
  for (const iso in P) {
    let x0 = 1, x1 = 0, y0 = 1, y1 = 0;
    for (const r of P[iso].r) for (const [lon, lat] of r) {
      const x = mx(lon), y = my(lat);
      if (x < x0) x0 = x; if (x > x1) x1 = x; if (y < y0) y0 = y; if (y > y1) y1 = y;
    }
    P[iso].caja = [x0, y0, x1, y1];
  }

  const crearMapa = (padre, zonaLibre, opciones = {}) => {
    const lienzo = F.crear("canvas", "fx-capa", padre);
    lienzo.width = W;
    lienzo.height = H;
    const ctx = lienzo.getContext("2d");
    ctx.imageSmoothingQuality = "high";
    const cam = { x: 0.5, y: 0.5, z: 1 };
    const capas = [];      // {iso, color, o: {a: 0..1}}
    const puntos = [];     // {el, lon, lat, dx, dy, punto, o}
    const piezas = [];     // {el, lon, lat, dx, dy}: banderas y pegatinas pegadas a un sitio
    const rios = [];       // {lineas, color, o: {a, p}}
    const trazos = [];     // fn(aPx): lo que se dibuja en la capa SVG (medidas y rutas)
    const sat = (opciones.satelite || []).map((m) => ({ ...m, img: F.imagen(m.src) }));
    if (sat.length) padre.classList.add("sat");
    else F.texturaMapa(padre);  // justo encima del lienzo y debajo de rotulos y piezas
    const colores = { mar: v("mar"), tierra: v("tierra"), borde: v("borde"), tinta: v("tinta"), alfa: Number(v("pais-alfa") || 0.85) };

    const k = () => S * 2 ** cam.z;
    const aPx = (lon, lat) => [W / 2 + (mx(lon) - cam.x) * k(), H / 2 + (my(lat) - cam.y) * k()];

    // Encuadre de una toma dentro de la zona libre (deja aire alrededor).
    const encuadre = (toma, zl = zonaLibre) => {
      if (toma.bbox) {
        const [o, s, e, n] = toma.bbox;
        const bx0 = mx(o), bx1 = mx(e), by0 = my(n), by1 = my(s);
        const aire = toma.aire ?? 0.78;
        const z = Math.log2(Math.min((zl.w * aire) / (Math.max(bx1 - bx0, 1e-4) * S), (zl.h * aire) / (Math.max(by1 - by0, 1e-4) * S)));
        const zz = Math.max(0.2, Math.min(toma.zmax ?? 7.5, z));
        const kk = S * 2 ** zz;
        return { x: (bx0 + bx1) / 2 - (zl.x + zl.w / 2 - W / 2) / kk, y: (by0 + by1) / 2 - (zl.y + zl.h / 2 - H / 2) / kk, z: zz };
      }
      return { x: mx(toma.lon), y: my(toma.lat), z: toma.z ?? 3 };
    };

    const trazar = (iso) => {
      for (const r of P[iso].r) {
        let [x, y] = aPx(r[0][0], r[0][1]);
        ctx.moveTo(x, y);
        for (let i = 1; i < r.length; i++) {
          [x, y] = aPx(r[i][0], r[i][1]);
          ctx.lineTo(x, y);
        }
        ctx.closePath();
      }
    };
    const seVe = (iso) => {
      const [x0, y0, x1, y1] = P[iso].caja, kk = k();
      return !(W / 2 + (x1 - cam.x) * kk < 0 || W / 2 + (x0 - cam.x) * kk > W || H / 2 + (y1 - cam.y) * kk < 0 || H / 2 + (y0 - cam.y) * kk > H);
    };

    // Foto de satelite: solo desde el mosaico mas lejano que ya cubre toda la pantalla (los de debajo no se ven).
    const pintarSatelite = () => {
      const kk = k();
      const rect = (m) => [W / 2 + (m.x0 - cam.x) * kk, H / 2 + (m.y0 - cam.y) * kk, (m.x1 - m.x0) * kk, (m.y1 - m.y0) * kk];
      let desde = 0;
      for (let i = sat.length - 1; i >= 0; i--) {
        const [x, y, w, h] = rect(sat[i]);
        if (x <= 0 && y <= 0 && x + w >= W && y + h >= H) { desde = i; break; }
      }
      ctx.fillStyle = "#0d1b2a";
      ctx.fillRect(0, 0, W, H);
      for (let i = desde; i < sat.length; i++) {
        const [x, y, w, h] = rect(sat[i]);
        if (x > W || y > H || x + w < 0 || y + h < 0 || !sat[i].img.naturalWidth) continue;
        ctx.drawImage(sat[i].img, x, y, w, h);
      }
    };

    const pintarRios = () => {
      for (const r of rios) {
        if (r.o.a <= 0.001) continue;
        ctx.globalAlpha = r.o.a;
        ctx.lineCap = "round";
        for (const [ancho, color] of [[corto * 0.016, "rgba(255,255,255,0.55)"], [corto * 0.008, r.color]]) {
          ctx.strokeStyle = color;
          ctx.lineWidth = ancho;
          for (const l of r.lineas) {
            // se dibuja de su principio a su final segun avanza p (0..1)
            const n = Math.max(2, Math.ceil(l.length * r.o.p));
            ctx.beginPath();
            let [x, y] = aPx(l[0][0], l[0][1]);
            ctx.moveTo(x, y);
            for (let i = 1; i < n; i++) {
              [x, y] = aPx(l[i][0], l[i][1]);
              ctx.lineTo(x, y);
            }
            ctx.stroke();
          }
        }
      }
      ctx.globalAlpha = 1;
    };

    const pintar = () => {
      ctx.lineJoin = "round";
      if (sat.length) {
        pintarSatelite();
        ctx.beginPath();
        for (const iso in P) if (seVe(iso)) trazar(iso);
        ctx.strokeStyle = "rgba(255,255,255,0.28)";
        ctx.lineWidth = Math.max(1, corto * 0.0016);
        ctx.stroke();
      } else {
        ctx.fillStyle = colores.mar;
        ctx.fillRect(0, 0, W, H);
        ctx.beginPath();
        for (const iso in P) if (seVe(iso)) trazar(iso);
        ctx.fillStyle = colores.tierra;
        ctx.fill();
        ctx.strokeStyle = colores.borde;
        ctx.lineWidth = Math.max(1, corto * 0.0018);
        ctx.stroke();
      }
      for (const c of capas) {
        if (c.o.a <= 0.001 || !P[c.iso]) continue;
        ctx.beginPath();
        trazar(c.iso);
        // en satelite el relleno se apaga al acercarse: de cerca el pais llena la pantalla y solo tapa la foto
        // g (foco): 1 = apagado porque ya se habla de otro; casi se funde con la tierra
        ctx.globalAlpha = c.o.a * (1 - 0.75 * c.o.g) * (sat.length ? 0.35 * Math.min(1, Math.max(0, (6 - cam.z) / 3)) : colores.alfa);
        ctx.fillStyle = c.color;
        ctx.fill();
        ctx.globalAlpha = c.o.a * (1 - 0.6 * c.o.g);
        ctx.strokeStyle = sat.length ? "#ffffff" : colores.tinta;
        ctx.lineWidth = corto * 0.0035;
        ctx.stroke();
      }
      ctx.globalAlpha = 1;
      pintarRios();
      for (const p of puntos) {
        const [x, y] = aPx(p.lon, p.lat);
        if (p.punto && p.o.a > 0) {
          ctx.globalAlpha = p.o.a;
          ctx.beginPath();
          ctx.arc(x, y, corto * 0.011, 0, Math.PI * 2);
          ctx.fillStyle = "#fff";
          ctx.fill();
          ctx.lineWidth = corto * 0.004;
          ctx.strokeStyle = colores.tinta;
          ctx.stroke();
          ctx.globalAlpha = 1;
        }
        p.x = x + p.dx;
        p.y = y + p.dy - (p.punto ? corto * 0.045 : 0);
      }
      separar();
      for (const p of piezas) {
        const [x, y] = aPx(p.lon, p.lat);
        p.el.style.left = x + p.dx + "px";
        p.el.style.top = y + p.dy + "px";
      }
      if (trazos.length) {
        svg.innerHTML = trazos.map((fn) => fn(aPx)).join("");
      }
    };

    // Rotulos que no se pisan: el que llega despues baja lo justo; nadie sale de la pantalla.
    const separar = () => {
      const vivos = puntos.filter((p) => p.o.a > 0.01);
      for (const p of vivos) {
        p.w = p.w || p.el.offsetWidth;
        p.h = p.h || p.el.offsetHeight;
        p.y2 = Math.min(H * 0.7, Math.max(H * 0.06, p.y));
        p.x2 = Math.min(W - p.w / 2 - corto * 0.03, Math.max(p.w / 2 + corto * 0.03, p.x));
      }
      for (let i = 0; i < vivos.length; i++) for (let j = 0; j < i; j++) {
        const a = vivos[i], b = vivos[j];
        if (Math.abs(a.x2 - b.x2) < (a.w + b.w) / 2 && Math.abs(a.y2 - b.y2) < (a.h + b.h) / 2) a.y2 = b.y2 + (a.h + b.h) / 2 + corto * 0.01;
      }
      for (const p of puntos) {
        p.el.style.left = (p.x2 ?? p.x) + "px";
        p.el.style.top = (p.y2 ?? p.y) + "px";
        // si su sitio se ha salido de la pantalla (la camara se fue), el rotulo se esconde en vez de pegarse al borde
        const fuera = p.x < -corto * 0.05 || p.x > W + corto * 0.05 || p.y < -corto * 0.05 || p.y > H * 0.75;
        p.el.style.visibility = fuera ? "hidden" : "visible";
      }
    };

    // Camara: cada toma es un sitio al que se LLEGA en el segundo t. Vuelo suave (con un alejamiento a mitad si el
    // salto es largo) y, al llegar, sigue acercandose despacio hasta la siguiente toma.
    const tomas = (lista, inicio) => {
      Object.assign(cam, inicio);
      let previa = { ...inicio }, tPrevia = 0;
      lista.forEach((toma) => {
        const meta = encuadre(toma);
        const dur = Math.max(0.5, Math.min(1.9, toma.t - tPrevia));
        const t0 = Math.max(tPrevia, toma.t - dur);
        if (t0 > tPrevia) F.tl.to(cam, { z: previa.z + DERIVA * (t0 - tPrevia), duration: t0 - tPrevia, ease: "none" }, tPrevia);
        const desde = previa.z + DERIVA * (t0 - tPrevia);
        const salto = Math.hypot(meta.x - previa.x, meta.y - previa.y) * S * 2 ** Math.min(desde, meta.z) / corto;
        F.tl.to(cam, { x: meta.x, y: meta.y, duration: dur, ease: "power2.inOut" }, t0);
        if (salto > 1.6) {
          const alto = Math.min(desde, meta.z) - Math.min(2.2, Math.log2(salto));
          F.tl.to(cam, { z: alto, duration: dur / 2, ease: "power2.out" }, t0).to(cam, { z: meta.z, duration: dur / 2, ease: "power2.in" }, t0 + dur / 2);
        } else {
          F.tl.to(cam, { z: meta.z, duration: dur, ease: "power2.inOut" }, t0);
        }
        previa = meta;
        tPrevia = toma.t;
      });
      if (F.D > tPrevia) F.tl.to(cam, { z: previa.z + DERIVA * (F.D - tPrevia), duration: F.D - tPrevia, ease: "none" }, tPrevia);
    };

    const pais = (iso, color, a, b) => {
      const c = { iso, color, o: { a: a <= 0 ? 1 : 0, g: 0 } };  // a <= 0: ya pintado en el primer fotograma
      capas.push(c);
      if (a > 0) F.tl.to(c.o, { a: 1, duration: 0.5, ease: "power2.out" }, a);
      if (b != null && b < F.D) F.tl.to(c.o, { a: 0, duration: 0.4, ease: "power2.in" }, b);
      return c;
    };
    // Foco: el pais se apaga en t (ya se habla de otro)
    const apagar = (c, t) => F.tl.to(c.o, { g: 1, duration: 0.45, ease: "power2.out" }, Math.max(0, t));

    const etiqueta = (texto, lon, lat, a, opciones = {}) => {
      const el = F.crear("div", "etq-mapa", padre);
      el.textContent = texto;
      el.style.fontSize = corto * (opciones.tam || 0.042) + "px";
      const p = { el, lon, lat, dx: (opciones.dx || 0) * corto, dy: (opciones.dy || 0) * corto, punto: !!opciones.punto, o: { a: 0 } };
      puntos.push(p);
      F.tl.fromTo(el, { opacity: 0, scale: 0.6 }, { opacity: 1, scale: 1, duration: 0.4, ease: "back.out(2)", immediateRender: true }, Math.max(0, a));
      F.tl.to(p.o, { a: 1, duration: 0.3 }, Math.max(0, a));
      if (opciones.b != null && opciones.b < F.D) {
        F.tl.to(el, { opacity: 0, duration: 0.3 }, opciones.b);
        F.tl.to(p.o, { a: 0, duration: 0.3 }, opciones.b);
      }
      return p;
    };

    // Rio: se dibuja de nacimiento a desembocadura en 1.2 s desde a (y se apaga en b).
    const rio = (clave, color, a, b) => {
      const datos = (window.RIOS || {})[clave];
      if (!datos) return null;
      const r = { lineas: datos.l, color, o: { a: a <= 0 ? 1 : 0, p: a <= 0 ? 1 : 0 } };
      rios.push(r);
      if (a > 0) F.tl.to(r.o, { a: 1, duration: 0.3 }, a).to(r.o, { p: 1, duration: 1.2, ease: "power1.inOut" }, a);
      if (b != null && b < F.D) F.tl.to(r.o, { a: 0, duration: 0.4 }, b);
      return r;
    };

    // Un elemento (bandera, pegatina) pegado a un sitio del mapa: se mueve con la camara. dx/dy en px.
    const pieza = (el, lon, lat, dx = 0, dy = 0) => {
      piezas.push({ el, lon, lat, dx, dy });
      return el;
    };

    // Capa SVG para lineas que siguen al mapa (medidas, rutas): cada fn(aPx) devuelve su trozo de SVG.
    const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    svg.setAttribute("class", "fx-capa");
    svg.setAttribute("width", W);
    svg.setAttribute("height", H);
    svg.style.zIndex = 3;
    padre.appendChild(svg);
    const trazo = (fn) => trazos.push(fn);

    F.alPintar(pintar);
    return { cam, encuadre, tomas, pais, apagar, etiqueta, rio, pieza, trazo, pintar, aPx, satelite: sat.length > 0 };
  };

  // Zona donde se encuadra el mapa: "normal", "rotulo" (deja arriba sitio para un dato grande) o
  // "portada" (el titulo ocupa la mitad de arriba). Python la guarda en `previa` para seguir sin salto.
  F.zonaMapa = (tipo) => {
    const z = F.zona;
    if (tipo === "rotulo") return { ...z, y: z.y + z.h * 0.24, h: z.h * 0.76 };
    if (tipo === "portada") return F.vertical ? { ...z, y: z.y + z.h * 0.46, h: z.h * 0.54 } : { ...z, x: z.x + z.w * 0.5, w: z.w * 0.5, y: z.y + z.h * 0.12, h: z.h * 0.88 };
    return z;
  };
  F.DERIVA = DERIVA;
  F.crearMapa = crearMapa;
  // color con nombre del estilo (rojo, azul...) o un #hex
  F.color = (nombre) => (String(nombre || "").startsWith("#") ? nombre : v(nombre || "acento") || v("acento"));
})();
