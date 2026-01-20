import json
import time
from typing import Any, Dict, Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from langchain_core.runnables import RunnableConfig
from langsmith import traceable
from pydantic import BaseModel, Field

from agents.scheduler.graph import SchedulerAgent
from agents.scheduler.state import CommutePlan, SchedulerState
from engine.telemetry.metrics import MetricKey, metrics

logger = structlog.get_logger()

router = APIRouter(prefix="/v1", tags=["Commute Orchestrator"])

# --- API Contracts (DTOs) ---
# Separated from Internal State to allow independent evolution (Rule 17)


class PlanRequest(BaseModel):
    query: str = Field(
        ...,
        min_length=10,
        json_schema_extra={
            "example": "I need to get to JFK for flight BA112 from Brooklyn by 5pm"
        },
    )
    user_id: str = Field(..., json_schema_extra={"example": "user_123"})


class PlanResponse(BaseModel):
    success: bool
    plan: Optional[CommutePlan] = None
    error: Optional[str] = None
    trace_id: str


# --- Dependency Injection ---


def get_agent() -> SchedulerAgent:
    """
    Dependency to provide the initialized agent.
    In a real app, this might pull from a singleton or pool.
    """
    return SchedulerAgent()


# --- Endpoints ---


@router.post(
    "/plan",
    response_model=PlanResponse,
    status_code=status.HTTP_200_OK,
    summary="Generate a commute plan from natural language",
)
@traceable(run_type="chain", name="API_GenerateCommutePlan")
async def generate_commute_plan(
    request: PlanRequest, agent: SchedulerAgent = Depends(get_agent)
) -> PlanResponse:
    """
    Orchestrates the Commute Agent to analyze traffic and flight data.
    """
    log = logger.bind(user_id=request.user_id, route="plan")
    log.info("api.request_received", query=request.query)

    await metrics.increment(MetricKey.REQUESTS_TOTAL)

    # 1. Initialize State
    initial_state = SchedulerState(
        user_id=request.user_id,
        raw_query=request.query,
        user_context=None,
        traffic_data=None,
        flight_data=None,
        plan=None,
        error_log=[],
        retry_count=0,
        execution_trace=[],
    )

    try:
        # 2. Invoke Agent (Async)
        config = RunnableConfig(
            run_name=f"CommutePlan:{request.user_id}",
            tags=["api", "orchestrator"],
            metadata={"user_id": request.user_id, "client_id": "fastapi"},
        )

        agent_start = time.time()
        final_state = await agent.run(initial_state, config=config)
        agent_latency = int((time.time() - agent_start) * 1000)

        # Update agent-specific latency
        await metrics.set(MetricKey.AGENT_LATENCY_MS, agent_latency)

        # 3. Handle Failure (Self-Healing exhausted)
        if not final_state.get("plan"):
            await metrics.increment(MetricKey.REQUESTS_FAILED)
            error_msg = "Agent failed to generate a plan after retries."
            if final_state.get("error_log"):
                error_msg = f"Agent Error: {final_state['error_log'][-1]}"

            log.warning("api.agent_failure", error=error_msg)
            return PlanResponse(
                success=False,
                error=error_msg,
                trace_id=request.user_id,  # Using user_id as trace for MVP
            )

        # 4. Success
        await metrics.increment(MetricKey.REQUESTS_SUCCESS)
        log.info("api.success", action=final_state["plan"].recommended_action)
        return PlanResponse(
            success=True, plan=final_state["plan"], trace_id=request.user_id
        )

    except Exception as e:
        await metrics.increment(MetricKey.REQUESTS_FAILED)
        log.error("api.unhandled_exception", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal system error during planning.",
        )


@router.post(
    "/plan/stream",
    summary="Generate a commute plan with real-time token streaming",
)
async def generate_commute_plan_stream(
    request: PlanRequest, agent: SchedulerAgent = Depends(get_agent)
):
    """
    Streams the agent's reasoning process and final plan via SSE.
    Reduces TTFT by yielding tokens immediately.
    """

    async def event_generator():
        log = logger.bind(user_id=request.user_id, route="plan_stream")
        log.info("api.stream_request_received", query=request.query)

        await metrics.increment(MetricKey.REQUESTS_TOTAL)

        initial_state = SchedulerState(
            user_id=request.user_id,
            raw_query=request.query,
            user_context=None,
            traffic_data=None,
            flight_data=None,
            plan=None,
            error_log=[],
            retry_count=0,
            execution_trace=[],
        )

        config = RunnableConfig(
            run_name=f"CommutePlanStream:{request.user_id}",
            tags=["api", "streaming"],
            metadata={"user_id": request.user_id, "client_id": "fastapi_stream"},
        )

        agent_start = time.time()

        try:
            async for event in agent.astream(initial_state, config=config):
                # Format as SSE event
                yield f"data: {json.dumps(event)}\n\n"

            agent_latency = int((time.time() - agent_start) * 1000)
            await metrics.set(MetricKey.AGENT_LATENCY_MS, agent_latency)
            await metrics.increment(MetricKey.REQUESTS_SUCCESS)

        except Exception as e:
            await metrics.increment(MetricKey.REQUESTS_FAILED)
            log.error("api.stream_exception", error=str(e))
            yield f"data: {json.dumps({'type': 'error', 'content': str(e)})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")
