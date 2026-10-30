# Use an official Python runtime as a parent image
# bookworm: bullseye salio de soporte (2026-08) y sus mirrors devuelven 404
FROM python:3.11-slim-bookworm

# Set the working directory in the container
WORKDIR /MoneyPrinterTurbo

# 设置/MoneyPrinterTurbo目录权限为777
RUN chmod 777 /MoneyPrinterTurbo

ENV PYTHONPATH="/MoneyPrinterTurbo"

# Install system dependencies (mirror oficial de Debian)
RUN apt-get update && apt-get install -y --no-install-recommends \
        git \
        imagemagick \
        ffmpeg \
        curl \
        ca-certificates && \
    rm -rf /var/lib/apt/lists/*

# Estudio: CLI de Claude Code (guion, catalogo visual y asignacion con la
# suscripcion, sin API key). La sesion se persiste con CLAUDE_CONFIG_DIR en un
# volumen, o se pasa CLAUDE_CODE_OAUTH_TOKEN (sale de `claude setup-token`).
RUN curl -fsSL https://claude.ai/install.sh | bash
ENV PATH="/root/.local/bin:${PATH}"

# Estudio: graficos animados con HyperFrames (motion/). Necesita Node 22 y las
# librerias de su Chrome headless (lo descarga `hyperframes browser ensure`).
COPY --from=node:22-bookworm-slim /usr/local/bin/node /usr/local/bin/node
COPY --from=node:22-bookworm-slim /usr/local/lib/node_modules /usr/local/lib/node_modules
RUN ln -s /usr/local/lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm && \
    ln -s /usr/local/lib/node_modules/npm/bin/npx-cli.js /usr/local/bin/npx && \
    apt-get update && apt-get install -y --no-install-recommends \
        unzip libgbm1 libnss3 libatk-bridge2.0-0 libdrm2 libxcomposite1 libxdamage1 libxrandr2 \
        libcups2 libasound2 libpangocairo-1.0-0 libxshmfence1 libgtk-3-0 \
        fonts-liberation fonts-noto-core fonts-noto-color-emoji fonts-dejavu-core fontconfig && \
    rm -rf /var/lib/apt/lists/* && fc-cache -f
ENV CONTAINER=true HYPERFRAMES_NO_TELEMETRY=1 HYPERFRAMES_NO_UPDATE_CHECK=1 DO_NOT_TRACK=1
# Modelos de Whisper ("base" del Estudio y "small" de la Fabrica, ~460 MB) en el volumen de storage:
# se bajan una vez y sobreviven a recrear el contenedor
ENV HF_HOME=/MoneyPrinterTurbo/storage/.modelos
COPY motion/package.json motion/package-lock.json ./motion/
RUN cd motion && npm ci --no-audit --no-fund && node node_modules/hyperframes/bin/hyperframes.mjs browser ensure

# Fix security policy for ImageMagick
RUN sed -i '/<policy domain="path" rights="none" pattern="@\*"/d' /etc/ImageMagick-6/policy.xml

# Copy only the requirements.txt first to leverage Docker cache
COPY requirements.txt ./

# Install Python dependencies (PyPI oficial; el VPS esta en Europa)
RUN pip install --no-cache-dir --retries 3 --timeout 60 -r requirements.txt

# Now copy the rest of the codebase into the image
COPY . .

# Expose the port the app runs on
EXPOSE 8501

# Command to run the application
CMD ["streamlit", "run", "./webui/Main.py","--browser.serverAddress=127.0.0.1","--server.enableCORS=True","--browser.gatherUsageStats=False"]

# 1. Build the Docker image using the following command
# docker build -t moneyprinterturbo .

# 2. Run the Docker container using the following command
## For Linux or MacOS:
# docker run -v $(pwd)/config.toml:/MoneyPrinterTurbo/config.toml -v $(pwd)/storage:/MoneyPrinterTurbo/storage -p 127.0.0.1:8501:8501 moneyprinterturbo
## For Windows:
# docker run -v ${PWD}/config.toml:/MoneyPrinterTurbo/config.toml -v ${PWD}/storage:/MoneyPrinterTurbo/storage -p 127.0.0.1:8501:8501 moneyprinterturbo
