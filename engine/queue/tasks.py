import asyncio
import time
from typing import Any, Dict

import structlog
from langsmith import traceable

from agents.scheduler.graph import SchedulerAgent
from agents.scheduler.state import DecisionAction, SchedulerState, UserContext
from engine.queue.config import celery_app

logger = structlog.get_logger()


def run_async_agent(context_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Helper to run the Async Agent inside a Sync Celery Worker.
    """

    async def _execute():
        agent = SchedulerAgent()

        # Hydrate State from Payload
        user_context = UserContext(**context_data)
        user_id = context_data.get("user_id", "unknown_user")

        initial_state = SchedulerState(
            user_id=user_id,
            raw_query="BACKGROUND_POLL",
            user_context=user_context,
            traffic_data=None,
            flight_data=None,
            plan=None,
            error_log=[],
            retry_count=0,
            execution_trace=[],
        )

        from langchain_core.runnables import RunnableConfig

        config = RunnableConfig(
            run_name=f"WorkerPoll:{user_id}",
            tags=["worker", "proactive"],
            metadata={"user_id": user_id, "client_id": "celery_worker"},
        )

        from engine.telemetry.metrics import MetricKey, metrics

        # Invoke Graph
        agent_start = time.time()
        result = await agent.run(initial_state, config=config)
        agent_latency = int((time.time() - agent_start) * 1000)

        # Update agent-specific latency
        await metrics.set(MetricKey.AGENT_LATENCY_MS, agent_latency)

        return result

    return asyncio.run(_execute())


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
@traceable(run_type="chain", name="Worker_MonitorCommute")
def monitor_commute_task(self, user_context_json: Dict[str, Any]):
    """
    Background job:
    1. Check Traffic/Flight status.
    2. Logic: If 'Nudge' is required, trigger notification.
    3. If 'Wait', reschedule self (recursion) or exit.
    """
    log = logger.bind(task_id=self.request.id, user_id=user_context_json.get("user_id"))
    log.info("worker.task_start")

    try:
        # 1. Execute Logic
        result_state = run_async_agent(user_context_json)

        plan = result_state.get("plan")
        if not plan:
            log.warning("worker.agent_failed")
            return {"status": "failed", "reason": "no_plan"}

        # 2. Act on Decision
        action = plan.recommended_action

        if action in [DecisionAction.NUDGE_LEAVE_NOW, DecisionAction.NUDGE_BOOK_UBER]:
            # In a real app, this calls an external Push Notification Service
            log.info("worker.notification_triggered", message=plan.notification_message)
            return {"status": "alert_sent", "message": plan.notification_message}

        elif action == DecisionAction.WAIT:
            log.info("worker.condition_normal", buffer=plan.buffer_minutes_remaining)
            return {"status": "monitoring"}

    except Exception as e:
        log.error("worker.exception", error=str(e))
        # Self-Healing: Retry the background job on transient failures
        raise self.retry(exc=e)
