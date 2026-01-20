# Atlas Commute Orchestrator 🌍

> A high-velocity, agentic RAG system that proactively manages commute logistics using Gemini 3 Flash/Pro and LangGraph.

## 🏗 Architecture (Vertical Slice)

Atlas uses a **"Thin Router, Fat Logic"** pattern:
1.  **API Layer (FastAPI):** Stateless entry point.
2.  **Agent Core (LangGraph):** Dual-model reasoning engine.
    *   *Flash:* Fast intent extraction & tool routing.
    *   *Pro:* Complex decision making (Time buffers, Risk analysis).
3.  **State Layer (Redis):** Persists agent memory and system telemetry.
4.  **Tools:** Mock-first integrations for Traffic and Flight data.

## 🚀 Quick Start

### Prerequisites
*   Python 3.11+
*   `uv` (Package Manager)
*   Redis (Local or Docker)
*   Google Gemini API Key

### 1. Setup
```bash
# Install dependencies
make setup

# Create .env file
echo "GOOGLE_API_KEY=your_key_here" > .env
```

### 2. Run Local
```bash
# Start the API
make dev

# In a separate terminal, launch the dashboard
make dashboard
```

### 3. Test
```bash
# Run the full suite
make test
```

## 🛡️ Production & Security
*   **Non-Root Runtime:** Dockerfile creates an `atlas` user.
*   **Type Safety:** 100% Pydantic V2 coverage.
*   **Self-Healing:** Agents retry automatically upon JSON parsing errors.

## 📊 Observability
*   **Metrics:** Stored in Redis, accessible via `/v1/stats`.
*   **Logs:** Structured JSON in prod, `Rich` pretty-print in dev.

## 📁 Project Structure
*   `agents/`: LangGraph definitions & Prompts.
*   `api/`: FastAPI routes & DTOs.
*   `engine/`: Redis, Logging, Metrics.
*   `tools/`: Mock clients for testing.
