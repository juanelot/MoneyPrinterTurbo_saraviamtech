#!/usr/bin/env node
// Utilidades del Chrome de Flow para el Estudio:
//   node cli.js chrome   abre el Chrome dedicado (perfil FlowImageChrome) para iniciar sesion
//   node cli.js sesion   {"chrome":bool,"sesion":bool|null,"ocupado":bool} en una linea JSON
//   node cli.js cerrar   cierra el Chrome dedicado (la sesion de Google queda guardada en el perfil)
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { cdpAlive, ensureChrome, userDataDir } from './chrome.js';
import { comprobarSesion, conectar } from './flow.js';

const LOCK = path.join(path.dirname(fileURLToPath(import.meta.url)), '.flow.lock');
const [cmd] = process.argv.slice(2);

try {
  if (cmd === 'chrome') {
    const r = await ensureChrome();
    console.log(JSON.stringify({ ok: true, iniciado: r.started, perfil: userDataDir() }));
  } else if (cmd === 'sesion') {
    // Con un lote en marcha no se toca la pagina: si esta generando, hay sesion.
    if (fs.existsSync(LOCK)) {
      console.log(JSON.stringify({ chrome: true, sesion: true, ocupado: true }));
    } else if (!(await cdpAlive())) {
      console.log(JSON.stringify({ chrome: false, sesion: null, ocupado: false }));
    } else {
      const { browser, page } = await conectar();
      const sesion = await comprobarSesion(page).finally(() => browser.close().catch(() => {}));
      console.log(JSON.stringify({ chrome: true, sesion, ocupado: false }));
    }
  } else if (cmd === 'cerrar') {
    if (fs.existsSync(LOCK)) {
      console.log(JSON.stringify({ ok: false, motivo: 'Flow esta generando: detén la generacion antes de cerrar' }));
    } else if (!(await cdpAlive())) {
      console.log(JSON.stringify({ ok: true, cerrado: false }));
    } else {
      const { browser } = await conectar();
      const cdp = await browser.newBrowserCDPSession();
      await cdp.send('Browser.close').catch(() => {});
      console.log(JSON.stringify({ ok: true, cerrado: true }));
    }
  } else {
    console.log('Uso: node cli.js chrome | sesion | cerrar');
  }
} catch (err) {
  console.log(JSON.stringify({ ok: false, motivo: String(err.message || err) }));
  process.exit(1);
}
