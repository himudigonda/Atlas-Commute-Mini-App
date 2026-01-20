from unittest.mock import AsyncMock, patch

import pytest

from engine.telemetry.metrics import MetricKey, MetricsService


@pytest.mark.asyncio
async def test_metrics_increment_success():
    """Test standard increment with mocked Redis."""
    with patch("engine.telemetry.metrics.redis_client") as mock_redis:
        mock_redis.enabled = True
        mock_redis.client.incrby = AsyncMock()

        svc = MetricsService()
        await svc.increment(MetricKey.REQUESTS_TOTAL)

        mock_redis.client.incrby.assert_awaited_once_with(
            MetricKey.REQUESTS_TOTAL.value, 1
        )


@pytest.mark.asyncio
async def test_metrics_disabled_resilience():
    """Ensure no error is raised if Redis is disabled."""
    with patch("engine.telemetry.metrics.redis_client") as mock_redis:
        mock_redis.enabled = False

        svc = MetricsService()
        # Should not raise exception
        await svc.increment(MetricKey.REQUESTS_TOTAL)
