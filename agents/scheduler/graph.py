import asyncio
import operator
from datetime import datetime
from typing import Annotated, Any, Dict, List, Literal

import structlog
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, StateGraph
from langsmith import traceable

from agents.factory import ModelFactory
from agents.scheduler.prompts import CLASSIFIER_SYSTEM, REASONER_SYSTEM
from agents.scheduler.state import (
    CommutePlan,
    FlightMetrics,
    SchedulerState,
    TrafficMetrics,
    UserContext,
)
from engine.telemetry.logger import console
from engine.telemetry.time_utils import format_now, get_now, to_local
from tools.clients.flight_client import FlightClient
from tools.clients.traffic_client import TrafficClient

logger = structlog.get_logger()


class SchedulerAgent:
    def __init__(self):
        self.traffic_tool = TrafficClient()
        self.flight_tool = FlightClient()

        # Initialize Models
        self.flash_model = ModelFactory.get_fast()
        self.pro_model = ModelFactory.get_pro()

        # Build Graph
        workflow = StateGraph(SchedulerState)

        # Nodes
        workflow.add_node("classify", self.node_classify)
        workflow.add_node("fetch_context", self.node_fetch_context)
        workflow.add_node("reason", self.node_reason)

        # Edges
        workflow.set_entry_point("classify")

        # Conditional Edge: Self-Healing for Classifier
        workflow.add_conditional_edges(
            "classify",
            self.edge_check_classification,
            {"continue": "fetch_context", "retry": "classify", "end": END},
        )

        workflow.add_edge("fetch_context", "reason")

        # Conditional Edge: Self-Healing for Reasoner
        workflow.add_conditional_edges(
            "reason", self.edge_check_reasoning, {"done": END, "retry": "reason"}
        )

        self.runner = workflow.compile()

    @traceable(run_type="chain", name="SchedulerAgent.run")
    async def run(
        self, state: SchedulerState, config: RunnableConfig
    ) -> Dict[str, Any]:
        """Top-level agent execution with full tracing context."""
        # Ensure user_id is in metadata for LangSmith
        user_id = state.get("user_id", "unknown")
        if not config.get("metadata"):
            config["metadata"] = {}
        config["metadata"]["user_id"] = user_id

        return await self.runner.ainvoke(state, config=config)

    async def astream(self, state: SchedulerState, config: RunnableConfig):
        """Streams agent events for real-time UI updates (SSE)."""
        user_id = state.get("user_id", "unknown")
        if not config.get("metadata"):
            config["metadata"] = {}
        config["metadata"]["user_id"] = user_id

        # Use astream_events v2 for granular control
        async for event in self.runner.astream_events(
            state, config=config, version="v2"
        ):
            kind = event["event"]
            name = event["name"]

            # 1. Node Start Events
            if kind == "on_chain_start" and name in [
                "classify",
                "fetch_context",
                "reason",
            ]:
                yield {"type": "node_start", "node": name}

            # 2. Token Streaming (from the reasoning node)
            if kind == "on_chat_model_stream" and name == "ChatGoogleGenerativeAI":
                content = event["data"]["chunk"].content
                if content:
                    yield {"type": "token", "content": content}

            # 3. Final State Chunks
            if kind == "on_chain_end" and name == "LangGraph":
                yield {"type": "final_state", "output": event["data"]["output"]}

    def _extract_content(self, msg) -> str:
        """Robustly extracts string content from a message, handling lists/parts."""
        content = getattr(msg, "content", "")
        if not content:
            return ""
        if isinstance(content, list):
            # Flatten list of dicts/strings (common in some Gemini response formats)
            parts = []
            for part in content:
                if isinstance(part, str):
                    parts.append(part)
                elif isinstance(part, dict) and "text" in part:
                    parts.append(part["text"])
            return "".join(parts).strip()
        return str(content).strip()

    # --- NODE 1: Classify (Flash) ---
    @traceable(run_type="chain", name="NodeClassify")
    async def node_classify(
        self, state: SchedulerState, config: RunnableConfig
    ) -> Dict[str, Any]:
        """Extracts intent from raw query using Gemini Flash."""
        logger.info("agent.node.classify")
        from engine.telemetry.metrics import MetricKey, metrics

        try:
            now_str = format_now()
            temporal_anchor = f"[TEMPORAL ANCHOR: {now_str}]"

            messages = [
                SystemMessage(content=CLASSIFIER_SYSTEM.format(current_time=now_str)),
                HumanMessage(
                    content=f"{temporal_anchor}\nUser Query: {state['raw_query']}\n\nRESPONSE FORMAT: Strictly output valid raw JSON."
                ),
            ]

            if state.get("error_log"):
                messages.append(
                    HumanMessage(
                        content=f"PREVIOUS ERROR: {state['error_log'][-1]}. Fix the JSON structure."
                    )
                )

            logger.debug("agent.thinking", node="classify", anchor=temporal_anchor)

            # We use a plain .ainvoke and manual parse for hyper-stability.
            raw_msg = await self.flash_model.ainvoke(messages, config=config)
            content = self._extract_content(raw_msg)

            # Manual JSON Extraction Logic (Regex for robustness)
            import re

            json_match = re.search(r"\{.*\}", content, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
            else:
                json_str = content

            import json

            result = UserContext.model_validate(json.loads(json_str))

            # DEFENSIVE: Ensure user_id is preserved from state if LLM omits it
            if not result.user_id:
                result.user_id = state.get("user_id")

            logger.info(
                "agent.saying",
                node="classify",
                result=result.model_dump(),
                user_id=state.get("user_id"),
            )

            # Token Tracking (Hardened for Gemini/LangChain V2)
            token_count = 0
            if hasattr(raw_msg, "usage_metadata") and raw_msg.usage_metadata:
                token_count = raw_msg.usage_metadata.get("total_tokens", 0)
            elif hasattr(raw_msg, "response_metadata"):
                token_count = raw_msg.response_metadata.get("usage", {}).get(
                    "total_tokens", 0
                )

            if token_count > 0:
                await metrics.increment(MetricKey.TOKENS_USED, token_count)

            return {"user_context": result, "retry_count": 0}

        except Exception as e:
            logger.warning("agent.classify.failed", error=str(e))
            return {
                "error_log": [str(e)],
                "retry_count": state.get("retry_count", 0) + 1,
            }

    # --- NODE 2: Fetch Context (Parallel Tools) ---
    @traceable(run_type="chain", name="NodeFetchContext")
    async def node_fetch_context(
        self, state: SchedulerState, config: RunnableConfig
    ) -> Dict[str, Any]:
        """Executes Traffic and Flight tools in parallel."""
        logger.info("agent.node.fetch")
        ctx = state["user_context"]

        # Safety: Ensure origin/destination are strings
        origin = ctx.origin or "Current Location"
        destination = ctx.destination or "Airport"
        flight_num = ctx.flight_number or "UA1"

        try:
            # Asyncio Gather with timeout to prevent LangSmith 'Pending' hangs
            t_task = self.traffic_tool.get_travel_time(origin, destination)
            f_task = self.flight_tool.get_status(
                flight_num, target_date=ctx.target_arrival_time
            )

            traffic, flight = await asyncio.wait_for(
                asyncio.gather(t_task, f_task), timeout=10.0
            )

            return {"traffic_data": traffic, "flight_data": flight}
        except Exception as e:
            logger.error("agent.fetch.failed", error=str(e))
            # Graceful degradation logic is also handled in the clients' fail-safe returns
            # but we catch here to ensure the graph never crashes.
            return {"error_log": [f"Tool Failure: {str(e)}"]}

    # --- NODE 3: Reason (Pro) ---
    @traceable(run_type="chain", name="NodeReason")
    async def node_reason(
        self, state: SchedulerState, config: RunnableConfig
    ) -> Dict[str, Any]:
        """Decides action using Gemini Pro."""
        logger.info("agent.node.reason")
        from engine.telemetry.metrics import MetricKey, metrics

        try:
            # Context Preparation
            traffic = state.get("traffic_data") or TrafficMetrics(
                distance_meters=0,
                duration_seconds=0,
                status="clear",
                route_summary="Fallback",
            )
            flight = state.get("flight_data") or FlightMetrics(
                flight_number="N/A",
                status="on_time",
                scheduled_departure=get_now(),
                estimated_departure=get_now(),
            )

            now_str = format_now()
            prompt = REASONER_SYSTEM.format(
                traffic_status=(
                    traffic.status.value
                    if hasattr(traffic.status, "value")
                    else traffic.status
                ),
                traffic_duration=traffic.duration_seconds,
                flight_status=(
                    flight.status.value
                    if hasattr(flight.status, "value")
                    else flight.status
                ),
                flight_time=to_local(flight.estimated_departure).isoformat(),
                current_time=now_str,
            )

            temporal_anchor = (
                f"[TEMPORAL ANCHOR: The absolute current time is {now_str}]"
            )

            messages = [
                SystemMessage(content=prompt),
                HumanMessage(
                    content=f"{temporal_anchor}\nFinal logistics analysis. Provide commute plan in raw JSON format."
                ),
            ]

            if state.get("error_log") and state.get("retry_count", 0) > 0:
                messages.append(
                    HumanMessage(
                        content=f"PREVIOUS ERROR: {state['error_log'][-1]}. Ensure strict JSON adherence."
                    )
                )

            logger.info(
                "agent.thinking",
                node="reason",
                anchor=temporal_anchor,
                user_id=state.get("user_id"),
            )

            # Manual JSON Strategy
            raw_msg = await self.pro_model.ainvoke(messages, config=config)
            content = self._extract_content(raw_msg)

            import re

            json_match = re.search(r"\{.*\}", content, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
            else:
                json_str = content

            import json

            plan = CommutePlan.model_validate(json.loads(json_str))

            logger.info(
                "agent.saying",
                node="reason",
                result=plan.model_dump(),
                user_id=state.get("user_id"),
            )

            # Token Tracking (Hardened for Gemini/LangChain V2)
            token_count = 0
            if hasattr(raw_msg, "usage_metadata") and raw_msg.usage_metadata:
                token_count = raw_msg.usage_metadata.get("total_tokens", 0)
            elif hasattr(raw_msg, "response_metadata"):
                token_count = raw_msg.response_metadata.get("usage", {}).get(
                    "total_tokens", 0
                )

            if token_count > 0:
                await metrics.increment(MetricKey.TOKENS_USED, token_count)

            return {"plan": plan, "retry_count": 0}

        except Exception as e:
            logger.error("agent.reason.failed", error=str(e))
            return {
                "error_log": [str(e)],
                "retry_count": state.get("retry_count", 0) + 1,
            }

    # --- EDGES ---

    def edge_check_classification(
        self, state: SchedulerState
    ) -> Literal["continue", "retry", "end"]:
        if state.get("user_context"):
            return "continue"
        if state.get("retry_count", 0) > 3:
            logger.error("agent.classify.give_up")
            return "end"
        return "retry"

    def edge_check_reasoning(self, state: SchedulerState) -> Literal["done", "retry"]:
        if state.get("plan"):
            return "done"
        if state.get("retry_count", 0) > 3:
            logger.error("agent.reason.give_up")
            return "done"  # Done but failed
        return "retry"
