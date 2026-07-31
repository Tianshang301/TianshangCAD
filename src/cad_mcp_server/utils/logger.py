"""Structured logging configuration built on structlog.

Log records are rendered as JSON by default so that AI agents can parse
them reliably. The default console formatter is used when ``json`` is
``False`` (e.g. interactive CLI use).
"""

import logging
import sys
from typing import Any

import structlog

_CONFIGURED: bool = False


def configure_logging(
    level: str = "INFO",
    *,
    json_output: bool = True,
    log_file: str | None = None,
) -> None:
    """Configure structlog and stdlib logging once."""
    global _CONFIGURED
    numeric_level = getattr(logging, level.upper(), logging.INFO)

    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stderr)]
    if log_file:
        handlers.append(logging.FileHandler(log_file, encoding="utf-8"))

    logging.basicConfig(
        format="%(message)s",
        level=numeric_level,
        handlers=handlers,
    )

    processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.TimeStamper(fmt="iso", utc=True),
    ]
    if json_output:
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer())

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(numeric_level),
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )
    _CONFIGURED = True


def get_logger(name: str = "cad_mcp_server") -> structlog.stdlib.BoundLogger:
    """Return a bound structured logger."""
    if not _CONFIGURED:
        configure_logging()
    return structlog.get_logger(name)  # type: ignore[no-any-return]
