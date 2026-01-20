import operator
import asyncio
from datetime import datetime
from typing import Annotated, Any, Dict, List, Literal

from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import StateGraph, END

from agents.factory import ModelFactory
from agents.scheduler.state import (
    SchedulerState, 
    UserContext, 
    CommutePlan, 
    TrafficMetrics, 
    FlightMetrics
)
from agents.scheduler.prompts import CLASSIFIER_SYSTEM, REASONER_SYSTEM
from tools.clients.traffic_client import TrafficClient
from tools.clients.flight_client import FlightClient
import structlog

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
            {
                "continue": "fetch_context",
                "retry": "classify",
                "end": END
            }
        )
        
        workflow.add_edge("fetch_context", "reason")
        
        # Conditional Edge: Self-Healing for Reasoner
        workflow.add_conditional_edges(
            "reason",
            self.edge_check_reasoning,
            {
                "done": END,
                "retry": "reason"
            }
        )

        self.runner = workflow.compile()

    # --- NODE 1: Classify (Flash) ---
    async def node_classify(self, state: SchedulerState) -> Dict[str, Any]:
        """Extracts intent from raw query using Gemini Flash."""
        logger.info("agent.node.classify")
        
        try:
            # Prepare Prompt
            prompt = CLASSIFIER_SYSTEM.format(current_time=datetime.now().isoformat())
            messages = [SystemMessage(content=prompt)]
            
            # Inject Error Context if Retrying
            if state.get("error_log"):
                messages.append(HumanMessage(
                    content=f"PREVIOUS ERROR: {state['error_log'][-1]}. Fix the JSON structure."
                ))
            
            messages.append(HumanMessage(content=state["raw_query"]))

            # Call Model with Pydantic Structured Output
            extractor = self.flash_model.with_structured_output(UserContext)
            result = await extractor.ainvoke(messages)
            
            return {
                "user_context": result,
                "retry_count": 0  # Reset on success
            }

        except Exception as e:
            logger.warning("agent.classify.failed", error=str(e))
            return {
                "error_log": [str(e)],
                "retry_count": state.get("retry_count", 0) + 1
            }

    # --- NODE 2: Fetch Context (Parallel Tools) ---
    async def node_fetch_context(self, state: SchedulerState) -> Dict[str, Any]:
        """Executes Traffic and Flight tools in parallel."""
        logger.info("agent.node.fetch")
        ctx = state["user_context"]
        
        # Asyncio Gather for parallelism (Rule IV)
        t_task = self.traffic_tool.get_travel_time(ctx.origin, ctx.destination)
        f_task = self.flight_tool.get_status(ctx.flight_number)
        
        traffic, flight = await asyncio.gather(t_task, f_task)
        
        return {
            "traffic_data": traffic,
            "flight_data": flight
        }

    # --- NODE 3: Reason (Pro) ---
    async def node_reason(self, state: SchedulerState) -> Dict[str, Any]:
        """Decides action using Gemini Pro."""
        logger.info("agent.node.reason")
        
        try:
            # Context Preparation
            traffic = state["traffic_data"]
            flight = state["flight_data"]
            
            prompt = REASONER_SYSTEM.format(
                traffic_status=traffic.status.value,
                traffic_duration=traffic.duration_seconds,
                flight_status=flight.status.value,
                flight_time=flight.estimated_departure.isoformat(),
                current_time=datetime.now().isoformat()
            )
            
            messages = [SystemMessage(content=prompt)]
            
             # Inject Error Context if Retrying
            if state.get("error_log") and state.get("retry_count", 0) > 0:
                messages.append(HumanMessage(
                    content=f"PREVIOUS ERROR: {state['error_log'][-1]}. Ensure strict JSON adherence."
                ))

            # Call Model
            reasoner = self.pro_model.with_structured_output(CommutePlan)
            plan = await reasoner.ainvoke(messages)
            
            return {
                "plan": plan,
                "retry_count": 0
            }

        except Exception as e:
            logger.error("agent.reason.failed", error=str(e))
            return {
                "error_log": [str(e)],
                "retry_count": state.get("retry_count", 0) + 1
            }

    # --- EDGES ---
    
    def edge_check_classification(self, state: SchedulerState) -> Literal["continue", "retry", "end"]:
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
            return "done" # Done but failed
        return "retry"
