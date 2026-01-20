from dotenv import load_dotenv

# Load environment variables from .env before any other imports that might depend on them
load_dotenv()

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from api.routes import commute, monitor, stats
from engine.cache.redis_svc import redis_client
from engine.telemetry.logger import setup_logging
from engine.telemetry.metrics import MetricKey, metrics

# 1. Setup Telemetry (Global)
setup_logging(json_logs=False, log_level="INFO")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan event handler for FastAPI.
    Manages infrastructure connections (startup/shutdown).
    """
    # Startup: Initialize infrastructure connections
    await redis_client.connect()
    yield
    # Shutdown: Cleanup connections
    await redis_client.close()


# 2. Initialize App
app = FastAPI(
    title="Atlas Commute Orchestrator",
    version="0.1.0",
    description="Agentic RAG system for proactive commute monitoring.",
    lifespan=lifespan,
)

# 3. Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_latency_header(request: Request, call_next):
    """Middleware to measure request latency."""
    import time

    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time

    # Update latency metric in Redis (ms)
    await metrics.set(MetricKey.LATENCY_MS, int(process_time * 1000))

    response.headers["X-Process-Time"] = str(process_time)
    return response


# 4. Register Routes
app.include_router(commute.router)
app.include_router(stats.router)


@app.get("/health", tags=["System"])
async def health_check():
    return {"status": "ok", "version": "0.1.0"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("api.main:app", host="0.0.0.0", port=8000, reload=True)
