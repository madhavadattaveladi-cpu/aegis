"""Logging configured with Rich for readable, colourful console output.

Verbosity is configurable. By default AEGIS runs "quiet" (only warnings and
errors show), so the assistant's conversation isn't drowned out by INFO lines
and HTTP request logs. Turn the thinking process back on with the ``verbose``
flag (CLI ``--verbose``) or ``AEGIS_VERBOSE=true`` in your .env.
"""

from __future__ import annotations

import logging

from rich.console import Console
from rich.logging import RichHandler

console = Console()

_configured = False
_current_level: int = logging.WARNING


def setup_logging(level: int | None = None, *, force: bool = False) -> None:
    """Configure root logging once, routing through Rich.

    Args:
        level: explicit log level. If None, falls back to the verbose setting
            (INFO when verbose, WARNING otherwise).
        force: reconfigure even if already configured (used when the CLI sets
            verbosity after the first logger was created).
    """
    global _configured, _current_level

    if level is None:
        # Import here to avoid a circular import at module load time.
        try:
            from aegis.utils.config import get_settings

            verbose = get_settings().verbose
        except Exception:
            verbose = False
        level = logging.INFO if verbose else logging.WARNING

    if _configured and not force and level == _current_level:
        return

    _current_level = level
    root = logging.getLogger()
    # Clear existing handlers so re-configuring (e.g. --verbose) takes effect.
    for handler in list(root.handlers):
        root.removeHandler(handler)
    logging.basicConfig(
        level=level,
        format="%(message)s",
        datefmt="[%X]",
        handlers=[RichHandler(console=console, rich_tracebacks=True, show_path=False)],
    )
    # The httpx library logs every request at INFO; keep it quiet unless we are
    # explicitly in verbose mode.
    httpx_level = logging.INFO if level <= logging.INFO else logging.WARNING
    logging.getLogger("httpx").setLevel(httpx_level)
    logging.getLogger("httpcore").setLevel(logging.WARNING)

    _configured = True


def set_verbose(verbose: bool) -> None:
    """Turn the detailed thinking process (INFO logs + HTTP logs) on or off."""
    setup_logging(logging.INFO if verbose else logging.WARNING, force=True)


def get_logger(name: str) -> logging.Logger:
    """Return a named logger, ensuring logging is configured first."""
    setup_logging()
    return logging.getLogger(name)