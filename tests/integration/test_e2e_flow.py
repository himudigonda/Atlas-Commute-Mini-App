from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from agents.scheduler.state import CommutePlan, DecisionAction, UserContext
from api.main import app

client = TestClient(app)


@pytest.mark.asyncio
async def test_end_to_end_flow():
    """
    Simulates a full request lifecycle ensuring all components wire together.
    Uses 'MOCK_MODE=true' (default in clients) to avoid real tool API costs.
    Mocks the LLM calls to provide deterministic output.
    """

    # 1. Setup Mocks for the Heavy Lifting (LLM)
    mock_context = UserContext(
        user_id="e2e_user",
        origin="Downtown",
        destination="JFK",
        flight_number="UA100",
        target_arrival_time=None,
    )

    mock_plan = CommutePlan(
        metrics_analyzed=True,
        buffer_minutes_remaining=20,
        recommended_action=DecisionAction.NUDGE_LEAVE_NOW,
        reasoning_trace="Traffic spike detected.",
        notification_message="Leave NOW.",
    )

    # Patch the Factory to return mocks that return our Pydantic objects
    with (
        patch("agents.factory.ModelFactory.get_fast") as mock_fast,
        patch("agents.factory.ModelFactory.get_pro") as mock_pro,
    ):

        # Mock Flash (Extraction)
        mock_fast.return_value.with_structured_output.return_value.ainvoke = AsyncMock(
            return_value=mock_context
        )

        # Mock Pro (Reasoning)
        mock_pro.return_value.with_structured_output.return_value.ainvoke = AsyncMock(
            return_value=mock_plan
        )

        # 2. Execute Request
        payload = {"query": "Traffic check for UA100", "user_id": "test_e2e"}
        response = client.post("/v1/plan", json=payload)

        # 3. Assertions
        assert response.status_code == 200
        data = response.json()

        if not data["success"]:
            print(f"DEBUG: API Error: {data.get('error')}")

        assert data["success"] is True
        assert data["plan"]["recommended_action"] == "nudge_leave_now"

        # Verify Trace ID matches User ID (MVP Logic)
        assert data["trace_id"] == "test_e2e"
