import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime
from agents.scheduler.graph import SchedulerAgent
from agents.scheduler.state import SchedulerState, UserContext, CommutePlan, DecisionAction, TrafficStatus, FlightStatus

@pytest.mark.asyncio
async def test_scheduler_agent_happy_path():
    """
    Verifies the full graph execution flow with mocked tools and LLMs.
    """
    # 1. Setup Mocks
    mock_traffic = MagicMock()
    mock_traffic.get_travel_time = AsyncMock(return_value=MagicMock(
        status=TrafficStatus.HEAVY, duration_seconds=3600
    ))
    
    mock_flight = MagicMock()
    mock_flight.get_status = AsyncMock(return_value=MagicMock(
        status=FlightStatus.ON_TIME, estimated_departure=datetime.now()
    ))

    # Mock LLM Responses
    mock_context = UserContext(
        user_id="u1", origin="Home", destination="LAX", flight_number="UA123"
    )
    mock_plan = CommutePlan(
        metrics_analyzed=True,
        buffer_minutes_remaining=15,
        recommended_action=DecisionAction.NUDGE_LEAVE_NOW,
        reasoning_trace="Traffic heavy",
        notification_message="Leave now!"
    )

    with patch("agents.scheduler.graph.TrafficClient", return_value=mock_traffic), \
         patch("agents.scheduler.graph.FlightClient", return_value=mock_flight), \
         patch("agents.factory.ModelFactory.get_fast") as mock_fast, \
         patch("agents.factory.ModelFactory.get_pro") as mock_pro:
         
        # Configure LLM Mocks to return our Pydantic models
        mock_fast.return_value.with_structured_output.return_value.ainvoke = AsyncMock(
            return_value=mock_context
        )
        mock_pro.return_value.with_structured_output.return_value.ainvoke = AsyncMock(
            return_value=mock_plan
        )

        # 2. Init Agent
        agent = SchedulerAgent()
        
        # 3. Execute
        initial_state = {
            "raw_query": "I need to get to LAX for flight UA123 from Home",
            "error_log": [],
            "retry_count": 0,
            "execution_trace": []
        }
        
        final_state = await agent.runner.ainvoke(initial_state)

        # 4. Assertions
        assert final_state["user_context"] == mock_context
        assert final_state["plan"] == mock_plan
        
        # Verify Tool Calls
        mock_traffic.get_travel_time.assert_awaited_once()
        mock_flight.get_status.assert_awaited_once()

@pytest.mark.asyncio
async def test_self_healing_retry():
    """
    Verifies that the agent retries when extraction fails.
    """
    mock_traffic = MagicMock()
    mock_traffic.get_travel_time = AsyncMock(return_value=MagicMock(
        status=TrafficStatus.CLEAR, duration_seconds=1800
    ))
    
    mock_flight = MagicMock()
    mock_flight.get_status = AsyncMock(return_value=MagicMock(
        status=FlightStatus.ON_TIME, estimated_departure=datetime.now()
    ))

    with patch("agents.scheduler.graph.TrafficClient", return_value=mock_traffic), \
         patch("agents.scheduler.graph.FlightClient", return_value=mock_flight), \
         patch("agents.factory.ModelFactory.get_fast") as mock_fast, \
         patch("agents.factory.ModelFactory.get_pro") as mock_pro:

        # First call raises exception, Second call succeeds
        mock_extractor = AsyncMock()
        mock_extractor.ainvoke.side_effect = [
            ValueError("Invalid JSON"),  # Fail 1
            UserContext(user_id="u1", origin="A", destination="B", flight_number="UA111") # Success 2
        ]
        mock_fast.return_value.with_structured_output.return_value = mock_extractor
        
        # Reasoner succeeds immediately
        mock_pro.return_value.with_structured_output.return_value.ainvoke = AsyncMock(
            return_value=CommutePlan(
                metrics_analyzed=True,
                buffer_minutes_remaining=10,
                recommended_action=DecisionAction.WAIT,
                reasoning_trace="ok"
            )
        )

        agent = SchedulerAgent()
        initial_state = {"raw_query": "go to lax", "retry_count": 0, "error_log": [], "execution_trace": []}
        
        final_state = await agent.runner.ainvoke(initial_state)
        
        # Should have succeeded eventually
        assert final_state["user_context"] is not None
        # Should have 1 error in log
        assert len(final_state["error_log"]) == 1
