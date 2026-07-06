"""Loguru logging setup (Factor XI: logs as stdout event streams)."""

from __future__ import annotations

import sys

from loguru import logger

# Single sink to stdout, structured-ish single-line records. Remove the default
# handler so configuration is deterministic across the Lambda runtime and local
# uvicorn processes.
logger.configure(
    handlers=[
        {
            "sink": sys.stdout,
            "level": "INFO",
            "format": (
                "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
                "<level>{level: <8}</level> | "
                "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> "
                "- <level>{message}</level>"
            ),
            "enqueue": False,
        }
    ]
)

__all__ = ["logger"]
