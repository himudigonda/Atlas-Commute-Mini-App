import os

from celery import Celery

# 1. Configuration
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# 2. Instance
celery_app = Celery(
    "atlas_worker",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=["engine.queue.tasks"],  # Auto-discover tasks
)

# 3. Tuning (Production Velocity)
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    # Resilience: Acknowledge task only after completion
    task_acks_late=True,
    # Performance: Prefetch multiplier for high-throughput/short-tasks
    worker_prefetch_multiplier=1,
)
