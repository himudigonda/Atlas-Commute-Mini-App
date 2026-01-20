import asyncio
import json
import os
import sys
from collections import deque
from datetime import datetime

import httpx
import redis.asyncio as redis
from rich import box
from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from engine.telemetry.time_utils import format_now

# Configuration
API_URL = "http://localhost:8000/v1/stats"
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
REFRESH_RATE = 0.5  # seconds
MAX_LOGS = 20

console = Console()
log_queue = deque(maxlen=MAX_LOGS)


async def fetch_stats():
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(API_URL, timeout=0.5)
            if response.status_code == 200:
                return response.json().get("metrics", {})
            return {"error": f"Status {response.status_code}"}
        except Exception:
            return {"error": "API Offline"}


async def log_subscriber():
    """Background task to listen for logs from Redis."""
    try:
        r = redis.from_url(REDIS_URL, decode_responses=True)
        pubsub = r.pubsub()
        await pubsub.subscribe("atlas:logs")

        async for message in pubsub.listen():
            if message["type"] == "message":
                try:
                    data = json.loads(message["data"])
                    # Format: [timestamp] LEVEL - event
                    ts = data.get("timestamp", "").split("T")[-1][:8]
                    level = data.get("level", "info").upper()
                    event = data.get("event", "")

                    color = "cyan"
                    if level == "ERROR":
                        color = "red"
                    elif level == "WARNING":
                        color = "yellow"

                    # SPECIAL RENDERING: Thinking/Saying Boxes
                    if event in ["agent.thinking", "agent.saying"]:
                        node = data.get("node", "unknown").upper()
                        is_thinking = event == "agent.thinking"
                        icon = "🧠" if is_thinking else "💬"
                        title = f"{icon} Agent {node} | {'Thinking' if is_thinking else 'Saying'}"
                        border = "blue" if is_thinking else "magenta"

                        # Extract content
                        content = ""
                        if is_thinking:
                            content = data.get("anchor", "")
                        else:
                            content = json.dumps(data.get("result", {}), indent=2)

                        # Create boxed log
                        panel = Panel(
                            Text(content, style="white"),
                            title=title,
                            border_style=border,
                            box=box.ROUNDED,
                            expand=False,
                        )
                        log_queue.append(panel)
                    else:
                        # STANDARD LOG LINE
                        log_text = Text()
                        log_text.append(f"[{ts}] ", style="dim")
                        log_text.append(f"{level:7}", style=f"bold {color}")
                        log_text.append(f" {event}")
                        log_queue.append(log_text)
                except Exception:
                    pass
    except Exception as e:
        log_queue.append(Text(f"Log Subscriber Error: {str(e)}", style="red"))


def make_header() -> Panel:
    grid = Table.grid(expand=True)
    grid.add_column(justify="center", ratio=1)
    grid.add_column(justify="right")

    title = Text("Atlas Orchestrator // Live Control", style="bold white on blue")
    timestamp = Text(format_now(), style="dim white")

    grid.add_row(title, timestamp)
    return Panel(grid, style="white on blue")


def make_metrics_table(stats: dict) -> Panel:
    table = Table(box=box.SIMPLE_HEAD, expand=True)
    table.add_column("Metric", style="cyan")
    table.add_column("Value", justify="right", style="green bold")

    if "error" in stats:
        table.add_row("Status", "[red]OFFLINE[/red]")
    else:
        for k, v in stats.items():
            name = k.replace("_", " ").title()
            table.add_row(name, str(v))

    return Panel(table, title="System Telemetry", border_style="green")


def make_log_panel() -> Panel:
    # If the queue has Panels, they will be rendered as strings or we handle carefully
    # actually rich handles it if we append correctly, but the queue has mixture of Text and Panel
    # Let's iterate and build a Group if needed, but Panel expects a Renderable
    from rich.console import Group

    return Panel(
        Group(*list(log_queue)), title="Live Agent Logs", border_style="yellow"
    )


def make_layout() -> Layout:
    layout = Layout()
    layout.split(Layout(name="header", size=3), Layout(name="body"))
    layout["body"].split_row(
        Layout(name="metrics", ratio=1), Layout(name="logs", ratio=2)
    )
    return layout


async def main():
    layout = make_layout()

    # Start log subscriber in background
    asyncio.create_task(log_subscriber())

    with Live(layout, refresh_per_second=4, screen=True) as live:
        while True:
            # 1. Update Header
            layout["header"].update(make_header())

            # 2. Fetch & Update Metrics
            stats = await fetch_stats()
            layout["metrics"].update(make_metrics_table(stats))

            # 3. Update Logs
            layout["logs"].update(make_log_panel())

            await asyncio.sleep(REFRESH_RATE)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        console.print("[bold red]Dashboard Terminated[/bold red]")
