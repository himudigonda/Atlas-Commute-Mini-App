from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agents.scheduler.graph import SchedulerAgent
from agents.scheduler.state import FlightStatus, TrafficStatus, UserContext


@pytest.mark.asyncio
async def test_llm_malformed_json_self_healing():
    """Rule 33: Test that the agent recovers from malformed LLM JSON output."""
    with (
        patch("agents.factory.ModelFactory.get_fast") as mock_flash,
        patch("agents.factory.ModelFactory.get_pro") as mock_pro,
    ):

        mock_model = MagicMock()
        mock_flash.return_value = mock_model
        mock_pro.return_value = MagicMock()

        agent = SchedulerAgent()

        # Mock for token tracking call (first ainvoke)
        mock_response = MagicMock()
        mock_response.response_metadata = {"usage": {"total_tokens": 10}}
        mock_model.ainvoke = AsyncMock(return_value=mock_response)

        # Mock for structured output (with_structured_output call)
        mock_structured = AsyncMock()
        mock_structured.side_effect = [
            Exception("Output: 'invalid' is not valid JSON"),
            UserContext(
                user_id="u1", origin="A", destination="B", flight_number="UA123"
            ),
        ]
        mock_model.with_structured_output.return_value.ainvoke = mock_structured

        state = {"raw_query": "Need to go", "retry_count": 0, "error_log": []}

        # Run node directly
        result = await agent.node_classify(state)

        # Since it failed first, it should return incremented retry_count
        assert result["retry_count"] == 1
        assert len(result["error_log"]) == 1


@pytest.mark.asyncio
async def test_tool_failure_graceful_degradation():
    """Rule 15: Test system behavior when external tools (Traffic/Flight) fail."""
    with (
        patch("agents.factory.ModelFactory.get_fast"),
        patch("agents.factory.ModelFactory.get_pro"),
    ):

        agent = SchedulerAgent()
        with patch(
            "tools.clients.traffic_client.TrafficClient.get_travel_time",
            side_effect=Exception("API Down"),
        ):

            state = {
                "user_context": UserContext(
                    user_id="u1", origin="A", destination="B", flight_number="UA1"
                ),
                "raw_query": "check traffic",
            }
            # The node_fetch_context should catch this
            result = await agent.node_fetch_context(state)
            assert "Tool Failure: API Down" in result["error_log"][0]
