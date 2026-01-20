import asyncio
import json
import os
from pathlib import Path
from typing import Optional

from agents.scheduler.state import TrafficMetrics, TrafficStatus
import structlog

logger = structlog.get_logger()

class TrafficClient:
    """
    Simulates Google Routes API.
    Modes:
    - MOCK: Reads from local JSON to simulate specific traffic conditions.
    - REAL: (Placeholder) Would hit Google Routes API.
    """
    
    def __init__(self, mock_scenario: str = "traffic_heavy.json"):
        self.mock_mode = os.getenv("MOCK_MODE", "true").lower() == "true"
        self.mock_path = Path(__file__).parent.parent / "mocks" / mock_scenario

    async def get_travel_time(self, origin: str, destination: str) -> TrafficMetrics:
        """
        Fetch travel metrics. Simulates network latency.
        """
        logger.info("tool.traffic.start", origin=origin, destination=destination)
        
        # Simulate network I/O latency
        await asyncio.sleep(0.5)

        if self.mock_mode:
            return await self._get_mock_data()
        else:
            return await self._get_real_data(origin, destination)

    async def _get_mock_data(self) -> TrafficMetrics:
        try:
            if not self.mock_path.exists():
                raise FileNotFoundError(f"Mock file not found: {self.mock_path}")

            # Async file reading to avoid blocking event loop
            content = await asyncio.to_thread(self.mock_path.read_text, encoding="utf-8")
            data = json.loads(content)
            
            # Pydantic validation (The Contract)
            metrics = TrafficMetrics.model_validate(data)
            logger.info("tool.traffic.success", status=metrics.status)
            return metrics
            
        except Exception as e:
            logger.error("tool.traffic.failed", error=str(e))
            # Fallback for resilience
            return TrafficMetrics(
                distance_meters=0,
                duration_seconds=0,
                traffic_delay_seconds=0,
                status=TrafficStatus.CLEAR,
                route_summary="Unknown (Error)"
            )

    async def _get_real_data(self, origin: str, destination: str) -> TrafficMetrics:
        # TODO: Implement Google Maps API integration
        raise NotImplementedError("Real traffic API not configured for MVP")
