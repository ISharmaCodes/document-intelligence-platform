"""Logging setup for the platform.

Design goals (per the case study's "meaningful logging" requirement):
- Every request/processing stage can log with a consistent format.
- Log level is configurable via settings/.env, not hardcoded.
- No secrets or stack traces are ever leaked to API responses; logging is
  the *only* place full exception detail should appear (see
  app/core/exceptions.py for the corresponding handler behaviour).
"""

from __future__ import annotations

import logging
import sys

from app.core.config import Settings

_LOG_FORMAT = (
    "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
)
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def configure_logging(settings: Settings) -> None:
    """Configure the root logger once at application startup.

    Idempotent: safe to call multiple times (e.g. in tests) without
    duplicating log handlers.
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(settings.log_level.upper())

    # Avoid attaching duplicate handlers if called more than once
    # (e.g. under a test runner that re-imports the app).
    if any(isinstance(h, logging.StreamHandler) for h in root_logger.handlers):
        return

    handler = logging.StreamHandler(stream=sys.stdout)
    handler.setFormatter(logging.Formatter(fmt=_LOG_FORMAT, datefmt=_DATE_FORMAT))
    root_logger.addHandler(handler)

    # Quiet down noisy third-party loggers by default; raise individually
    # via LOG_LEVEL if deeper debugging is needed.
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Convenience accessor so modules don't repeat logging.getLogger boilerplate."""
    return logging.getLogger(name)
