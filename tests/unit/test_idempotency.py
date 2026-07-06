"""Unit tests for DynamoDB-backed idempotency (dedupe by webhook event id)."""

from __future__ import annotations

import json

import pytest

from launcher.config import LauncherConfig
from launcher.launcher import (
    Launcher,
    _idempotent_executor,
    build_idempotency_with,
    reset_idempotency,
)
from launcher.shared.stub_client import StubMicroVmClient
from launcher.shared.types import WebhookEvent
from tests._in_memory_idempotency import InMemoryPersistenceLayer


@pytest.fixture(autouse=True)
def _reset_idempotency_after_each():
    yield
    reset_idempotency()


def _event(event_id: str = "evt_1") -> WebhookEvent:
    return WebhookEvent(
        event_id=event_id,
        data_type="session.status_run_started",
        session_id="sesn_1",
    )


def _launcher_with_idempotency(cfg: LauncherConfig, stub: StubMicroVmClient) -> Launcher:
    build_idempotency_with(InMemoryPersistenceLayer())
    launcher = Launcher(cfg, stub)
    launcher.set_executor(_idempotent_executor(launcher))
    return launcher


def test_duplicate_event_launches_once_and_replays_result(launcher_env):
    cfg = LauncherConfig()
    stub = StubMicroVmClient()
    launcher = _launcher_with_idempotency(cfg, stub)

    first = launcher.handle(_event())
    second = launcher.handle(_event())

    assert first["statusCode"] == 200
    assert second["statusCode"] == 200
    # The MicroVM was launched exactly once; the second call replayed the cache.
    assert len(stub.launches) == 1
    first_id = json.loads(first["body"])["microvm_id"]
    second_id = json.loads(second["body"])["microvm_id"]
    assert first_id == second_id == "stub-microvm-0001"


def test_distinct_events_each_launch(launcher_env):
    cfg = LauncherConfig()
    stub = StubMicroVmClient()
    launcher = _launcher_with_idempotency(cfg, stub)

    launcher.handle(_event("evt_a"))
    launcher.handle(_event("evt_b"))

    assert len(stub.launches) == 2
