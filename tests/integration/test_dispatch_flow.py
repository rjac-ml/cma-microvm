"""Integration: process_webhook end-to-end with the stub MicroVM client."""

from __future__ import annotations

import json

from launcher.config import LauncherConfig
from launcher.launcher import process_webhook
from launcher.shared.stub_client import StubMicroVmClient
from tests.conftest import webhook_body


def test_dispatch_launches_one_microvm(launcher_env):
    config = LauncherConfig()
    stub = StubMicroVmClient()

    result = process_webhook(webhook_body(), {}, config, stub)

    assert result["statusCode"] == 200
    assert len(stub.launches) == 1

    launch = stub.launches[0]
    assert launch["image_identifier"] == "img_123"
    assert launch["execution_role_arn"] == "arn:aws:iam::1:role/microvm-exec"
    assert launch["max_lifetime_seconds"] == 28800

    payload = json.loads(launch["run_hook_payload"])
    session = payload["session"]
    assert session["ANTHROPIC_SESSION_ID"] == "sesn_001"
    assert session["ANTHROPIC_ENVIRONMENT_ID"] == "env_abc"
    assert session["AWS_REGION"] == "us-west-2"
    assert session["ENVIRONMENT_KEY_SECRET_ID"] == ("arn:aws:secrets:us-west-2:1:secret:envkey-abc")


def test_dispatch_non_start_event_does_not_launch(launcher_env):
    config = LauncherConfig()
    stub = StubMicroVmClient()

    result = process_webhook(
        webhook_body(event_type="session.status_run_finished"), {}, config, stub
    )

    assert result["statusCode"] == 200
    assert stub.launches == []
