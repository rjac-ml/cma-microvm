"""Webhook contract tests (POST /webhook) over the FastAPI app."""

from __future__ import annotations

from tests.conftest import sign_webhook, webhook_body


def test_healthz(client):
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_signed_start_returns_200_with_microvm_id(client, launcher_env, patch_signing_secret):
    body = webhook_body()
    response = client.post("/webhook", content=body, headers=sign_webhook(body))
    assert response.status_code == 200
    assert response.json()["microvm_id"] == "stub-microvm-0001"


def test_unsigned_rejected_with_401(client, launcher_env, patch_signing_secret):
    body = webhook_body()
    response = client.post("/webhook", content=body, headers={})
    assert response.status_code == 401


def test_tampered_signature_rejected_with_401(client, launcher_env, patch_signing_secret):
    body = webhook_body()
    headers = sign_webhook(body)
    headers["webhook-signature"] = "v1,deadbeef="
    response = client.post("/webhook", content=body, headers=headers)
    assert response.status_code == 401


def test_non_start_event_ignored(client, launcher_env, patch_signing_secret):
    body = webhook_body(event_type="session.status_run_finished")
    response = client.post("/webhook", content=body, headers=sign_webhook(body))
    assert response.status_code == 200
    assert response.json()["message"] == "ignored"


def test_missing_event_id_ignored(client, launcher_env, patch_signing_secret):
    body = webhook_body(event_id="")
    response = client.post("/webhook", content=body, headers=sign_webhook(body))
    assert response.status_code == 200
    assert response.json()["message"] == "ignored"


def test_missing_session_id_ignored(client, launcher_env, patch_signing_secret):
    body = webhook_body(session_id="")
    response = client.post("/webhook", content=body, headers=sign_webhook(body))
    assert response.status_code == 200
    assert response.json()["message"] == "ignored"


def test_run_microvm_failure_returns_502(client, launcher_env, monkeypatch):
    import launcher.app as app_mod
    from launcher.shared.microvm_client import LaunchMicroVmError

    class FailingClient:
        def launch_microvm(self, **_kwargs):
            raise LaunchMicroVmError("simulated RunMicrovm failure")

    monkeypatch.setattr(app_mod, "make_client", lambda _config: FailingClient())

    body = webhook_body()
    response = client.post("/webhook", content=body, headers={})
    assert response.status_code == 502
    assert response.json()["error"] == "run_microvm_failed"
