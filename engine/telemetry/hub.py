import asyncio
import json
import os

import redis.asyncio as redis


class LogHub:
    """
    Broadcasts logs via Redis Pub/Sub for the real-time TUI dashboard.
    """

    def __init__(self):
        self.redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        self.client = None
        self.channel = "atlas:logs"
        self.enabled = False

    async def connect(self):
        try:
            self.client = redis.from_url(self.redis_url, socket_connect_timeout=1.0)
            await self.client.ping()
            self.enabled = True
        except:
            self.enabled = False

    async def broadcast(self, log_entry: dict):
        if not self.enabled or not self.client:
            return
        try:
            await self.client.publish(self.channel, json.dumps(log_entry))
        except:
            pass


log_hub = LogHub()
