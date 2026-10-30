// Escena PROTAGONISTA: la pegatina de quien va el video, grande en el centro, cambia de estado al decir cada
// palabra (nace gris y se vuelve rosa, crece, se multiplica, se va...). Empieza como acabo en su escena anterior.
// ESCENA = { src, inicio: "gris", cambios: [{estado, a}], golpe?: {texto, a}, rotulo?: {texto, a} }
F.montar(() => {
  const E = F.E;
  F.fondo();
  const z = F.zona;
  let arriba = 0;
  if (E.rotulo) {
    const el = F.crear("div", "rotulo");
    el.textContent = E.rotulo.texto;
    el.style.cssText += `left:${z.x}px;width:${z.w}px;top:${z.y}px;`;
    F.ajustar(el, z.w, z.h * 0.2, F.corto * 0.18);
    F.entrar(el, E.rotulo.a);
    arriba = el.offsetHeight + F.corto * 0.03;
  }
  // el golpe va abajo de la zona: el protagonista ocupa lo que queda en medio
  const abajo = E.golpe ? z.h * 0.24 : 0;
  const hueco = { x: z.x, y: z.y + arriba, w: z.w, h: z.h - arriba - abajo };
  // los estados "grande" y "muchos" necesitan sitio: se dibuja algo mas pequeno que el hueco
  const alto = Math.min(hueco.h * 0.85, hueco.w * 0.8);
  const p = F.protagonista(E.src, alto, E.inicio);
  p.caja.style.cssText += `left:${hueco.x}px;top:${hueco.y}px;width:${hueco.w}px;height:${hueco.h}px;`;
  // (la escala de la caja es de la deriva; la entrada solo funde)
  F.tl.fromTo(p.caja, { opacity: 0 }, { opacity: 1, duration: 0.3, ease: "power2.out", immediateRender: true }, 0);
  for (const c of E.cambios || []) p.cambiar(c.estado, c.a);
  if (E.golpe) F.golpe(E.golpe, { x: z.x, y: z.y + z.h - abajo, w: z.w, h: abajo / 0.3 });
  F.deriva(p.caja);
});
