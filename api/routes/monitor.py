import structlog
from fastapi import APIRouter, status
from pydantic import BaseModel

from agents.scheduler.state import UserContext
from engine.queue.tasks import monitor_commute_task

logger = structlog.get_logger()
router = APIRouter(prefix="/v1", tags=["Background Monitoring"])


class MonitorRequest(BaseModel):
    user_context: UserContext


class MonitorResponse(BaseModel):
    task_id: str
    status: str


@router.post(
    "/monitor",
    response_model=MonitorResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Start a background polling task for this commute",
)
async def start_monitoring(request: MonitorRequest):
    """
    Offloads the monitoring logic to the Celery worker queue.
    """
    log = logger.bind(user_id=request.user_context.user_id)
    log.info("api.monitor_requested")

    # Serialize Pydantic model to JSON for Celery
    payload = request.user_context.model_dump(mode="json")

    # Trigger Task
    task = monitor_commute_task.delay(payload)

    return MonitorResponse(task_id=str(task.id), status="queued")
