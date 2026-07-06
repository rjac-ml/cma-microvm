"""Shared pytest fixtures and helpers for the launcher test suite."""

from __future__ import annotations

import datetime
import json

import pytest
from fastapi.testclient import TestClient
from standardwebhooks import Webhook

from launcher.app import app

SIGNING_SECRET = "whsec_test_signing_secret_123"


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture
def launcher_env(monkeypatch):
    """Populate the environment with a valid launcher configuration (stub client)."""
    monkeypatch.setenv("ANTHROPIC_ENVIRONMENT_ID", "env_abc")
    monkeypatch.setenv("MICROVM_IMAGE_IDENTIFIER", "img_123")
    monkeypatch.setenv(
        "ENVIRONMENT_KEY_SECRET_ARN", "arn:aws:secrets:us-west-2:1:secret:envkey-abc"
    )
    monkeypatch.setenv("MICROVM_EXECUTION_ROLE_ARN", "arn:aws:iam::1:role/microvm-exec")
    monkeypatch.setenv("AWS_REGION", "us-west-2")
    monkeypatch.setenv("LAUNCHER_USE_STUB", "1")
    monkeypatch.delenv("IDEMPOTENCY_TABLE", raising=False)
    monkeypatch.delenv("SIGNING_SECRET_ARN", raising=False)
    # Scrub any Anthropic vars leaking from the real shell so tests are hermetic
    # and never accidentally assert against live credential values.
    for _leak in ("ANTHROPIC_BASE_URL", "ANTHROPIC_API_KEY", "ANTHROPIC_ENVIRONMENT_KEY"):
        monkeypatch.delenv(_leak, raising=False)
    yield


@pytest.fixture
def patch_signing_secret(monkeypatch):
    """Enable signature verification using the test signing secret."""
    monkeypatch.setenv("SIGNING_SECRET_ARN", "arn:aws:secrets:us-west-2:1:secret:webhook-signing")
    import launcher.launcher as launcher_mod

    monkeypatch.setattr(
        launcher_mod.parameters, "get_secret", lambda *args, **kwargs: SIGNING_SECRET
    )


def sign_webhook(body: str, secret: str = SIGNING_SECRET) -> dict[str, str]:
    """Produce standardwebhooks headers Anthropic's ``unwrap`` will accept."""
    wh = Webhook(secret)
    ts = datetime.datetime.now(tz=datetime.UTC)
    sig = wh.sign("msg_test", ts, body)
    return {
        "webhook-id": "msg_test",
        "webhook-timestamp": str(int(ts.timestamp())),
        "webhook-signature": sig,
    }


def webhook_body(
    *,
    event_id: str = "evt_001",
    event_type: str = "session.status_run_started",
    session_id: str = "sesn_001",
) -> str:
    return json.dumps(
        {
            "id": event_id,
            "type": event_type,
            "data": {"type": "session", "id": session_id},
        }
    )
