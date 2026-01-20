import logging
import sys

import structlog
from rich.console import Console
from rich.logging import RichHandler
from structlog.types import Processor

# Global Console for Rich outputs
console = Console()


def setup_logging(json_logs: bool = False, log_level: str = "INFO") -> None:
    """
    Configures the application-wide logging strategy.

    Args:
        json_logs: If True, outputs JSON for ELK/Datadog. If False, uses Rich.
        log_level: 'DEBUG', 'INFO', 'WARNING', 'ERROR'.
    """

    shared_processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.CallsiteParameterAdder(
            {
                structlog.processors.CallsiteParameter.FILENAME,
                structlog.processors.CallsiteParameter.LINENO,
            }
        ),
    ]

    if json_logs:
        # Production: JSON output
        processors = shared_processors + [
            structlog.processors.dict_tracebacks,
            structlog.processors.JSONRenderer(),
        ]
        handler = logging.StreamHandler(sys.stdout)
    else:
        # Development: Rich output
        processors = shared_processors + [
            structlog.dev.ConsoleRenderer(colors=True, pad_event_to=20),
        ]
        # RichHandler handles the formatting
        handler = RichHandler(
            console=console, rich_tracebacks=True, show_path=False, markup=True
        )

    structlog.configure(
        processors=processors,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    # Configure standard library logging to route through structlog/rich
    stdlib_logger = logging.getLogger()
    stdlib_logger.handlers.clear()
    stdlib_logger.addHandler(handler)
    stdlib_logger.setLevel(log_level.upper())

    # Silence noisy libraries
    logging.getLogger("uvicorn.access").disabled = True
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)

    log = structlog.get_logger()
    log.info("logging.initialized", mode="json" if json_logs else "rich")
