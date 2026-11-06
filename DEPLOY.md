# Despliegue en VPS (Portainer + Traefik + Docker Swarm)

URL final: **https://virales.saraviamtech.com**

## 1. Preparar datos en el VPS (una sola vez)

```bash
mkdir -p /root/mpt-data/storage /root/mpt-data/songs
# Subir tu config.toml REAL (con las API keys) — NO está en el repo:
# scp MoneyPrinterTurbo/config.toml root@VPS:/root/mpt-data/config.toml
```

La carpeta `/root/mpt-data/songs` se monta sobre `resource/songs` y OCULTA
los MP3 por defecto de la imagen. Copiarlos una sola vez tras clonar el repo:

```bash
cp MoneyPrinterTurbo_saraviamtech/MoneyPrinterTurbo/resource/songs/*.mp3 /root/mpt-data/songs/
```

En `/root/mpt-data/config.toml` verifica:
- `pexels_api_keys`, llm keys, etc.
- `video_codec = "libx264"` (el VPS no tiene GPU NVENC)

## 2. Clonar y construir imágenes (en el VPS)

```bash
apt-get install -y git-lfs && git lfs install
git clone https://github.com/juanelot/MoneyPrinterTurbo_saraviamtech.git
cd MoneyPrinterTurbo_saraviamtech

docker build -t mpt-api:latest ./MoneyPrinterTurbo
docker build -t mpt-ui:latest --build-arg MPT_API_URL=http://api:8080 ./mpt-ui
```

> Git LFS es obligatorio: sin él las fuentes (.ttf) y canciones (.mp3)
> serían punteros vacíos y el render fallaría.

## 3. Generar el hash de la auth básica

```bash
apt-get install -y apache2-utils
htpasswd -nb admin TU_PASSWORD
```

Copiar el resultado en `docker-stack.yml` (label `basicauth.users`),
**duplicando cada `$` como `$$`**.

## 4. Desplegar en Portainer

Stacks → Add stack → pegar el contenido de `docker-stack.yml` → Deploy.
(O por CLI: `docker stack deploy -c docker-stack.yml mpt`)

## 5. DNS

Registro A: `virales.saraviamtech.com` → IP del VPS.
Traefik emite el certificado solo (resolver `letsencryptresolver`).

## Actualizar a una nueva versión

```bash
cd MoneyPrinterTurbo_saraviamtech && git pull
docker build -t mpt-api:latest ./MoneyPrinterTurbo
docker build -t mpt-ui:latest --build-arg MPT_API_URL=http://api:8080 ./mpt-ui
docker service update --force mpt_api
docker service update --force mpt_ui
```

## Estudio (studio.saraviamtech.com)

Es un servicio más del stack. Comparte el backend `api` y usa la misma auth básica.

```bash
mkdir -p /root/mpt-data/claude /root/mpt-data/recursos
docker build -t mpt-api:latest ./MoneyPrinterTurbo          # ya incluye el CLI de Claude
docker build -t estudio-ui:latest --build-arg MPT_API_URL=http://api:8080 ./estudio-ui
```

1. **DNS:** crea un registro A `studio.saraviamtech.com` → IP del VPS. Si quieres otro dominio, cambia la label `Host(...)` en `docker-stack.yml`.
2. **Sesión de Claude**, una sola vez. Hay dos formas:
   - Iniciar sesión dentro del contenedor: `docker exec -it $(docker ps -qf name=mpt_api) claude` y después `/login`. La sesión queda guardada en `/root/mpt-data/claude`.
   - Usar un token: en tu PC ejecuta `claude setup-token` y pon el resultado en `CLAUDE_CODE_OAUTH_TOKEN` (variable de entorno del servicio `api`).
3. **Carpetas de recursos:** lo que copies a `/root/mpt-data/recursos` aparece en el contenedor como `/recursos`. En `config.toml`, limita el acceso con `estudio_carpetas_permitidas = ["/recursos"]`.
4. **Proyectos:** se guardan en `/root/mpt-data/storage/estudio/`.

Para actualizar, añade `docker service update --force mpt_estudio` a los comandos de arriba.


## Notas

- Los videos quedan en `/root/mpt-data/storage/tasks/` (persisten a reinicios).
- Render solo CPU: un 1080×1920 con subtítulos puede tardar 15–40 min según el VPS.
- Las tareas en curso viven en memoria: si el contenedor `api` se reinicia
  a mitad de un video, esa tarea se pierde (los archivos ya generados no).
- El polling del frontend llega hasta 30–40 min; para videos muy largos en
  un VPS lento, revisar igualmente "Mis videos" más tarde.
