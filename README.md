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

### ⚠️ Obtener canciones y fuentes (paso obligatorio)

Este repo no incluye los archivos binarios pesados (MP3 de música de fondo y fuentes TTF/TTC). Descárgalos del repositorio original:

```bash
# Opción A — clonar el repo original y copiar los recursos
git clone https://github.com/harry0703/MoneyPrinterTurbo.git temp-original
cp -r temp-original/resource/songs MoneyPrinterTurbo/resource/songs
cp -r temp-original/resource/fonts MoneyPrinterTurbo/resource/fonts
rm -rf temp-original
```

```bash
# Opción B — descargar solo los recursos sin clonar todo
# Ve a https://github.com/harry0703/MoneyPrinterTurbo y descarga manualmente
# las carpetas resource/songs/ y resource/fonts/
# y colócalas en MoneyPrinterTurbo/resource/
```

Sin las canciones el video se generará **sin música de fondo**. Sin las fuentes los **subtítulos fallarán**.

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
- Sube tus videos (MP4, MOV, AVI, MKV — mínimo 1920×1080, clips de 3s+)
- Selecciona cuáles usar y genera

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
