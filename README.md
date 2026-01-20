# Atlas Commute Orchestrator 🌍

> A production-hardened, agentic RAG system that proactively manages commute logistics using Gemini 2.0 and LangGraph.

## 🏗 Architecture
- **API**: FastAPI (Stateless, Lifespan managed).
- **Agent**: LangGraph (Dual-model tiering: 2.0 Flash/Pro).
- **Queue**: Celery + Redis (Background monitor).
- **Telemetry**: Redis atomic counters + Rich Dashboard.

## 🚀 Quick Start
1. **Setup**: `make setup`
2. **Local Dev**: `make dev`
3. **Observability**: `make dashboard` (in separate terminal)

## 🛡️ Hardening & Security
- **Python 3.12**: Optimized for high-concurrency `asyncio`.
- **Non-Root Images**: Secure Docker runtime using `atlas` user.
- **Self-Healing**: Automatic retry logic for LLM hallucinations.
- **Singleton Clients**: Prevent socket exhaustion in high-traffic scenarios.

## 📊 Environment
Requires:
- `GOOGLE_API_KEY`
- `REDIS_URL`

## 📁 Project Structure
- `agents/`: Core reasoning and prompts.
- `tools/`: Singleton API clients.
- `engine/`: Infrastructure (Redis, Metrics, Queue).
- `api/`: FastAPI routers and schemas.
- `scripts/`: Operational tools (Dashboard).
