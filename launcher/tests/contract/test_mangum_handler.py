"""Lambda-mode parity: the Mangum handler must behave like the FastAPI app.

SC-003: one OCI image, two entry modes, identical dispatch contract.
"""

from __future__ import annotations

from launcher.app import handler
from tests.conftest import sign_webhook, webhook_body


def _event(body: str, headers: dict[str, str]) -> dict:
    return {
        "resource": "/webhook",
        "path": "/webhook",
        "httpMethod": "POST",
        "headers": headers,
        "multiValueHeaders": {k: [v] for k, v in headers.items()},
        "queryStringParameters": None,
        "multiValueQueryStringParameters": None,
        "pathParameters": None,
        "stageVariables": None,
        "requestContext": {
            "httpMethod": "POST",
            "path": "/webhook",
            "requestId": "r1",
            "stage": "test",
        },
        "body": body,
        "isBase64Encoded": False,
    }


def test_mangum_signed_start_returns_200(launcher_env, patch_signing_secret):
    body = webhook_body()
    response = handler(_event(body, sign_webhook(body)), None)
    assert response["statusCode"] == 200
    assert "stub-microvm-0001" in response["body"]


def test_mangum_bad_signature_returns_401(launcher_env, patch_signing_secret):
    body = webhook_body()
    bad_headers = {
        "webhook-id": "msg_test",
        "webhook-timestamp": "1",
        "webhook-signature": "v1,deadbeef=",
    }
    response = handler(_event(body, bad_headers), None)
    assert response["statusCode"] == 401
