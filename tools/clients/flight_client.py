import asyncio
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

import structlog

from agents.scheduler.state import FlightMetrics, FlightStatus

logger = structlog.get_logger()


class FlightClient:
    """
    Simulates AviationStack/FlightAware API.
    Implemented as a Singleton to prevent socket exhaustion.
    """

    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(FlightClient, cls).__new__(cls)
        return cls._instance

    def __init__(self, mock_scenario: str = "flight_delayed.json"):
        # Ensure init only runs once for the singleton
        if hasattr(self, "_initialized"):
            return
        self.mock_mode = os.getenv("MOCK_MODE", "true").lower() == "true"
        self.mock_path = Path(__file__).parent.parent / "mocks" / mock_scenario
        self._initialized = True

    async def get_status(
        self, flight_number: str, target_date: Optional[datetime] = None
    ) -> FlightMetrics:
        logger.info("tool.flight.start", flight=flight_number, target=target_date)

        # Simulate API latency
        await asyncio.sleep(0.3)

        if self.mock_mode:
            return await self._get_mock_data(flight_number, target_date)
        else:
            raise NotImplementedError("Real flight API not configured")

    async def _get_mock_data(
        self, flight_number: str, target_date: Optional[datetime] = None
    ) -> FlightMetrics:
        try:
            content = await asyncio.to_thread(
                self.mock_path.read_text, encoding="utf-8"
            )
            data = json.loads(content)

            # Rule: If target_date is provided, shift the mock data to that specific day
            # but keep the time (hours/mins) from the mock file for consistency.
            if target_date:
                sched = datetime.fromisoformat(data["scheduled_departure"])
                est = datetime.fromisoformat(data["estimated_departure"])

                data["scheduled_departure"] = target_date.replace(
                    hour=sched.hour, minute=sched.minute, second=sched.second
                ).isoformat()

                data["estimated_departure"] = target_date.replace(
                    hour=est.hour, minute=est.minute, second=est.second
                ).isoformat()

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
                gate="N/A",
            )
