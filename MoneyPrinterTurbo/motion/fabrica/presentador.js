// Presentador: un personaje plano (SVG) abajo a la derecha, cortado a la altura del pecho, que habla todo el video.
// ESCENA.presentador = {
//   aspecto: {piel, pelo, ropa, ropa2, peinado: corto|largo|rizado|calvo|coleta, gafas: bool, barba: bool},
//   t0: segundo del video en que empieza esta escena (parpadeo y balanceo siguen sin saltos entre escenas),
//   boca: "0123..." un digito (0 cerrada - 9 muy abierta) por fotograma a 30 fps, sacado del volumen de la voz,
//   asentir: [s], senalar: [s] (mano que sube 1.7 s), palma: [s] (mano abierta 1.4 s) en segundos de la escena }
// Todo se pinta en F.alPintar (no con tweens): asi cada fotograma depende solo del tiempo y la cache por escena vale.
(() => {
  const NS = "http://www.w3.org/2000/svg";
  const LINEA = "#3b2a20";

  const el = (tag, attrs, padre) => {
    const n = document.createElementNS(NS, tag);
    for (const [k, v] of Object.entries(attrs || {})) n.setAttribute(k, v);
    if (padre) padre.appendChild(n);
    return n;
  };
  const trazo = (extra = {}) => ({ stroke: LINEA, "stroke-width": 6, "stroke-linejoin": "round", "stroke-linecap": "round", ...extra });

  // 10 bocas: 0 una sonrisa cerrada; 1-9 cada vez mas abierta (con dientes desde la 4 y lengua desde la 6)
  const bocas = [];
  for (let k = 0; k < 10; k++) {
    if (k === 0) { bocas.push({ d: "M -30 -2 Q 0 12 30 -2", abierta: false }); continue; }
    const w = 24 + k * 2.6, h = 5 + k * 5.4;
    bocas.push({ d: `M ${-w} 0 Q 0 ${-h * 0.22} ${w} 0 Q ${w * 0.6} ${h} 0 ${h} Q ${-w * 0.6} ${h} ${-w} 0 Z`, abierta: true, w, h, k });
  }

  // PRNG fijo: los parpadeos son los mismos en cada render (la cache y el video entero cuadran)
  const azar = (semilla) => () => ((semilla = (semilla * 16807) % 2147483647) - 1) / 2147483646;

  // Presentador propio (una imagen: busto recortado, presentadores.py): la imagen se balancea entera; encima, su boca
  // abierta cuando hay voz (cerrada se ve la del dibujo) y parpados del color de su piel al parpadear.
  // P.imagen = archivo; P.aspecto = {proporcion, ojos: [[x, y], [x, y]], boca: [x, y], ancho_boca, piel} (0-1)
  const deImagen = (P) => {
    const A = P.aspecto;
    const { W, H } = F;
    const alto = F.vertical ? H * 0.42 : F.cuadrado ? H * 0.48 : H * 0.62;
    const ancho = alto * A.proporcion;
    const caja = F.crear("div", "", document.getElementById("root"));
    caja.style.cssText = `position:absolute;z-index:6;width:${ancho}px;height:${alto}px;bottom:0;right:${W * 0.02}px;transform-origin:50% 100%;`;
    const img = F.crear("img", "", caja);
    img.src = P.imagen;
    F.imagen(P.imagen);
    img.style.cssText = "position:absolute;inset:0;width:100%;height:100%;";
    const svg = el("svg", { viewBox: `0 0 ${ancho} ${alto}`, width: "100%", height: "100%" }, caja);
    svg.style.cssText = "position:absolute;inset:0;overflow:visible;";
    // parpados: elipses de piel sobre cada ojo que se cierran de arriba abajo
    const sep = Math.abs(A.ojos[1][0] - A.ojos[0][0]) * ancho;
    // tamano del parpado: el del ojo medido en la imagen (un poco mas grande para taparlo entero)
    const rx = A.ojo_tam ? A.ojo_tam[0] * ancho * 0.62 : sep * 0.24;
    const ry = A.ojo_tam ? A.ojo_tam[1] * alto * 0.75 : sep * 0.2;
    const parpados = A.ojos.map(([x, y]) => {
      const g = el("g", { transform: `translate(${x * ancho} ${y * alto})` }, svg);
      const p = el("ellipse", { cx: 0, cy: 0, rx, ry, fill: A.piel }, g);
      const linea = el("path", { d: `M ${-rx} ${ry * 0.1} Q 0 ${ry * 0.5} ${rx} ${ry * 0.1}`, fill: "none",
                                 stroke: LINEA, "stroke-width": Math.max(2, sep * 0.035), "stroke-linecap": "round" }, g);
      g.style.display = "none";
      return { g, p, linea };
    });
    // boca: las mismas formas que el presentador dibujado, a la escala de su boca
    const escala = (A.ancho_boca * ancho / 2) / 40;
    const bocaG = el("g", { transform: `translate(${A.boca[0] * ancho} ${A.boca[1] * alto}) scale(${escala})` }, svg);
    // dientes y lengua recortados a la forma de la boca (si no, asoman por fuera de los labios)
    const defsB = el("defs", {}, svg);
    const recorte = el("path", { d: bocas[5].d }, el("clipPath", { id: "bocaImagen" }, defsB));
    // al hablar se tapan los labios dibujados (cerrados) con piel de borde suave; si no, un labio se ve cerrado
    el("feGaussianBlur", { stdDeviation: 2 }, el("filter", { id: "bordeSuave", x: "-30%", y: "-60%", width: "160%", height: "220%" }, defsB));
    el("ellipse", { cx: 0, cy: 0, rx: 52, ry: (A.alto_labios || 0.026) * alto / escala * 0.75, fill: A.piel, filter: "url(#bordeSuave)" }, bocaG);
    // la forma se abre hacia arriba y hacia abajo de la linea de los labios
    const forma = el("g", {}, bocaG);
    const fondoBoca = el("path", { d: bocas[5].d, fill: "#5b1d1d", ...trazo({ "stroke-width": 5 }) }, forma);
    const dentro = el("g", { "clip-path": "url(#bocaImagen)" }, forma);
    const dientes = el("rect", { x: -40, y: -2, width: 80, height: 6, fill: "#efe9df" }, dentro);
    const lengua = el("ellipse", { cx: 0, cy: 30, rx: 20, ry: 11, fill: "#b9504a" }, dentro);
    const r = azar(97);
    const parpadeos = [];
    for (let t = 1.2; t < P.t0 + F.D + 5; t += 2.4 + r() * 1.8) parpadeos.push(t);
    const boca = String(P.boca || "");
    F.alPintar((t) => {
      const g = P.t0 + t;
      const k = Math.min(9, Number(boca[Math.min(boca.length - 1, Math.max(0, Math.floor(t * 30)))]) || 0);
      bocaG.style.display = k ? "" : "none";
      if (k) {
        // sobre un dibujo con labios la boca se abre poco: como mucho la forma 5 de 9
        const b = bocas[Math.ceil(k * 0.55)];
        fondoBoca.setAttribute("d", b.d);
        recorte.setAttribute("d", b.d);
        forma.setAttribute("transform", `translate(0 ${-b.h * 0.42})`);
        // solo una franja fina de dientes arriba, y solo con la boca bien abierta
        dientes.style.display = k >= 7 ? "" : "none";
        dientes.setAttribute("y", -b.h * 0.1);
        dientes.setAttribute("height", b.h * 0.16);
        lengua.style.display = k >= 5 ? "" : "none";
        lengua.setAttribute("cy", b.h * 0.85);
      }
      let rot = Math.sin(g * 1.1) * 1.0 + Math.sin(g * 0.53 + 1) * 0.7, dy = 0;
      for (const a of P.asentir || []) {
        const u = (t - a) / 0.5;
        if (u >= 0 && u <= 1) { dy += Math.sin(Math.PI * u) * alto * 0.012; rot += Math.sin(Math.PI * u) * 0.8; }
      }
      caja.style.transform = `translate(${Math.sin(g * 0.8) * ancho * 0.006}px, ${dy + Math.sin(g * 1.9) * alto * 0.002}px) rotate(${rot}deg)`;
      let cierre = 0;
      for (const b of parpadeos) {
        if (g >= b && g <= b + 0.14) { cierre = Math.sin(Math.PI * (g - b) / 0.14); break; }
        if (b > g) break;
      }
      parpados.forEach(({ g: gr, p }) => {
        gr.style.display = cierre > 0.05 ? "" : "none";
        p.setAttribute("ry", ry * cierre);
        p.setAttribute("cy", -ry * (1 - cierre));
      });
    });
  };

  F.presentador = () => {
    const P = F.E.presentador;
    if (!P) return;
    if (P.imagen) return deImagen(P);
    const A = { piel: "#f1c7a3", pelo: "#3a2a22", ropa: "#2f5d8a", ropa2: "#24496e", peinado: "corto", gafas: true, barba: false, ...(P.aspecto || {}) };
    const { W, H } = F;
    // tamano y sitio: en vertical 650x770 de 1080x1920 desde x 430, y 1170; en horizontal a la derecha, 60 % del alto
    const alto = F.vertical ? H * 0.401 : F.cuadrado ? H * 0.46 : H * 0.6;
    const ancho = alto * 650 / 770;
    const caja = F.crear("div", "", document.getElementById("root"));
    caja.style.cssText = `position:absolute;z-index:6;width:${ancho}px;height:${alto}px;bottom:0;` +
      (F.vertical ? `left:${W * 0.398}px;` : `right:${W * 0.03}px;`);
    const svg = el("svg", { viewBox: "0 0 650 770", width: "100%", height: "100%" }, caja);
    svg.style.overflow = "visible";
    const defs = el("defs", {}, svg);

    const cuerpo = el("g", {}, svg);
    // capucha detras del cuello, torso con sudadera, cordones
    el("path", { d: "M 205 560 Q 325 500 445 560 L 430 610 Q 325 560 220 610 Z", fill: A.ropa2, ...trazo() }, cuerpo);
    el("path", { d: "M 25 775 C 35 650 125 590 235 572 Q 325 610 415 572 C 525 590 615 650 625 775 Z", fill: A.ropa, ...trazo() }, cuerpo);
    el("path", { d: "M 292 600 L 286 690 M 358 600 L 364 690", fill: "none", ...trazo({ "stroke-width": 5 }) }, cuerpo);
    el("circle", { cx: 286, cy: 696, r: 7, fill: "#fbfaf8", ...trazo({ "stroke-width": 4 }) }, cuerpo);
    el("circle", { cx: 364, cy: 696, r: 7, fill: "#fbfaf8", ...trazo({ "stroke-width": 4 }) }, cuerpo);
    el("path", { d: "M 140 700 Q 150 650 175 625 M 510 700 Q 500 650 475 625", fill: "none", ...trazo({ "stroke-width": 5, stroke: A.ropa2 }) }, cuerpo);
    // cuello
    el("path", { d: "M 282 470 L 282 585 Q 325 605 368 585 L 368 470 Z", fill: A.piel, ...trazo() }, cuerpo);

    const cabeza = el("g", {}, svg);
    if (A.peinado === "largo" || A.peinado === "coleta") {
      el("path", { d: A.peinado === "largo" ? "M 160 320 C 140 470 170 560 230 575 L 420 575 C 480 560 510 470 490 320 Z"
        : "M 470 250 C 560 260 585 360 545 440 C 520 400 500 330 470 300 Z", fill: A.pelo, ...trazo() }, cabeza);
    }
    for (const x of [172, 478]) el("ellipse", { cx: x, cy: 345, rx: 26, ry: 40, fill: A.piel, ...trazo() }, cabeza);
    el("ellipse", { cx: 325, cy: 330, rx: 150, ry: 168, fill: A.piel, ...trazo() }, cabeza);
    if (A.barba) el("path", { d: "M 182 360 C 190 470 250 500 325 500 C 400 500 460 470 468 360 C 440 420 400 445 325 445 C 250 445 210 420 182 360 Z", fill: A.pelo, ...trazo() }, cabeza);
    const pelo = {
      corto: "M 172 325 C 155 180 245 140 330 140 C 425 140 500 185 478 325 C 468 265 430 228 382 236 C 330 214 262 222 232 256 C 205 275 185 300 172 325 Z",
      largo: "M 168 340 C 150 175 245 135 330 138 C 430 140 505 180 482 340 C 470 270 440 230 395 222 C 345 250 270 255 225 240 C 195 270 178 300 168 340 Z",
      coleta: "M 172 320 C 158 185 245 142 330 142 C 425 142 498 186 478 320 C 462 250 420 222 330 222 C 250 222 195 250 172 320 Z",
      rizado: "M 175 320 C 140 280 150 210 200 195 C 205 150 260 125 300 145 C 330 115 390 120 410 150 C 460 140 500 185 490 230 C 520 260 505 305 475 320 C 460 260 410 232 330 232 C 255 232 200 262 175 320 Z",
      calvo: "",
    }[A.peinado] ?? "";
    if (pelo) el("path", { d: pelo, fill: A.pelo, ...trazo() }, cabeza);

    // ojos con parpados (se recortan a la forma del ojo) y pupilas que miran un poco hacia el contenido
    const parpados = [];
    for (const [k, x] of [[0, 268], [1, 382]]) {
      const id = `ojo${k}`;
      el("ellipse", { cx: x, cy: 322, rx: 30, ry: 27 }, el("clipPath", { id }, defs));
      el("ellipse", { cx: x, cy: 322, rx: 30, ry: 27, fill: "#ffffff", ...trazo({ "stroke-width": 5 }) }, cabeza);
      el("circle", { cx: x - 7, cy: 318, r: 13, fill: LINEA }, cabeza);
      el("circle", { cx: x - 11, cy: 313, r: 4, fill: "#ffffff" }, cabeza);
      const g = el("g", { "clip-path": `url(#${id})` }, cabeza);
      const p = el("rect", { x: x - 34, y: 293, width: 68, height: 58, fill: A.piel }, g);
      p.style.transformBox = "fill-box";
      p.style.transformOrigin = "50% 0%";
      parpados.push(p);
    }
    const cejas = el("g", {}, cabeza);
    el("path", { d: "M 238 270 Q 268 254 298 266 M 352 266 Q 382 254 412 270", fill: "none", ...trazo({ "stroke-width": 9, stroke: A.pelo === "#f2d27a" ? LINEA : A.pelo }) }, cejas);
    if (A.gafas) {
      el("rect", { x: 222, y: 284, width: 94, height: 76, rx: 24, fill: "rgba(255,255,255,0.12)", ...trazo({ "stroke-width": 7 }) }, cabeza);
      el("rect", { x: 334, y: 284, width: 94, height: 76, rx: 24, fill: "rgba(255,255,255,0.12)", ...trazo({ "stroke-width": 7 }) }, cabeza);
      el("path", { d: "M 316 312 Q 325 302 334 312 M 222 306 L 180 296 M 428 306 L 470 296", fill: "none", ...trazo({ "stroke-width": 7 }) }, cabeza);
    }
    el("path", { d: "M 322 352 Q 312 385 330 390", fill: "none", ...trazo({ "stroke-width": 5 }) }, cabeza);
    el("ellipse", { cx: 240, cy: 392, rx: 22, ry: 11, fill: "#e8846f", opacity: 0.35 }, cabeza);
    el("ellipse", { cx: 410, cy: 392, rx: 22, ry: 11, fill: "#e8846f", opacity: 0.35 }, cabeza);

    // boca: un grupo en (325, 425) con la forma, los dientes y la lengua (se cambian cada fotograma)
    const bocaG = el("g", { transform: "translate(325 425)" }, cabeza);
    const id = "boca-recorte";
    const recorte = el("path", { d: bocas[5].d }, el("clipPath", { id }, defs));
    const fondoBoca = el("path", { d: bocas[0].d, fill: "#5b1d1d", ...trazo({ "stroke-width": 5 }) }, bocaG);
    const interior = el("g", { "clip-path": `url(#${id})` }, bocaG);
    const dientes = el("rect", { x: -60, y: -8, width: 120, height: 14, fill: "#ffffff" }, interior);
    const lengua = el("ellipse", { cx: 0, cy: 40, rx: 26, ry: 16, fill: "#d9655a" }, interior);
    const contorno = el("path", { d: bocas[0].d, fill: "none", ...trazo({ "stroke-width": 5 }) }, bocaG);
    let ultimaBoca = -1;
    const ponerBoca = (k) => {
      if (k === ultimaBoca) return;
      ultimaBoca = k;
      const b = bocas[k];
      fondoBoca.setAttribute("d", b.d);
      contorno.setAttribute("d", b.d);
      fondoBoca.setAttribute("fill", b.abierta ? "#5b1d1d" : "none");
      recorte.setAttribute("d", b.d);
      interior.style.display = b.abierta ? "" : "none";
      if (b.abierta) {
        dientes.style.display = b.k >= 4 ? "" : "none";
        lengua.style.display = b.k >= 6 ? "" : "none";
        lengua.setAttribute("cy", b.h * 0.95);
      }
    };

    // manos: una que senala hacia arriba a la izquierda (donde esta el contenido) y otra abierta
    const mano = (tipo) => {
      const g = el("g", {}, svg);
      g.style.display = "none";
      if (tipo === "senalar") {
        el("path", { d: "M 60 775 L 95 600 L 175 610 L 160 775 Z", fill: A.ropa, ...trazo() }, g);
        el("rect", { x: 70, y: 500, width: 110, height: 110, rx: 40, fill: A.piel, ...trazo() }, g);
        el("rect", { x: 78, y: 395, width: 34, height: 125, rx: 17, fill: A.piel, ...trazo(), transform: "rotate(-14 95 520)" }, g);
        el("path", { d: "M 150 530 Q 185 540 180 575", fill: "none", ...trazo({ "stroke-width": 5 }) }, g);
      } else {
        el("path", { d: "M 470 775 L 500 610 L 590 615 L 595 775 Z", fill: A.ropa, ...trazo() }, g);
        el("rect", { x: 480, y: 505, width: 120, height: 110, rx: 36, fill: A.piel, ...trazo() }, g);
        [[488, 430, -12], [520, 412, -4], [552, 414, 4], [582, 432, 12]].forEach(([x, y, r]) =>
          el("rect", { x, y, width: 28, height: 98, rx: 14, fill: A.piel, ...trazo(), transform: `rotate(${r} ${x + 14} ${y + 90})` }, g));
        el("rect", { x: 440, y: 520, width: 70, height: 30, rx: 15, fill: A.piel, ...trazo(), transform: "rotate(-35 505 540)" }, g);
      }
      return g;
    };
    const manos = { senalar: mano("senalar"), palma: mano("palma") };

    // parpadeos de todo el video (0,14 s cada 2,4-4,2 s) con la misma semilla en todas las escenas
    const r = azar(97);
    const parpadeos = [];
    for (let t = 1.2; t < P.t0 + F.D + 5; t += 2.4 + r() * 1.8) parpadeos.push(t);
    const boca = String(P.boca || "");
    const salida = (u, sube, dura) => {   // 0 escondida → 1 arriba → 0, con rebote al subir
      if (u < 0 || u > dura) return 0;
      if (u < sube) { const x = u / sube, c = 2.2; return 1 + (c + 1) * Math.pow(x - 1, 3) + c * Math.pow(x - 1, 2); }
      if (u > dura - 0.25) return Math.max(0, 1 - Math.pow((u - (dura - 0.25)) / 0.25, 2));
      return 1;
    };

    F.alPintar((t) => {
      const g = P.t0 + t;
      ponerBoca(Math.min(9, Number(boca[Math.min(boca.length - 1, Math.max(0, Math.floor(t * 30)))]) || 0));
      // balanceo continuo y cabeceo en las palabras clave
      let rot = Math.sin(g * 1.1) * 1.6 + Math.sin(g * 0.53 + 1) * 1.1, dy = 0, ceja = 0;
      for (const a of P.asentir || []) {
        const u = (t - a) / 0.5;
        if (u >= 0 && u <= 1) { dy += Math.sin(Math.PI * u) * 14; rot += Math.sin(Math.PI * u) * 1.5; }
      }
      let k = 0;
      for (const [tipo, lista, dura] of [["senalar", P.senalar, 1.7], ["palma", P.palma, 1.4]]) {
        let v = 0;
        for (const a of lista || []) v = Math.max(v, salida(t - a, 0.3, dura));
        const m = manos[tipo];
        m.style.display = v > 0.001 ? "" : "none";
        m.setAttribute("transform", `translate(0 ${(1 - v) * 470}) rotate(${Math.sin(g * 3) * 2 * v} 325 700)`);
        k = Math.max(k, v);
      }
      ceja = -9 * k;
      cejas.setAttribute("transform", `translate(0 ${ceja})`);
      cabeza.setAttribute("transform", `translate(${Math.sin(g * 0.8) * 4} ${dy}) rotate(${rot} 325 520)`);
      cuerpo.setAttribute("transform", `translate(0 ${Math.sin(g * 1.9) * 2})`);
      let cierre = 0;
      for (const b of parpadeos) {
        if (g >= b && g <= b + 0.14) { cierre = Math.sin(Math.PI * (g - b) / 0.14); break; }
        if (b > g) break;
      }
      parpados.forEach((p) => { p.style.transform = `scaleY(${cierre})`; });
    });
  };
})();
