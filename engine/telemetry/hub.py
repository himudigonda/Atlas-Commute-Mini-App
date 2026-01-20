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
            # Use a short timeout for initial connect
            self.client = redis.from_url(
                self.redis_url, socket_connect_timeout=2.0, socket_timeout=2.0
            )
            await self.client.ping()
            self.enabled = True
        except Exception:
            self.enabled = False

    async def broadcast(self, log_entry: dict):
        if not self.enabled:
            return

        # Attempt broadcast with one-shot reconnection
        try:
            if not self.client:
                await self.connect()

            await self.client.publish(self.channel, json.dumps(log_entry))
        except (redis.ConnectionError, redis.TimeoutError):
            # Try to reconnect once if connection fails
            try:
                await self.connect()
                if self.enabled and self.client:
                    await self.client.publish(self.channel, json.dumps(log_entry))
            except Exception:
                pass
        except Exception:
            pass


log_hub = LogHub()
