import redis.asyncio as redis
import structlog
import os

logger = structlog.get_logger()

class CacheService:
    def __init__(self):
        self.client = None
        self.enabled = False
        self._memory = {}

    async def init(self):
        url = os.getenv("REDIS_URL", "redis://localhost:6379")
        try:
            self.client = redis.from_url(url, decode_responses=True)
            await self.client.ping()
            self.enabled = True
            logger.info("cache.connected", provider="redis")
        except Exception as e:
            logger.warning("cache.offline", error=str(e), fallback="in_memory")

    async def get(self, key: str):
        return await self.client.get(key) if self.enabled else self._memory.get(key)

    async def set(self, key: str, val: str, ttl=3600):
        if self.enabled: await self.client.set(key, val, ex=ttl)
        else: self._memory[key] = val

cache = CacheService()
