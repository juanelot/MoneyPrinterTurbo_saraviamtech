"""
Cliente para la API de Kie AI (modelo gpt-image-2-text-to-image).

Flujo asíncrono:
  1. POST /api/v1/jobs/createTask  -> devuelve data.taskId
  2. GET  /api/v1/jobs/recordInfo  -> se consulta (polling) hasta state == success/fail
  3. La imagen sale en data.resultJson -> {"resultUrls": ["https://..."]}
     Las URLs expiran a las 24h, así que se descargan de inmediato.

Este módulo es independiente: NO modifica nada del pipeline existente,
solo agrega la capacidad de generar imágenes a partir de un prompt.
"""

import json
import os
import time

import requests
from loguru import logger

from app.config import config
from app.utils import utils

_BASE_URL = "https://api.kie.ai"
_CREATE_TASK_URL = f"{_BASE_URL}/api/v1/jobs/createTask"
_RECORD_INFO_URL = f"{_BASE_URL}/api/v1/jobs/recordInfo"
_MODEL = "gpt-image-2-text-to-image"


def _get_api_key() -> str:
    """Lee la API key de Kie desde config.toml ([app] kie_api_keys)."""
    api_keys = config.app.get("kie_api_keys")
    if not api_keys:
        raise ValueError(
            "\n\n##### kie_api_keys no está configurada #####\n\n"
            f"Agrégala en el archivo config.toml: {config.config_file}\n"
            'Ejemplo:  kie_api_keys = "tu-api-key"\n'
        )
    if isinstance(api_keys, list):
        # admite varias keys; usa la primera no vacía
        api_keys = next((k for k in api_keys if k), None)
        if not api_keys:
            raise ValueError("kie_api_keys está vacía en config.toml")
    return str(api_keys).strip()


def _headers() -> dict:
    return {
        "Authorization": f"Bearer {_get_api_key()}",
        "Content-Type": "application/json",
    }


def create_task(
    prompt: str,
    aspect_ratio: str = "9:16",
    resolution: str = "1K",
) -> str:
    """Crea una tarea de generación y devuelve el taskId."""
    payload = {
        "model": _MODEL,
        "input": {
            "prompt": prompt[:20000],
            "aspect_ratio": aspect_ratio,
        },
    }
    # Nota de la doc: con aspect_ratio "auto" solo se permite 1K; y 1:1 no admite 4K.
    if resolution and aspect_ratio not in ("auto",) and aspect_ratio != "1:1":
        payload["input"]["resolution"] = resolution
    elif resolution and aspect_ratio == "1:1" and resolution != "4K":
        payload["input"]["resolution"] = resolution

    resp = requests.post(
        _CREATE_TASK_URL, headers=_headers(), json=payload, timeout=60
    )
    data = _parse_response(resp, context="createTask")
    task_id = (data.get("data") or {}).get("taskId")
    if not task_id:
        raise RuntimeError(f"Kie createTask no devolvió taskId: {data}")
    return task_id


def query_task(task_id: str) -> dict:
    """Consulta el estado de una tarea. Devuelve el objeto data."""
    resp = requests.get(
        _RECORD_INFO_URL,
        headers=_headers(),
        params={"taskId": task_id},
        timeout=60,
    )
    data = _parse_response(resp, context="recordInfo")
    return data.get("data") or {}


def _parse_response(resp: requests.Response, context: str) -> dict:
    try:
        body = resp.json()
    except Exception:
        raise RuntimeError(
            f"Kie {context} respondió no-JSON (HTTP {resp.status_code}): {resp.text[:300]}"
        )
    code = body.get("code")
    # La API usa code 200 para éxito; otros valores son error aunque HTTP sea 200.
    if code not in (200, None):
        msg = body.get("msg", "")
        raise RuntimeError(f"Kie {context} error code={code}: {msg}")
    return body


def wait_for_result(
    task_id: str,
    timeout: int = 900,
    initial_delay: float = 3.0,
    max_delay: float = 15.0,
) -> str:
    """
    Hace polling con backoff exponencial hasta que la tarea termina.
    Devuelve la URL de la primera imagen generada.
    """
    deadline = time.time() + timeout
    delay = initial_delay
    while time.time() < deadline:
        data = query_task(task_id)
        state = (data.get("state") or "").lower()

        if state == "success":
            return _extract_image_url(data)
        if state == "fail":
            raise RuntimeError(
                f"Kie task {task_id} falló: "
                f"{data.get('failCode', '')} {data.get('failMsg', '')}".strip()
            )
        # waiting / queuing / generating -> seguir esperando
        logger.debug(f"kie task {task_id} state={state}, esperando {delay:.0f}s")
        time.sleep(delay)
        delay = min(delay * 1.5, max_delay)

    raise TimeoutError(f"Kie task {task_id} no terminó en {timeout}s")


def _extract_image_url(data: dict) -> str:
    result_json = data.get("resultJson")
    if not result_json:
        raise RuntimeError(f"Kie task sin resultJson: {data}")
    try:
        result = json.loads(result_json)
    except (json.JSONDecodeError, TypeError):
        raise RuntimeError(f"resultJson no parseable: {result_json}")
    urls = result.get("resultUrls") or []
    if not urls:
        raise RuntimeError(f"resultJson sin resultUrls: {result_json}")
    return urls[0]


def download_image(url: str, save_path: str) -> str:
    """Descarga la imagen a save_path (las URLs de Kie expiran en 24h)."""
    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    resp = requests.get(url, timeout=120, stream=True)
    resp.raise_for_status()
    with open(save_path, "wb") as f:
        for chunk in resp.iter_content(chunk_size=8192):
            if chunk:
                f.write(chunk)
    return save_path


def generate_image(
    prompt: str,
    save_path: str,
    aspect_ratio: str = "9:16",
    resolution: str = "1K",
    timeout: int = 900,
    retries: int = 2,
) -> str:
    """
    Genera UNA imagen a partir de un prompt y la descarga a save_path.
    Conveniencia que encadena create_task + wait_for_result + download_image.
    Reintenta ante errores transitorios (ej. rate-limit 429 o fallo puntual).
    """
    last_err = None
    for attempt in range(retries + 1):
        try:
            task_id = create_task(
                prompt, aspect_ratio=aspect_ratio, resolution=resolution
            )
            logger.info(f"kie task creada: {task_id}")
            url = wait_for_result(task_id, timeout=timeout)
            return download_image(url, save_path)
        except Exception as e:
            last_err = e
            msg = str(e)
            # backoff ante rate-limit / errores temporales
            wait = 5 * (attempt + 1)
            if "429" in msg or "Rate" in msg or "limit" in msg.lower():
                wait = 15 * (attempt + 1)
            if attempt < retries:
                logger.warning(
                    f"reintento {attempt + 1}/{retries} en {wait}s tras error: {msg}"
                )
                time.sleep(wait)
    raise last_err


if __name__ == "__main__":
    out = os.path.join(utils.storage_dir("temp", create=True), "kie_test.png")
    generate_image(
        "A simple beginner drawing made in MS Paint of a primitive human, white background",
        out,
    )
    logger.info(f"imagen guardada en: {out}")
