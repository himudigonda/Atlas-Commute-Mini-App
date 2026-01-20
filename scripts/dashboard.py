import asyncio
import json
import os
import sys
from typing import Any, Dict

import httpx
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
REFRESH_RATE = 0.5  # Stable refresh for telemetry


class DashboardManager:
    def __init__(self):
        self.console = Console()
        self.metrics = {}
        self.api_status = "Offline"
        self.layout = self._setup_layout()

    def _setup_layout(self) -> Layout:
        layout = Layout()
        layout.split(Layout(name="header", size=3), Layout(name="body"))
        return layout

    def make_header(self) -> Panel:
        grid = Table.grid(expand=True)
        grid.add_column(justify="center", ratio=1)
        grid.add_column(justify="right")

        title = Text(
            "Atlas Orchestrator // System Telemetry", style="bold white on blue"
        )
        timestamp = Text(format_now(), style="dim white")

        grid.add_row(title, timestamp)
        return Panel(grid, style="white on blue")

    def make_metrics_table(self) -> Panel:
        table = Table(box=box.SIMPLE_HEAD, expand=True)
        table.add_column("System Metric", style="cyan")
        table.add_column("Current Value", justify="right", style="green bold")

        table.add_row(
            "API Gateway",
            f"[bold {'green' if self.api_status == 'Online' else 'red'}]{self.api_status}[/]",
        )

        # Spacer
        table.add_row("", "")

        if self.metrics:
            for k, v in self.metrics.items():
                name = k.replace("_", " ").title()
                table.add_row(name, str(v))
        else:
            table.add_row("[dim]Waiting for data...[/dim]", "")

        return Panel(table, title="Live Performance Metrics", border_style="green")

    async def fetch_api_stats(self):
        """Polls the API for metric snapshots."""
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(API_URL, timeout=1.0)
                if response.status_code == 200:
                    data = response.json()
                    self.metrics = data.get("metrics", {})
                    self.api_status = "Online"
                else:
                    self.api_status = f"Error {response.status_code}"
            except Exception:
                self.api_status = "Offline"

    async def run(self):
        """Main execution loop for the TUI."""
        with Live(self.layout, refresh_per_second=2, screen=True) as live:
            while True:
                # 1. Update Layout Components Directly
                self.layout["header"].update(self.make_header())
                self.layout["body"].update(self.make_metrics_table())

                # 2. Polling (Non-blocking)
                await self.fetch_api_stats()

                await asyncio.sleep(REFRESH_RATE)


if __name__ == "__main__":
    try:
        manager = DashboardManager()
        asyncio.run(manager.run())
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print(f"Fatal Error: {e}")
        sys.exit(1)
