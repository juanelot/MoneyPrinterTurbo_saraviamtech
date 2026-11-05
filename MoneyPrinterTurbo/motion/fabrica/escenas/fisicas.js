// Escena FISICAS: la simulacion la pinta Blender (motion/blender/fisicas.py) y Python la pone detras. Aqui solo va lo
// de encima sobre verde croma, igual que en la escena barro: el gancho grande (titulo) y la frase de golpe.
// ESCENA = { clip: true, tres_d: {...para Blender}, titulo?: "...*clave*...", golpe?: {texto, a} }
F.montar(() => {
  const E = F.E;
  const caja = F.crear("div", "ilus");
  caja.style.background = "#00ff00";
  const z = F.zona;
  if (E.titulo) {
    // arriba, en blanco con borde oscuro (el plano 3D no tiene un color de fondo fijo)
    const t = F.crear("div", "titulo");
    t.innerHTML = F.marcar(E.titulo);
    t.style.cssText += `position:absolute;left:${z.x}px;width:${z.w}px;top:${F.H * (F.vertical ? 0.08 : 0.06)}px;text-align:center;` +
      "color:#fff;-webkit-text-stroke:0.08em #1e1c1a;paint-order:stroke fill;text-shadow:0 0.06em 0.2em rgba(0,0,0,0.45);";
    F.ajustar(t, z.w, F.H * 0.2, F.corto * 0.12);
    // ya se lee en el primer fotograma (es lo que decide si siguen mirando) y se asienta
    F.tl.fromTo(t, { scale: 1.12 }, { scale: 1, duration: 0.5, ease: "power3.out", immediateRender: true }, 0);
  }
  if (E.golpe) F.golpe(E.golpe, { ...z, y: z.y + z.h * (E.titulo ? 0.3 : 0) });
});
