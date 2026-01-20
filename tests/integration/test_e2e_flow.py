from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from agents.scheduler.state import CommutePlan, DecisionAction, UserContext
from api.main import app

client = TestClient(app)


@pytest.mark.asyncio
async def test_end_to_end_flow():
    """
    Simulates a full request lifecycle ensuring all components wire together.
    """

    # 1. Setup Mocks for the Heavy Lifting (LLM)
    mock_context_json = {
        "user_id": "e2e_user",
        "origin": "Downtown",
        "destination": "JFK",
        "flight_number": "UA100",
        "target_arrival_time": None,
    }

    mock_plan_json = {
        "metrics_analyzed": True,
        "buffer_minutes_remaining": 20,
        "recommended_action": "nudge_leave_now",
        "reasoning_trace": "Traffic spike detected.",
        "notification_message": "Leave NOW.",
    }

    # Patch the Factory to return mocks
    with (
        patch("agents.factory.ModelFactory.get_fast") as mock_fast,
        patch("agents.factory.ModelFactory.get_pro") as mock_pro,
    ):

        # Mock Model instances
        fast_instance = MagicMock()
        pro_instance = MagicMock()
        mock_fast.return_value = fast_instance
        mock_pro.return_value = pro_instance

        # Mock ainvoke for raw text responses
        import json

        mock_fast_msg = MagicMock()
        mock_fast_msg.content = json.dumps(mock_context_json)
        mock_fast_msg.response_metadata = {"usage": {"total_tokens": 10}}
        fast_instance.ainvoke = AsyncMock(return_value=mock_fast_msg)

        mock_pro_msg = MagicMock()
        mock_pro_msg.content = json.dumps(mock_plan_json)
        mock_pro_msg.response_metadata = {"usage": {"total_tokens": 15}}
        pro_instance.ainvoke = AsyncMock(return_value=mock_pro_msg)

        # 2. Execute Request
        payload = {"query": "Traffic check for UA100", "user_id": "test_e2e"}
        response = client.post("/v1/plan", json=payload)

        # 3. Assertions
        assert response.status_code == 200
        data = response.json()

        assert data["success"] is True
        assert data["plan"]["recommended_action"] == "nudge_leave_now"
        assert data["trace_id"] == "test_e2e"
