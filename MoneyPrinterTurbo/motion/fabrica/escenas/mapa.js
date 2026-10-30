// Escena MAPA: la camara vuela de toma en toma, los paises se iluminan y salen rotulos y un dato grande.
// ESCENA = {
//   previa: {toma, dz, zona} | null    -- donde acabo la camara de la escena anterior (para seguir sin salto)
//   tomas: [{t, bbox | lon, lat, z}],  -- a donde llega la camara y en que segundo
//   paises: [{iso, color, a, b?}],     -- se pinta en a (y se apaga en b)
//   etiquetas: [{texto, lon, lat, a, b?, punto?}],
//   rotulos: [{texto, a, b?}]          -- fecha o cifra grande, arriba; la camara encuadra debajo
//   golpe: {texto, a, b?} | null       -- frase corta de impacto, arriba, como un sello
//   satelite: [{src, x0, y0, x1, y1}]  -- foto de satelite (si no, mapa del estilo)
//   rios: [{clave, color, a, b?}], banderas: [{src, lon, lat, a, b?, ojos?, dx?, dy?}],
//   pegatinas: [{src, lon, lat, a, b?, tam?, dx?, dy?}], circulos: [{lon, lat, a, b?}],
//   medidas: [{desde: [lon, lat], hasta: [lon, lat], texto, a}], rutas: [{desde, hasta, a, dur?, src?}]
// }
F.montar(() => {
  const E = F.E;
  // Si hay rotulo grande (o frase de golpe) arriba, el mapa se encuadra en el resto de la zona.
  const arriba = (E.rotulos || []).length || E.golpe;
  const mapa = F.crearMapa(F.escena, F.zonaMapa(arriba ? "rotulo" : "normal"), { satelite: E.satelite });
  let inicio;
  if (E.previa) {
    inicio = mapa.encuadre(E.previa.toma, F.zonaMapa(E.previa.zona));
    inicio.z += E.previa.dz || 0;
  } else {
    // sin escena anterior: se empieza un poco mas lejos de la primera toma
    const primera = mapa.encuadre(E.tomas[0]);
    inicio = { ...primera, z: primera.z - 0.9 };
  }
  mapa.tomas(E.tomas || [], inicio);
  const capas = (E.paises || []).map((p) => ({ p, c: mapa.pais(p.iso, F.color(p.color), p.a, p.b) }));
  if (E.foco) {
    // al pintarse un pais de otro color, los de antes se apagan: solo brilla aquel del que se habla
    for (const x of capas) {
      const luego = capas.filter((y) => y.p.a > x.p.a + 0.3 && y.p.color !== x.p.color).map((y) => y.p.a);
      if (luego.length) mapa.apagar(x.c, Math.min(...luego));
    }
  }
  for (const r of E.rios || []) mapa.rio(r.clave, F.color(r.color || "azul"), r.a, r.b);
  for (const e of E.etiquetas || []) mapa.etiqueta(e.texto, e.lon, e.lat, e.a, { b: e.b, punto: e.punto, dy: e.dy });
  for (const c of E.circulos || []) F.circulo(mapa, c);
  for (const m of E.medidas || []) F.medida(mapa, m);
  for (const r of E.rutas || []) F.ruta(mapa, r);
  for (const b of E.banderas || []) F.bandera(mapa, b);
  for (const p of E.pegatinas || []) F.pegatina(mapa, p);
  if (E.golpe) F.golpe(E.golpe);
  for (const r of E.rotulos || []) {
    const el = F.crear("div", "rotulo");
    el.textContent = r.texto;
    el.style.left = F.zona.x + "px";
    el.style.width = F.zona.w + "px";
    el.style.top = F.zona.y + "px";
    F.ajustar(el, F.zona.w, F.zona.h * 0.22, F.corto * 0.2);
    F.entrar(el, r.a);
    if (r.b != null && r.b < F.D) F.tl.to(el, { opacity: 0, duration: 0.3 }, r.b);
  }
});
