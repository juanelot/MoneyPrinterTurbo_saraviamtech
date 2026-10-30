// Escena ILUSTRACION: una escena dibujada (biblioteca de la Fabrica) a pantalla completa, con un acercamiento
// lento que nunca se para. En horizontal la imagen (vertical) va entera en el centro sobre ella misma desenfocada.
// ESCENA = { src: "ilus_xxx.webp", golpe?: {texto, a, b?}, rotulo?: {texto, a}, variante? }
// Variantes del movimiento (Python las reparte para que no se repitan): 0 acercarse, 1 alejarse,
// 2 barrido lateral, 3 foto enmarcada e inclinada sobre ella misma desenfocada.
F.montar(() => {
  const E = F.E;
  const caja = F.crear("div", "ilus");
  if (E.clip) {
    // hay un clip de video para esta escena: todo verde croma salvo los textos (Python pone el clip detras)
    caja.style.background = "#00ff00";
    pintarTextos(E);
    return;
  }
  const V = E.variante || 0;
  // la ilustracion es 9:16: en 1:1 y 16:9 no llena sin cortar demasiado (y el marco tambien la deja entera)
  const ancha = F.W / F.H > 0.8 || V === 3;
  if (ancha) {
    const fondo = F.crear("img", "", caja);
    fondo.src = E.src;
    fondo.style.cssText = "inset:-6%;width:112%;height:112%;object-fit:cover;filter:blur(28px) brightness(0.6);";
  }
  const img = F.crear("img", "", caja);
  img.src = E.src;
  F.imagen(E.src);
  if (V === 3 && F.W / F.H <= 0.8) {
    // marco: la foto con borde claro, algo inclinada, que se endereza despacio
    const b = F.corto * 0.02;
    img.style.cssText = `left:50%;top:6%;height:62%;border:${b}px solid #f4f1ea;border-bottom-width:${b * 3}px;` +
      `border-radius:${b * 0.4}px;box-shadow:0 2vmin 6vmin rgba(0,0,0,0.6);`;
    gsap.set(img, { xPercent: -50 });   // centrada con GSAP (un translate en el css se sumaria al de la animacion)
    F.tl.fromTo(img, { rotation: -4, scale: 0.94 }, { rotation: 1.5, scale: 1.02, duration: F.D, ease: "none" }, 0);
  } else {
    img.style.cssText = ancha
      ? `top:3%;height:94%;left:50%;border-radius:${F.corto * 0.02}px;box-shadow:0 1vmin 4vmin rgba(0,0,0,0.6);`
      : "inset:0;width:100%;height:100%;object-fit:cover;";
    // movimiento lento que nunca se para, hacia un punto algo por encima del centro (donde suelen estar las caras)
    const mov = ancha || V === 0 ? [{ scale: 1.0 }, { scale: 1.1 }]
      : V === 1 ? [{ scale: 1.16 }, { scale: 1.02 }]
      : [{ scale: 1.14, xPercent: -4 }, { scale: 1.14, xPercent: 4 }];
    if (ancha) gsap.set(img, { xPercent: -50 });
    F.tl.fromTo(img, mov[0], { ...mov[1], duration: F.D, ease: "none", transformOrigin: "50% 40%" }, 0);
  }
  F.tl.fromTo(img, { opacity: 0.4 }, { opacity: 1, duration: 0.35, ease: "power2.out", immediateRender: true }, 0);
  const sombra = F.crear("div", "fx-capa", caja);
  sombra.style.background = "linear-gradient(180deg, rgba(0,0,0,0.35) 0%, rgba(0,0,0,0) 30%, rgba(0,0,0,0) 60%, rgba(0,0,0,0.45) 100%)";
  pintarTextos(E);
});

function pintarTextos(E) {
  // con rotulo arriba, la frase de golpe baja para no pisarlo
  if (E.golpe) F.golpe(E.golpe, E.rotulo ? { ...F.zona, y: F.zona.y + F.zona.h * 0.26 } : F.zona);
  if (E.rotulo) {
    const el = F.crear("div", "rotulo");
    el.textContent = E.rotulo.texto;
    el.style.cssText += `left:${F.zona.x}px;width:${F.zona.w}px;top:${F.zona.y}px;color:#fff;text-shadow:0 0.04em 0.2em rgba(0,0,0,0.8);`;
    F.ajustar(el, F.zona.w, F.zona.h * 0.22, F.corto * 0.2);
    F.entrar(el, E.rotulo.a);
  }
}
