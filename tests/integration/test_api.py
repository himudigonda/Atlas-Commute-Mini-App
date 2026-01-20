from fastapi.testclient import TestClient
from unittest.mock import MagicMock, AsyncMock
from api.main import app
from api.routes.commute import get_agent
from agents.scheduler.state import CommutePlan, DecisionAction

client = TestClient(app)

# --- Mock Data ---
MOCK_PLAN = CommutePlan(
    metrics_analyzed=True,
    buffer_minutes_remaining=45,
    recommended_action=DecisionAction.WAIT,
    reasoning_trace="Traffic is clear.",
    notification_message="All good."
)

def test_health_check():
    """Verify system health endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": "0.1.0"}

def test_plan_commute_success():
    """
    Mock the entire Agent execution to test API contract handling.
    """
    mock_agent = MagicMock()
    # Mock the graph runner's ainvoke method
    mock_agent.runner.ainvoke = AsyncMock(return_value={
        "plan": MOCK_PLAN,
        "error_log": []
    })

    # Override dependency
    app.dependency_overrides[get_agent] = lambda: mock_agent

    payload = {
        "query": "I need to get to JFK for flight BA112 from Brooklyn by 5pm",
        "user_id": "test_user"
    }
    
    response = client.post("/v1/plan", json=payload)
    
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["plan"]["recommended_action"] == "wait"
    
    # Cleanup
    app.dependency_overrides = {}

def test_plan_commute_agent_failure():
    """
    Test how the API handles an agent returning no plan (exhausted retries).
    """
    mock_agent = MagicMock()
    mock_agent.runner.ainvoke = AsyncMock(return_value={
        "plan": None,
        "error_log": ["JSON Parsing Error"]
    })

    app.dependency_overrides[get_agent] = lambda: mock_agent

    payload = {
        "query": "Garbage input",
        "user_id": "test_user"
    }
    
    response = client.post("/v1/plan", json=payload)
    
    assert response.status_code == 200 # We return 200 with success=False
    data = response.json()
    assert data["success"] is False
    assert "JSON Parsing Error" in data["error"]
    
    app.dependency_overrides = {}
