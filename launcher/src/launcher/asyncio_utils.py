"""Async-offload helpers (constitution Principle III: async-first).

The launcher's blocking I/O (boto3 ``RunMicrovm``, Powertools secret retrieval
and idempotency) runs off the event loop via ``anyio.to_thread.run_sync``. The
FastAPI route stays ``async def``; the loop never blocks.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TypeVar

import anyio

T = TypeVar("T")


async def run_sync(func: Callable[..., T], *args: object, **kwargs: object) -> T:
    """Run a blocking callable in a worker thread, awaitably."""
    return await anyio.to_thread.run_sync(lambda: func(*args, **kwargs))
