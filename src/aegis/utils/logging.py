"""Logging configured with Rich for readable, colourful console output."""

from __future__ import annotations

import logging

from rich.console import Console
from rich.logging import RichHandler

console = Console()

_configured = False


def setup_logging(level: int = logging.INFO) -> None:
    """Configure root logging once, routing through Rich."""
    global _configured
    if _configured:
        return
    logging.basicConfig(
        level=level,
        format="%(message)s",
        datefmt="[%X]",
        handlers=[RichHandler(console=console, rich_tracebacks=True, show_path=False)],
    )
    _configured = True


def get_logger(name: str) -> logging.Logger:
    """Return a named logger, ensuring logging is configured first."""
    setup_logging()
    return logging.getLogger(name)
