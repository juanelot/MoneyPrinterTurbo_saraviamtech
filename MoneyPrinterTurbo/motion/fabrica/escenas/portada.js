// Escena PORTADA (el gancho): el titulo ya se ve en el primer fotograma (sirve de miniatura) y se asienta despacio.
// ESCENA = { titulo: "¿Por que *Bolivia* no tiene mar?", antetitulo?: "...",
//            mapa?: {toma, paises: [{iso, color}]},  (con mapa de fondo y sus paises ya pintados)
//            protagonista?: src }  (sin mapa: la pegatina de quien va el video, grande junto al titulo)
F.montar(() => {
  const E = F.E;
  if (E.mapa) {
    const mapa = F.crearMapa(F.escena, F.zonaMapa("portada"), { satelite: E.satelite });
    const meta = mapa.encuadre(E.mapa.toma);
    mapa.tomas([], meta);  // quieta en su sitio y acercandose despacio
    for (const p of E.mapa.paises || []) mapa.pais(p.iso, F.color(p.color), 0);
    const velo = F.crear("div", "fx-capa");
    velo.style.background = `linear-gradient(180deg, ${F.v("fondo")}b3 0%, ${F.v("fondo")}40 38%, ${F.v("fondo")}00 62%)`;
  } else {
    F.fondo();
  }
  // con mapa: en vertical el titulo va arriba; en horizontal, a la izquierda (el mapa ocupa la derecha)
  const con = E.mapa || E.protagonista;
  const lado = con && !F.vertical;
  const ancho = lado ? F.zona.w * 0.48 : F.zona.w;
  const caja = F.crear("div", "titulo");
  caja.style.cssText += `position:absolute;left:${F.zona.x}px;width:${ancho}px;text-align:${lado ? "left" : "center"};`;
  if (E.antetitulo) {
    const ante = F.crear("div", "", caja);
    ante.textContent = E.antetitulo;
    ante.style.cssText = "font-family:var(--f-texto);font-weight:700;font-size:0.32em;letter-spacing:0.12em;text-transform:uppercase;color:var(--tinta-suave);margin-bottom:0.5em;";
  }
  const titulo = F.crear("div", "", caja);
  // cada palabra en su span para que se asienten una tras otra
  titulo.innerHTML = F.enPalabras(E.titulo || "");
  const alto = con && F.vertical ? F.zona.h * 0.42 : F.zona.h * 0.8;
  F.ajustar(caja, ancho, alto, F.corto * 0.14);
  caja.style.top = (con && F.vertical ? F.zona.y : F.zona.y + (F.zona.h - caja.offsetHeight) / 2) + "px";
  if (E.protagonista && !E.mapa) {
    // debajo del titulo (vertical) o a la derecha (horizontal); ya visible en el primer fotograma
    const libre = F.vertical ? { x: F.zona.x, y: F.zona.y + caja.offsetHeight + F.corto * 0.05, w: F.zona.w }
                             : { x: F.zona.x + ancho + F.corto * 0.04, y: F.zona.y, w: F.zona.w - ancho - F.corto * 0.04 };
    // sin subtitulos en la portada (el titulo ya dice lo mismo) puede bajar mas que la zona segura
    libre.h = ((E.subtitulos || []).length || !F.vertical ? F.zona.y + F.zona.h : F.H * 0.8) - libre.y;
    // las pegatinas traen margen transparente: se dibuja algo mas grande que el hueco
    const lado_px = Math.min(libre.w * 1.05, libre.h * 1.1);
    const caja_p = F.crear("div", "");
    caja_p.style.cssText = `position:absolute;left:${libre.x}px;top:${libre.y}px;width:${libre.w}px;height:${libre.h}px;display:flex;align-items:center;justify-content:center;`;
    const img = F.icono(caja_p, { src: E.protagonista }, lado_px);
    if (img) img.style.cssText += `max-width:${libre.w}px;object-fit:contain;`;
    F.tl.fromTo(caja_p, { scale: 0.94 }, { scale: 1.04, duration: F.D, ease: "none" }, 0);
    F.flotar(img, -0.5);
  }
  // primer fotograma ya compuesto: las palabras solo se asientan (no aparecen de la nada)
  F.tl.fromTo(titulo.querySelectorAll(".pal"), { y: "0.12em", scale: 1.06 }, { y: 0, scale: 1, duration: 0.5, ease: "power3.out", stagger: 0.05 }, 0);
  F.tl.fromTo(caja, { scale: 1.03 }, { scale: 1, duration: F.D, ease: "none" }, 0);
});
