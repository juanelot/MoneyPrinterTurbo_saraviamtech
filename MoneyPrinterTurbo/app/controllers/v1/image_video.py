"""
Endpoint NUEVO para el flujo "video de imágenes" estilo Zenn.

No modifica nada de los endpoints existentes. Reutiliza el mismo task_manager
(cola/concurrencia) del controlador de video y el patrón de creación de tareas.
"""

from fastapi import BackgroundTasks, Request
from loguru import logger

from app.controllers import base
from app.controllers.manager.base_manager import TaskQueueFullError
from app.controllers.v1.base import new_router
from app.controllers.v1.video import task_manager
from app.models.exception import HttpException
from app.models.schema import ImageVideoRequest, TaskResponse
from app.services import image_task as itm
from app.services import state as sm
from app.utils import utils

router = new_router()


@router.post(
    "/image-video",
    response_model=TaskResponse,
    summary="Generate a Zenn-style video from AI-generated images",
)
def create_image_video(
    background_tasks: BackgroundTasks, request: Request, body: ImageVideoRequest
):
    task_id = utils.get_uuid()
    request_id = base.get_task_id(request)
    try:
        task = {
            "task_id": task_id,
            "request_id": request_id,
            "params": body.model_dump(),
        }
        sm.state.update_task(task_id)
        task_manager.add_task(
            itm.start, task_id=task_id, params=body, stop_at="video"
        )
        logger.success(f"Image-video task created: {utils.to_json(task)}")
        return utils.get_response(200, task)
    except TaskQueueFullError as e:
        sm.state.delete_task(task_id)
        logger.warning(f"reject task (queue full), task_id: {task_id}")
        raise HttpException(
            task_id=task_id, status_code=429, message=f"{request_id}: {str(e)}"
        )
    except ValueError as e:
        raise HttpException(
            task_id=task_id, status_code=400, message=f"{request_id}: {str(e)}"
        )
