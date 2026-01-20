# Atlas Commute Orchestrator - Deployment Plan

## 🎯 The Problem
Fragmented travel data (traffic spikes, flight delays) leads to missed connections and poor user experience. Current solutions are reactive; Atlas is proactive.

## 🏗 Architecture (Vertical Slice)
- **API (FastAPI)**: Thin entry point.
- **Brain (LangGraph)**: Multi-agent reasoning (Flash for extraction, Pro for deep logic).
- **State (Redis)**: Cross-worker persistence and telemetry.
- **Data (SchedulerState)**: Strict Pydantic-backed contracts.

## 🔄 The Graph Logic
- **Cyclic Control**: Using `retry` edges for LLM self-healing.
- **Parallel Execution**: Tool fetching happens concurrently.
- **Structured Output**: Enforced Pydantic schemas for all agent decisions.

## 🚀 Scaling Path (Future)
1. **Redis Distributed Locking**: Implement in `engine/queue/tasks.py` to prevent duplicate agent execution for the same user.
2. **Persistent Storage**: Migrate from mock JSONs to **Postgres/PostGIS** for realistic geo-spatial travel analysis.
3. **Observability**: Integrate **LangSmith** for deep trace analysis and cost optimization.
4. **Auth**: Add enterprise OAuth2/OIDC layers for multi-tenant isolation.
