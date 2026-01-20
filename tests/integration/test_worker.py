from unittest.mock import MagicMock, patch

from agents.scheduler.state import CommutePlan, DecisionAction
from engine.queue.tasks import monitor_commute_task


def test_monitor_task_execution():
    """
    Tests the sync-to-async bridge in the Celery task.
    """
    # Mock Data
    mock_payload = {
        "user_id": "worker_test",
        "origin": "A",
        "destination": "B",
        "flight_number": "UA1",
        "target_arrival_time": None,
    }

    mock_plan = CommutePlan(
        metrics_analyzed=True,
        buffer_minutes_remaining=5,
        recommended_action=DecisionAction.NUDGE_LEAVE_NOW,
        reasoning_trace="Traffic Bad",
        notification_message="Go!",
        input_query="BACKGROUND_POLL",  # Added to match Pydantic model expectations if needed
    )

    # Patch the async runner helper
    with patch("engine.queue.tasks.run_async_agent") as mock_runner:
        # Configure the mock to return a state dict
        mock_runner.return_value = {"plan": mock_plan, "error_log": []}

        # Execute Task Directly (Synchronously)
        result = monitor_commute_task(mock_payload)

        # Assertions
        mock_runner.assert_called_once()
        assert result["status"] == "alert_sent"
        assert result["message"] == "Go!"
