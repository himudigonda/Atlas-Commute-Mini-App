import os
import json
from typing import Optional, Type, TypeVar
from pydantic import BaseModel
import redis.asyncio as redis
import structlog

logger = structlog.get_logger()

# Generic type for Pydantic models
T = TypeVar("T", bound=BaseModel)

class RedisService:
    """
    Singleton wrapper for Redis with automatic Pydantic serialization.
    Implements Rule 11 (Caching) and Rule 15 (Resilience).
    """
    _instance: Optional["RedisService"] = None

    def __init__(self) -> None:
        self.client: Optional[redis.Redis] = None
        self.enabled: bool = False
        self._url: str = os.getenv("REDIS_URL", "redis://localhost:6379")

    @classmethod
    def get_instance(cls) -> "RedisService":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    async def connect(self) -> None:
        """Initializes the Redis connection pool."""
        try:
            self.client = redis.from_url(
                self._url, 
                encoding="utf-8", 
                decode_responses=True,
                socket_connect_timeout=2.0  # Fail fast
            )
            if self.client:
                await self.client.ping()
                self.enabled = True
                logger.info("redis.connected", url=self._url)
        except Exception as e:
            self.enabled = False
            logger.error("redis.connection_failed", error=str(e), fallback="disabled")

    async def close(self) -> None:
        if self.client:
            await self.client.close()
            logger.info("redis.closed")

    async def set_model(self, key: str, model: BaseModel, ttl: int = 3600) -> bool:
        """
        Stores a Pydantic model as JSON.
        """
        if not self.enabled or not self.client:
            return False
        try:
            # Pydantic V2 serialization
            data = model.model_dump_json()
            await self.client.set(key, data, ex=ttl)
            return True
        except Exception as e:
            logger.error("redis.set_error", key=key, error=str(e))
            return False

    async def get_model(self, key: str, model_cls: Type[T]) -> Optional[T]:
        """
        Retrieves JSON and validates it against the Pydantic schema.
        Returns None if key missing or validation fails.
        """
        if not self.enabled or not self.client:
            return None
        try:
            data = await self.client.get(key)
            if not data:
                return None
            # Pydantic V2 validation
            return model_cls.model_validate_json(data)
        except Exception as e:
            logger.error("redis.get_error", key=key, error=str(e))
            return None

# Singleton export
redis_client = RedisService.get_instance()
