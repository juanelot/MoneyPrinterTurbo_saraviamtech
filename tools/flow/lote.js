#!/usr/bin/env node
// Genera en Google Flow la imagen de cada escena de un script.json del Estudio.
// Se comporta como la extension "AI Content Generator":
//   - el ARCHIVO manda: una escena con imagen en --out ya esta hecha y se salta;
//   - 4 intentos por escena, hasta 2 min cada uno; pausa 4 s tras OK y 4,5 s tras fallo;
//   - las fallidas se quedan sin archivo (pendientes para la proxima corrida).
// Mejoras: repaso automatico de las fallidas (--pasadas-extra), pausa si Flow avisa de
// cuota/limite y escritura atomica (.part + rename).
//
//   node lote.js --script escenas/script.json --out recursos/images --aspect 9:16 --model 2
//                [--solo 3,7,12] [--pasadas-extra 2] [--detener ruta/.detener]
//
// Progreso: una linea JSON por evento en stdout. Codigo de salida: 0 fin normal,
// 2 detenido, 3 sin sesion, 4 limite de Flow, 1 error.
import fs from 'node:fs';
import path from 'node:path';
import { parseArgs } from 'node:util';
import { withFlowLock } from './lock.js';
import { ASPECTS, Limite, MODELS, SinSesion, abrirProyecto, configurar, conectar, generarUna, nuevoProyecto, sleep } from './flow.js';

const INTENTOS = 4;
const PAUSA_OK = 4000;
const PAUSA_FALLO = 4500;
const SUFIJO = ', no text, no letters, no words, no captions, no watermark';

const { values: op } = parseArgs({
  options: {
    script: { type: 'string' },
    out: { type: 'string' },
    aspect: { type: 'string', default: '16:9' },
    model: { type: 'string', default: '2' },
    solo: { type: 'string', default: '' },
    'pasadas-extra': { type: 'string', default: '2' },
    detener: { type: 'string', default: '' },
  },
});

const emitir = (o) => process.stdout.write(`${JSON.stringify({ t: Date.now(), ...o })}\n`);

function salir(codigo, evento) {
  if (evento) emitir(evento);
  process.exit(codigo);
}

if (!op.script || !op.out) salir(1, { evento: 'error', motivo: 'faltan --script y --out' });
if (!ASPECTS.includes(op.aspect)) salir(1, { evento: 'error', motivo: `--aspect debe ser ${ASPECTS.join(', ')}` });
if (!MODELS[op.model]) salir(1, { evento: 'error', motivo: `--model debe ser ${Object.keys(MODELS).join(', ')}` });

const EXT = new Set(['.jpg', '.jpeg', '.png', '.bmp', '.webp']);
const PATRON = /(?:scene|escena|image|imagen|img|video|clip|shot)[\s_-]*0*(\d+)/i;

// Mismo criterio que recursos.numero_escena del backend.
function numeroDe(nombre) {
  const base = path.parse(nombre).name;
  const m = base.match(PATRON) || base.match(/\d+/);
  return m ? Number(m[1] ?? m[0]) : null;
}

function hechas() {
  const set = new Set();
  if (!fs.existsSync(op.out)) return set;
  for (const n of fs.readdirSync(op.out)) {
    if (EXT.has(path.extname(n).toLowerCase())) {
      const k = numeroDe(n);
      if (k != null) set.add(k);
    }
  }
  return set;
}

let parar = false;
const detenido = () => parar || (op.detener && fs.existsSync(op.detener));
process.on('SIGTERM', () => { parar = true; });
process.on('SIGINT', () => { parar = true; });

// Espera troceada para que "detener" no tenga que esperar la pausa entera.
async function pausa(ms) {
  for (let t = 0; t < ms && !detenido(); t += 250) await sleep(250);
}

function guardar(numero, { buffer, tipo }) {
  fs.mkdirSync(op.out, { recursive: true });
  const final = path.join(op.out, `scene_${String(numero).padStart(4, '0')}.${tipo}`);
  const part = `${final}.part`;
  fs.writeFileSync(part, buffer);
  fs.renameSync(part, final);
  return final;
}

async function main() {
  const script = JSON.parse(fs.readFileSync(op.script, 'utf8'));
  const solo = new Set(op.solo.split(',').map((s) => Number(s.trim())).filter(Boolean));
  let escenas = (script.scenes || [])
    .filter((e) => (e.image_prompt || '').trim())
    .filter((e) => !solo.size || solo.has(Number(e.scene_number)));
  const listas = hechas();
  const pendientes = escenas.filter((e) => !listas.has(Number(e.scene_number)));
  emitir({ evento: 'inicio', total: escenas.length, pendientes: pendientes.length, listas: escenas.length - pendientes.length });
  // nada que hacer: sin navegador que cerrar (fin() aun no existe aqui)
  if (!pendientes.length) return [0, { evento: 'fin', ok: 0, error: 0, detenido: false }];

  // Un proyecto de Flow por corrida; si la pagina se rompe se reconecta al mismo.
  let sesion = null;
  let projectId = null;
  const abrir = async () => {
    if (sesion?.browser.isConnected()) return sesion;
    sesion = await conectar();
    if (!projectId) {
      projectId = await nuevoProyecto(sesion.page);
      emitir({ evento: 'proyecto', id: projectId });
    }
    await abrirProyecto(sesion.page, projectId);
    await configurar(sesion.page, { aspect: op.aspect, model: MODELS[op.model] });
    return sesion;
  };
  const cerrar = async () => {
    await sesion?.browser.close().catch(() => {});
    sesion = null;
  };
  const fin = async (codigo, evento) => { await cerrar(); return [codigo, evento]; };

  const ok = new Set();
  let fallidas = pendientes;
  const extra = Math.max(0, Number(op['pasadas-extra']) || 0);
  for (let pasada = 1; pasada <= 1 + extra && fallidas.length; pasada++) {
    if (pasada > 1) emitir({ evento: 'pasada', n: pasada, pendientes: fallidas.length });
    const siguientes = [];
    for (const e of fallidas) {
      if (detenido()) return fin(2, { evento: 'fin', ok: ok.size, error: siguientes.length, detenido: true });
      const n = Number(e.scene_number);
      if (hechas().has(n)) { ok.add(n); continue; } // subida a mano mientras tanto
      let hecha = false;
      for (let intento = 1; intento <= INTENTOS && !hecha; intento++) {
        if (detenido()) return fin(2, { evento: 'fin', ok: ok.size, error: siguientes.length, detenido: true });
        emitir({ escena: n, estado: 'generando', intento, pasada });
        const t0 = Date.now();
        try {
          const s = await abrir();
          const img = await generarUna(s.page, s.context, `${e.image_prompt.trim()}${SUFIJO}`);
          const archivo = guardar(n, img);
          ok.add(n);
          hecha = true;
          emitir({ escena: n, estado: 'ok', intento, archivo: path.basename(archivo), segundos: Math.round((Date.now() - t0) / 1000) });
        } catch (err) {
          if (err instanceof SinSesion) return fin(3, { evento: 'sin_sesion', motivo: err.message });
          if (err instanceof Limite) return fin(4, { evento: 'limite', motivo: err.message, escena: n });
          emitir({ escena: n, estado: 'intento', intento, motivo: String(err.message || err).slice(0, 300) });
          // Tras un fallo raro (pagina rota, ajustes perdidos) se vuelve a abrir el proyecto.
          if (!/no pudo generar/.test(err.message || '')) await cerrar();
          await pausa(PAUSA_FALLO);
        }
      }
      if (hecha) await pausa(PAUSA_OK);
      else { siguientes.push(e); emitir({ escena: n, estado: 'error', intentos: INTENTOS }); }
    }
    fallidas = siguientes;
  }
  return fin(0, { evento: 'fin', ok: ok.size, error: fallidas.length, detenido: false });
}

// El lock se suelta ANTES de salir (process.exit dentro de main se lo saltaria).
withFlowLock(main, { pollMs: 1000 })
  .then(([codigo, evento]) => salir(codigo, evento))
  .catch((err) => salir(1, { evento: 'error', motivo: String(err?.message || err).slice(0, 500) }));
