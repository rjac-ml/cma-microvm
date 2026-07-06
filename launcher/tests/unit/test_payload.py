"""Unit tests for run-hook payload construction + the credential boundary."""

from __future__ import annotations

import json

from launcher.config import LauncherConfig
from launcher.shared.payload import _FORBIDDEN_KEYS, build_run_hook_payload
from launcher.shared.types import WebhookEvent

_FORBIDDEN_KEYS_VALUES = ("sk-ant-org-...", "sk-ant-env-...")


def _event() -> WebhookEvent:
    return WebhookEvent(
        event_id="evt_1",
        data_type="session.status_run_started",
        session_id="sesn_1",
    )


def test_payload_carries_session_dispatch_fields(launcher_env):
    cfg = LauncherConfig()
    body = build_run_hook_payload(_event(), cfg)
    data = json.loads(body)

    assert data["version"] == "1"
    session = data["session"]
    assert session["ANTHROPIC_SESSION_ID"] == "sesn_1"
    assert session["ANTHROPIC_ENVIRONMENT_ID"] == "env_abc"
    assert session["AWS_REGION"] == "us-west-2"
    assert session["ENVIRONMENT_KEY_SECRET_ID"] == ("arn:aws:secrets:us-west-2:1:secret:envkey-abc")


def test_credential_boundary_no_forbidden_keys(launcher_env):
    """SC/FR-004: API key and environment key never appear in the run hook."""
    cfg = LauncherConfig()
    body = build_run_hook_payload(_event(), cfg)
    flat = json.dumps(json.loads(body))

    for key in _FORBIDDEN_KEYS:
        assert key not in flat, f"forbidden key {key} present in run hook payload"

    # Only a secret *reference* is carried, never the key value itself.
    for value in _FORBIDDEN_KEYS_VALUES:
        assert value not in flat


def test_base_url_optional_and_included_when_set(launcher_env, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_BASE_URL", "https://api.anthropic.example")
    cfg = LauncherConfig()
    body = build_run_hook_payload(_event(), cfg)
    session = json.loads(body)["session"]
    assert session["ANTHROPIC_BASE_URL"] == "https://api.anthropic.example"


def test_base_url_absent_when_unset(launcher_env):
    cfg = LauncherConfig()
    body = build_run_hook_payload(_event(), cfg)
    session = json.loads(body)["session"]
    assert "ANTHROPIC_BASE_URL" not in session
