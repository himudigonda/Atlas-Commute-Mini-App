from enum import Enum
from typing import Any, Dict

import structlog

from engine.cache.redis_svc import redis_client

logger = structlog.get_logger()


class MetricKey(str, Enum):
    REQUESTS_TOTAL = "metrics:requests:total"
    REQUESTS_SUCCESS = "metrics:requests:success"
    REQUESTS_FAILED = "metrics:requests:failed"
    CACHE_HITS = "metrics:cache:hits"
    CACHE_MISSES = "metrics:cache:misses"
    TOKENS_USED = "metrics:tokens:total"
    LATENCY_MS = "metrics:latency:last"
    AGENT_LATENCY_MS = "metrics:latency:agent"


class MetricsService:
    """
    Atomic counter service using Redis.
    Allows real-time tracking of system throughput across workers.
    """

    async def increment(self, key: MetricKey, amount: int = 1) -> None:
        """Increment a specific metric counter."""
        if not redis_client.enabled:
            return

        try:
            await redis_client.client.incrby(key.value, amount)
        except Exception as e:
            logger.warning("metrics.incr_failed", key=key, error=str(e))

    async def set(self, key: MetricKey, value: Any) -> None:
        """Set a specific metric value."""
        if not redis_client.enabled:
            return

        try:
            await redis_client.client.set(key.value, value)
        except Exception as e:
            logger.warning("metrics.set_failed", key=key, error=str(e))

    async def get_snapshot(self) -> Dict[str, int]:
        """Fetch all metrics for the dashboard."""
        if not redis_client.enabled:
            return {"status": "redis_offline"}

        try:
            # Pipeline for performance
            pipe = redis_client.client.pipeline()
            keys = [k.value for k in MetricKey]
            for k in keys:
                pipe.get(k)

            values = await pipe.execute()

            # Map keys back to clean names (remove 'metrics:' prefix for display)
            result = {}
            for i, key_enum in enumerate(MetricKey):
                val = values[i]
                clean_name = key_enum.value.replace("metrics:", "")
                result[clean_name] = int(val) if val else 0

            return result
        except Exception as e:
            logger.error("metrics.snapshot_failed", error=str(e))
            return {}


metrics = MetricsService()
