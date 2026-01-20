from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes import commute, stats
from engine.cache.redis_svc import redis_client
from engine.telemetry.logger import setup_logging

# 1. Setup Telemetry (Global)
setup_logging(json_logs=False, log_level="INFO")

# 2. Initialize App
app = FastAPI(
    title="Atlas Commute Orchestrator",
    version="0.1.0",
    description="Agentic RAG system for proactive commute monitoring.",
)

# 3. Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# 4. Register Routes
app.include_router(commute.router)
app.include_router(stats.router)


@app.on_event("startup")
async def startup_event():
    """Initialize infrastructure connections."""
    await redis_client.connect()


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup connections."""
    await redis_client.close()


@app.get("/health", tags=["System"])
async def health_check():
    return {"status": "ok", "version": "0.1.0"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("api.main:app", host="0.0.0.0", port=8000, reload=True)
