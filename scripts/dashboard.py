import asyncio
import sys
from datetime import datetime
from time import sleep

import httpx
from rich import box
from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

# Configuration
API_URL = "http://localhost:8000/v1/stats"
REFRESH_RATE = 1  # seconds

console = Console()


def fetch_stats():
    try:
        response = httpx.get(API_URL, timeout=0.5)
        if response.status_code == 200:
            return response.json().get("metrics", {})
        return {"error": f"Status {response.status_code}"}
    except Exception:
        return {"error": "API Offline"}


def make_header() -> Panel:
    grid = Table.grid(expand=True)
    grid.add_column(justify="center", ratio=1)
    grid.add_column(justify="right")

    title = Text("Atlas Orchestrator // Live Control", style="bold white on blue")
    timestamp = Text(datetime.now().strftime("%H:%M:%S"), style="dim white")

    grid.add_row(title, timestamp)
    return Panel(grid, style="white on blue")


def make_metrics_table(stats: dict) -> Panel:
    table = Table(box=box.SIMPLE_HEAD, expand=True)
    table.add_column("Metric", style="cyan")
    table.add_column("Value", justify="right", style="green bold")

    if "error" in stats:
        table.add_row("Status", "[red]OFFLINE[/red]")
    else:
        table.add_row("Requests (Total)", str(stats.get("requests:total", 0)))
        table.add_row("Requests (Success)", str(stats.get("requests:success", 0)))
        table.add_row(
            "Requests (Failed)", f"[red]{stats.get('requests:failed', 0)}[/red]"
        )
        table.add_row("Cache Hits", str(stats.get("cache:hits", 0)))

    return Panel(table, title="System Telemetry", border_style="green")


def make_layout() -> Layout:
    layout = Layout()
    layout.split(Layout(name="header", size=3), Layout(name="body"))
    layout["body"].split_row(
        Layout(name="metrics", ratio=1),
        Layout(name="logs", ratio=2),  # Placeholder for log stream
    )
    return layout


def run_dashboard():
    layout = make_layout()

    with Live(layout, refresh_per_second=4, screen=True) as live:
        while True:
            # 1. Update Header
            layout["header"].update(make_header())

            # 2. Fetch & Update Metrics
            stats = fetch_stats()
            layout["metrics"].update(make_metrics_table(stats))

            # 3. Placeholder Log Panel
            layout["logs"].update(
                Panel(
                    Text("Waiting for log stream... (Not connected)", style="dim"),
                    title="Live Agent Logs",
                    border_style="yellow",
                )
            )

            sleep(REFRESH_RATE)


if __name__ == "__main__":
    try:
        run_dashboard()
    except KeyboardInterrupt:
        console.print("[bold red]Dashboard Terminated[/bold red]")
