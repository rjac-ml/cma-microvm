"""FastAPI + Mangum entrypoint for the launcher.

One image, two entry modes (constitution Factor X: dev/prod parity):
- Locally (uvicorn): ``uvicorn launcher.app:app`` serves the same ASGI app.
- In AWS Lambda (container image): ``handler = Mangum(app)`` adapts API Gateway
  proxy events to that same ASGI app.

The webhook route is ``async def``; the blocking ``process_webhook`` flow is
offloaded to a worker thread (Principle III) so the event loop never blocks.
"""

from __future__ import annotations

import json
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from mangum import Mangum

from launcher.asyncio_utils import run_sync
from launcher.config import LauncherConfig
from launcher.launcher import make_client, process_webhook
from launcher.logging import logger

app = FastAPI(title="claude-microvm-launcher")


def _response_from(result: dict[str, Any]) -> JSONResponse:
    body = result.get("body", "")
    try:
        content = json.loads(body) if body.startswith("{") else {"message": body}
    except (ValueError, TypeError):
        content = {"message": body}
    return JSONResponse(
        status_code=int(result.get("statusCode", 200)),
        content=content,
    )


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/webhook")
async def webhook(request: Request) -> JSONResponse:
    raw = (await request.body()).decode("utf-8") or ""
    headers = {k.lower(): v for k, v in request.headers.items()}
    config = LauncherConfig()
    client = make_client(config)
    logger.info("dispatching webhook ({} bytes)", len(raw))
    result = await run_sync(process_webhook, raw, headers, config, client)
    return _response_from(result)


# Lambda entrypoint (container image). Unused under uvicorn.
handler = Mangum(app)
