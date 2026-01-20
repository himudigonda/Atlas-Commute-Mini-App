import structlog
from fastapi import APIRouter

from engine.telemetry.metrics import metrics

logger = structlog.get_logger()
router = APIRouter(prefix="/v1", tags=["Observability"])


@router.get("/stats", summary="Get system telemetry")
async def get_system_stats():
    """
    Returns real-time counters from the Redis backend.
    Used by the CLI Dashboard.
    """
    snapshot = await metrics.get_snapshot()
    return {"system": "Atlas Commute Orchestrator", "metrics": snapshot}
