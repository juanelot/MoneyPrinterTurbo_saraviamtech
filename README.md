# MoneyPrinterTurbo — SaraviaMtech Edition

Una versión mejorada de [MoneyPrinterTurbo](https://github.com/harry0703/MoneyPrinterTurbo) con una interfaz web moderna construida desde cero en **Next.js 16 + TypeScript**.

> **Créditos:** Este proyecto está basado en [MoneyPrinterTurbo](https://github.com/harry0703/MoneyPrinterTurbo) de [@harry0703](https://github.com/harry0703). Todos los créditos del motor de generación de videos (FastAPI backend, FFmpeg pipeline, Azure TTS, Pexels/Pixabay integration) corresponden al proyecto original.

---

## ¿Qué es?

Genera videos cortos virales automáticamente con IA:

1. **Guión** — GPT-4o mini escribe el guión según tu tema
2. **Voz** — Azure TTS Edge sintetiza la narración (331+ voces, gratis)
3. **Clips** — Descarga clips de Pexels, Pixabay, o usa tus propios videos
4. **Video final** — FFmpeg ensambla, añade subtítulos quemados y música de fondo

---

## Mejoras de esta versión (SaraviaMtech UI)

| Característica | Original (Streamlit) | Esta versión (Next.js) |
|---|---|---|
| Interfaz | Streamlit básico | Dark theme moderno, animaciones |
| Voces disponibles | Manual (~80) | 331 voces Azure + 40+ adicionales |
| Logs en tiempo real | Terminal externa | Panel visual en la UI |
| Timeout FFmpeg | Sin aviso | Banner automático + 30 min de espera |
| Biblioteca de videos | No existe | Grid con player, descarga y eliminación |
| Medios locales | Solo ruta manual | Subida de archivos desde la UI |
| Caché de clips | No gestionable | Botón limpiar caché con info de tamaño |
| Fuente de clips | Pexels solamente | Pexels + Pixabay + Local |
| Preview de voz | No existe | Preview con player de audio integrado |

---

## Estructura del proyecto

```
MoneyPrinterTurbo_saraviamtech/
├── MoneyPrinterTurbo/          # Backend Python (FastAPI) — proyecto original
│   ├── app/
│   ├── storage/
│   │   ├── tasks/              # Videos generados
│   │   ├── cache_videos/       # Clips descargados de Pexels/Pixabay
│   │   └── local_videos/       # Tus videos locales
│   ├── config.toml             # Configuración principal
│   └── main.py
└── mpt-ui/                     # Frontend Next.js (esta mejora)
    ├── app/
    │   ├── page.tsx            # Root — tabs Crear / Mis videos
    │   └── api/library/        # API para gestión de biblioteca
    ├── components/
    │   ├── VideoForm.tsx        # Formulario principal
    │   ├── GenerationProgress.tsx
    │   ├── VideoResult.tsx
    │   ├── VideoLibrary.tsx     # Biblioteca de videos
    │   └── LogPanel.tsx         # Panel de logs en tiempo real
    └── lib/
        └── voices.ts            # 331 voces Azure generadas desde azure_voices.json
```

---

## Instalación

### Requisitos previos

- Python 3.10+
- Node.js 18+
- FFmpeg instalado y en PATH
- ImageMagick (para subtítulos)

### 1. Clonar el repositorio

```bash
git clone https://github.com/juanelot/MoneyPrinterTurbo_saraviamtech.git
cd MoneyPrinterTurbo_saraviamtech
```

### ⚠️ Requisito: Git LFS

Las canciones MP3 y fuentes TTF/TTC se almacenan con **Git LFS**. Asegúrate de tenerlo instalado antes de clonar:

```bash
# Instalar Git LFS (solo una vez por máquina)
git lfs install
```

Descarga en Windows: https://git-lfs.com — con LFS instalado el `git clone` descarga todo automáticamente.

### 2. Configurar el backend

```bash
cd MoneyPrinterTurbo
python -m venv .venv
.venv\Scripts\activate        # Windows
pip install -r requirements.txt
```

Edita `config.toml` y agrega tus API keys:

```toml
[app]
openai_api_key = "sk-..."          # GPT-4o mini para guiones
pexels_api_keys = ["tu-key"]       # gratis en pexels.com/api
pixabay_api_keys = ["tu-key"]      # gratis en pixabay.com/api/docs
```

Inicia el backend:

```bash
python main.py
# Corre en http://localhost:8080
```

### 3. Configurar el frontend

```bash
cd ../mpt-ui
npm install
npm run dev
# Corre en http://localhost:3000
```

---

## Uso

1. Abre `http://localhost:3000`
2. Escribe el tema del video en "Asunto"
3. Elige fuente de clips: **Pexels**, **Pixabay** o **Local**
4. Selecciona voz (filtra por idioma)
5. Haz clic en **Generar video**
6. Espera 5–15 minutos (FFmpeg ensambla el video final)
7. Descarga desde la pantalla de resultado o desde **Mis videos**

### Medios locales

Si quieres usar tus propios clips:
- Selecciona "Local (archivos propios)" como fuente
- Sube videos (MP4, MOV, AVI, FLV, MKV) o imágenes (JPG, PNG)
- **Resolución mínima: lado corto ≥ 400px** (clips verticales de IA tipo 464×832 sirven).
  Los que no cumplan se descartan con un aviso en los logs.
- Las imágenes se convierten a clips con efecto zoom (~30-60s de procesado por
  imagen — sube solo las necesarias: con clips de 4s, ~15 imágenes ≈ 1 min de video)
- Si un archivo aparece como "skip unreadable local material", está corrupto o es
  una imagen renombrada como .mp4 — re-exportarlo

### Música de fondo personalizada

En "Música de fondo" hay 3 opciones: **Sin música**, **Aleatoria** (MP3s incluidos
en `resource/songs`) y **Personalizada**:
- Al elegir "Personalizada" aparece el botón **Subir música** (MP3) y la lista de
  canciones subidas — haz clic en una para seleccionarla
- Sin canción seleccionada el video sale **sin** música
- Disponible tanto en "Crear video" como en el modo Zenn; las canciones subidas
  se comparten entre ambos
- En el VPS las canciones persisten en `/root/mpt-data/songs` (ver [DEPLOY.md](DEPLOY.md))

---

## CLI de automatización (`zenn_cli.py`)

Script de línea de comandos para generar videos **sin abrir el navegador**, ideal para
automatización, cron o que lo dispare otro agente/app (ej. **Hermes**, n8n). Usa el mismo
REST del backend, así que el resultado es idéntico al de la web. **Cubre las 3 formas de generar:**

| Modo | Qué hace |
|---|---|
| `--modo kie` (default) | Video estilo Zenn con imágenes generadas por IA (Kie AI) |
| `--modo local` | Video estilo Zenn con TUS imágenes (sube una carpeta, orden alfabético) |
| `--modo video` | Video clásico con clips de Pexels / Pixabay / locales |

### Requisitos

```bash
pip install requests        # única dependencia del CLI
```

### Configuración por entorno

```bash
# URL base de la API (default: el VPS público)
export MPT_API_BASE="https://virales.saraviamtech.com/api/mpt/v1"
# o local:  export MPT_API_BASE="http://localhost:8080/api/v1"

# Solo si activaste auth básica en Traefik
export MPT_BASIC_AUTH="usuario:password"
```

### Ejemplos

```bash
# 1) Kie AI con un guion propio y tope de imágenes (recomendado fijar max-images)
python zenn_cli.py --tema "Mundial 2026" --guion guion.txt --max-images 207 --out ./videos

# 2) Con un perfil guardado (voz, subtítulos, estilo, etc.) — ver perfil_zenn.example.json
python zenn_cli.py --perfil perfil_zenn.json --tema "Mundial 2026" --guion guion.txt

# 3) Imágenes locales: sube y ordena alfabéticamente la carpeta
python zenn_cli.py --modo local --tema "Mi video" --guion guion.txt --imagenes-dir ./mis_imagenes

# 4) Video clásico con clips de Pexels
python zenn_cli.py --modo video --tema "Datos del espacio" --fuente-clips pexels --terminos "space,stars"

# 5) Por lotes: un tema por línea, el backend genera cada guion
python zenn_cli.py --perfil perfil_zenn.json --lote temas.txt --parrafos 30 --out ./videos
```

### Perfil de configuración

Guarda tu combinación favorita (voz, subtítulos, estilo, etc.) en un JSON y reutilízala con
`--perfil`. Cualquier flag CLI **sobreescribe** lo que venga en el perfil. Plantilla completa
en [`perfil_zenn.example.json`](perfil_zenn.example.json). Cópiala a `perfil_zenn.json` y edítala.

### Controles disponibles (1:1 con la web)

`--voz`, `--voz-velocidad`, `--voz-volumen`, `--sin-voz`, `--musica`, `--musica-volumen`,
`--sin-subtitulos`, `--sub-posicion`, `--fuente`, `--tam-fuente`, `--color-texto`,
`--color-contorno`, `--grosor-contorno`, `--aspect`, `--codec`, `--tematica`, `--estilo`,
`--min-dur`, `--max-images`, `--idioma`, `--parrafos`, `--instrucciones`, `--capitulos`,
`--timeout`. Modo video además: `--fuente-clips`, `--terminos`, `--concat`, `--transicion`, `--dur-clip`.

Ver todo con `python zenn_cli.py --help`.

### Integración con Hermes (u otro agente)

El CLI imprime el progreso por stdout y termina con código `0` (éxito) o `1` (error), así que
cualquier orquestador lo invoca como un comando normal:

1. Prepara un `perfil_zenn.json` con tu configuración base.
2. Que Hermes ejecute el comando, p. ej.:
   `python zenn_cli.py --perfil perfil_zenn.json --tema "{{tema}}" --max-images 207 --out /ruta/salida`
3. El MP4 final queda en la carpeta `--out` con nombre `tema-slug-<taskid>.mp4`.
4. Para varios videos de una vez, usa `--lote temas.txt` (un tema por línea).

> El `--timeout` por defecto es 2 h (no se corta como el navegador a los 40 min). Si generas
> muchas imágenes con Kie, el render puede tardar bastante; el CLI espera hasta que termina.

---

## Despliegue en producción (VPS)

Guía completa en **[DEPLOY.md](DEPLOY.md)** (Portainer + Traefik + Docker Swarm).
Resumen: datos persistentes en `/root/mpt-data/` (`config.toml`, `storage/`,
`songs/`), imágenes construidas en el VPS, auth básica en Traefik. Para actualizar:
`git pull` + rebuild + `docker service update --force`; si cambió `docker-stack.yml`,
re-desplegar el stack.

---

## Variables de configuración importantes

| Parámetro | Descripción |
|---|---|
| `openai_api_key` | Clave de OpenAI para generación de guiones |
| `pexels_api_keys` | Array de keys de Pexels |
| `pixabay_api_keys` | Array de keys de Pixabay |
| `llm_provider` | Proveedor LLM: `openai`, `ollama`, `moonshot`, etc. |
| `openai_model_name` | Modelo a usar (default: `gpt-4o-mini`) |

---

## Licencia

El backend ([MoneyPrinterTurbo](https://github.com/harry0703/MoneyPrinterTurbo)) mantiene su licencia original MIT.  
La interfaz (`mpt-ui`) desarrollada por **SaraviaMtech** — uso libre con atribución.

---

*Desarrollado por [SaraviaMtech](https://github.com/juanelot)*
