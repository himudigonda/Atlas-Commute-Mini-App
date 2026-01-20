import asyncio
import json
import os
from pathlib import Path
from datetime import datetime

from agents.scheduler.state import FlightMetrics, FlightStatus
import structlog

logger = structlog.get_logger()

class FlightClient:
    """
    Simulates AviationStack/FlightAware API.
    """
    
    def __init__(self, mock_scenario: str = "flight_delayed.json"):
        self.mock_mode = os.getenv("MOCK_MODE", "true").lower() == "true"
        self.mock_path = Path(__file__).parent.parent / "mocks" / mock_scenario

    async def get_status(self, flight_number: str) -> FlightMetrics:
        logger.info("tool.flight.start", flight=flight_number)
        
        # Simulate API latency
        await asyncio.sleep(0.3)

        if self.mock_mode:
            return await self._get_mock_data(flight_number)
        else:
            raise NotImplementedError("Real flight API not configured")

    async def _get_mock_data(self, flight_number: str) -> FlightMetrics:
        try:
            content = await asyncio.to_thread(self.mock_path.read_text, encoding="utf-8")
            data = json.loads(content)
            
            # Override mock flight number to match request for realism
            data["flight_number"] = flight_number
            
            metrics = FlightMetrics.model_validate(data)
            logger.info("tool.flight.success", status=metrics.status)
            return metrics
            
        except Exception as e:
            logger.error("tool.flight.failed", error=str(e))
            # Fail-safe return
            return FlightMetrics(
                flight_number=flight_number,
                status=FlightStatus.ON_TIME,
                scheduled_departure=datetime.now(),
                estimated_departure=datetime.now(),
                terminal="N/A",
                gate="N/A"
            )
