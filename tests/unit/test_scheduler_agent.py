import json
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agents.scheduler.graph import SchedulerAgent
from agents.scheduler.state import (
    CommutePlan,
    DecisionAction,
    FlightStatus,
    SchedulerState,
    TrafficStatus,
    UserContext,
)


@pytest.mark.asyncio
async def test_scheduler_agent_happy_path():
    """
    Verifies the full graph execution flow with mocked tools and LLMs.
    """
    # 1. Setup Mocks
    mock_traffic = MagicMock()
    mock_traffic.get_travel_time = AsyncMock(
        return_value=MagicMock(status=TrafficStatus.HEAVY, duration_seconds=3600)
    )

    mock_flight = MagicMock()
    mock_flight.get_status = AsyncMock(
        return_value=MagicMock(
            status=FlightStatus.ON_TIME, estimated_departure=datetime.now()
        )
    )

    # Mock LLM Responses as JSON strings
    mock_context = {
        "user_id": "u1",
        "origin": "Home",
        "destination": "LAX",
        "flight_number": "UA123",
    }
    mock_plan = {
        "metrics_analyzed": True,
        "buffer_minutes_remaining": 15,
        "recommended_action": "nudge_leave_now",
        "reasoning_trace": "Traffic heavy",
        "notification_message": "Leave now!",
    }

    with (
        patch("agents.scheduler.graph.TrafficClient", return_value=mock_traffic),
        patch("agents.scheduler.graph.FlightClient", return_value=mock_flight),
        patch("agents.factory.ModelFactory.get_fast") as mock_fast,
        patch("agents.factory.ModelFactory.get_pro") as mock_pro,
    ):

        fast_instance = MagicMock()
        pro_instance = MagicMock()
        mock_fast.return_value = fast_instance
        mock_pro.return_value = pro_instance

        # Mock ainvoke
        mock_fast_msg = MagicMock()
        mock_fast_msg.content = json.dumps(mock_context)
        mock_fast_msg.response_metadata = {"usage": {"total_tokens": 10}}
        fast_instance.ainvoke = AsyncMock(return_value=mock_fast_msg)

        mock_pro_msg = MagicMock()
        mock_pro_msg.content = json.dumps(mock_plan)
        mock_pro_msg.response_metadata = {"usage": {"total_tokens": 15}}
        pro_instance.ainvoke = AsyncMock(return_value=mock_pro_msg)

        # 2. Init Agent
        agent = SchedulerAgent()

        # 3. Execute
        initial_state = {
            "user_id": "u1",
            "raw_query": "I need to get to LAX for flight UA123 from Home",
            "error_log": [],
            "retry_count": 0,
            "execution_trace": [],
        }

        final_state = await agent.runner.ainvoke(initial_state)

        # 4. Assertions
        assert final_state["user_context"].user_id == "u1"
        assert final_state["plan"].recommended_action == DecisionAction.NUDGE_LEAVE_NOW

        # Verify Tool Calls
        mock_traffic.get_travel_time.assert_awaited_once()
        mock_flight.get_status.assert_awaited_once()


@pytest.mark.asyncio
async def test_self_healing_retry():
    """
    Verifies that the agent retries when extraction fails.
    """
    mock_traffic = MagicMock()
    mock_traffic.get_travel_time = AsyncMock(
        return_value=MagicMock(status=TrafficStatus.CLEAR, duration_seconds=1800)
    )

    mock_flight = MagicMock()
    mock_flight.get_status = AsyncMock(
        return_value=MagicMock(
            status=FlightStatus.ON_TIME, estimated_departure=datetime.now()
        )
    )

    with (
        patch("agents.scheduler.graph.TrafficClient", return_value=mock_traffic),
        patch("agents.scheduler.graph.FlightClient", return_value=mock_flight),
        patch("agents.factory.ModelFactory.get_fast") as mock_fast,
        patch("agents.factory.ModelFactory.get_pro") as mock_pro,
    ):

        fast_instance = MagicMock()
        pro_instance = MagicMock()
        mock_fast.return_value = fast_instance
        mock_pro.return_value = pro_instance

        # Mock ainvoke with side effects
        mock_fast_msg_fail = MagicMock()
        mock_fast_msg_fail.content = "Invalid garbage"

        mock_fast_msg_ok = MagicMock()
        mock_fast_msg_ok.content = json.dumps(
            {
                "user_id": "u1",
                "origin": "A",
                "destination": "B",
                "flight_number": "UA111",
            }
        )
        mock_fast_msg_ok.response_metadata = {"usage": {"total_tokens": 10}}

        fast_instance.ainvoke = AsyncMock(
            side_effect=[mock_fast_msg_fail, mock_fast_msg_ok]
        )

        mock_pro_msg = MagicMock()
        mock_pro_msg.content = json.dumps(
            {
                "metrics_analyzed": True,
                "buffer_minutes_remaining": 10,
                "recommended_action": "wait",
                "reasoning_trace": "ok",
            }
        )
        mock_pro_msg.response_metadata = {"usage": {"total_tokens": 5}}
        pro_instance.ainvoke = AsyncMock(return_value=mock_pro_msg)

        agent = SchedulerAgent()
        initial_state = {
            "user_id": "u1",
            "raw_query": "go to lax",
            "retry_count": 0,
            "error_log": [],
            "execution_trace": [],
        }

        final_state = await agent.runner.ainvoke(initial_state)

        # Should have succeeded eventually
        assert final_state["user_context"] is not None
        # Should have at least 1 error in log (the JSON decode failure)
        assert len(final_state["error_log"]) >= 1
