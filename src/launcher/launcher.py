"""Launcher: launch one ephemeral MicroVM per started session.

On a ``session.status_run_started`` webhook event, verifies the Anthropic webhook
signature in-process, then launches one MicroVM via ``RunMicrovm`` with the
session dispatch delivered through ``runHookPayload``.

Security model:
- The launcher passes only a *reference* to the environment-key secret into the
  MicroVM. The environment key is fetched by the VM's own execution role.
- The organization API key never reaches AWS compute.

Behavior:
- Rejects deliveries that fail signature verification (401).
- Ignores non-``session.status_run_started`` events (200).
- Dedupes by webhook event id (DynamoDB-backed idempotency).
- Enforces the RunMicrovm 5 TPS rate limit.
- On RunMicrovm failure, returns non-2xx so Anthropic retries.

The pure ``Launcher`` core is unchanged from the original implementation; only
the entry/adapter layer moved to ``app.py`` (FastAPI + Mangum) and logging moved
to Loguru. ``process_webhook`` is the blocking entry the ASGI route offloads to a
worker thread (constitution Principle III).
"""

from __future__ import annotations

import json
import os
from collections.abc import Callable
from typing import Any

from aws_lambda_powertools.utilities import parameters
from aws_lambda_powertools.utilities.idempotency import (
    DynamoDBPersistenceLayer,
    IdempotencyConfig,
    idempotent_function,
)
from aws_lambda_powertools.utilities.idempotency.exceptions import (
    IdempotencyAlreadyInProgressError,
)

# Module-scope import so the heavy anthropic + pydantic + httpx cost is paid
# once during init, not on every invocation.
try:
    import anthropic
except ImportError:  # pragma: no cover
    anthropic = None  # type: ignore[assignment]

from launcher.config import LauncherConfig
from launcher.logging import logger
from launcher.shared.constants import (
    DEFAULT_IDLE_POLICY,
    DEFAULT_LOGGING_CONFIG,
    SESSION_RUN_STARTED,
    all_ingress_arn,
    internet_egress_arn,
)
from launcher.shared.microvm_client import (
    Boto3MicroVmClient,
    LaunchMicroVmError,
    MicroVmClient,
)
from launcher.shared.payload import build_run_hook_payload
from launcher.shared.rate_limiter import TokenBucket
from launcher.shared.types import WebhookEvent

_SECRET_CACHE_SECONDS = 300
_IDEMPOTENCY_TTL_SECONDS = 28800  # matches DEFAULT_MAX_LIFETIME_SECONDS

_SESSION_ID_PREFIX = "sesn_"
_SESSION_ID_MAX_LEN = 128


def verify_signature(body: str, headers: dict[str, str], signing_secret: str) -> bool:
    """Verify a webhook delivery using the Anthropic SDK.

    Returns True if the signature is valid and the payload is fresh, else False.
    """
    try:
        client = anthropic.Anthropic(api_key="unused-for-webhook-verification")
        client.beta.webhooks.unwrap(body, headers=headers, key=signing_secret)
        return True
    except Exception as exc:  # noqa: BLE001
        logger.warning("webhook signature verification failed: {}", exc)
        return False


class Launcher:
    """Pure launch logic, testable without AWS."""

    def __init__(
        self,
        config: LauncherConfig,
        client: MicroVmClient,
        *,
        rate_limiter: TokenBucket | None = None,
        executor: Callable[[WebhookEvent], dict[str, Any]] | None = None,
    ) -> None:
        self._config = config
        self._client = client
        self._rate_limiter = rate_limiter or TokenBucket(config.launch_tps_limit)
        self._executor = executor or self._launch_and_dispatch

    def set_executor(self, executor: Callable[[WebhookEvent], dict[str, Any]]) -> None:
        """Install the idempotency-wrapped executor."""
        self._executor = executor

    def _launch_and_dispatch(self, event: WebhookEvent) -> dict[str, Any]:
        """Launch one MicroVM with the run hook payload. Raises on failure."""
        run_hook_payload = build_run_hook_payload(event, self._config)
        self._rate_limiter.acquire()
        launched = self._client.launch_microvm(
            image_identifier=self._config.image_identifier,
            run_hook_payload=run_hook_payload,
            max_lifetime_seconds=self._config.max_lifetime_seconds,
            execution_role_arn=self._config.execution_role_arn,
            idle_policy=DEFAULT_IDLE_POLICY,
            logging_config=DEFAULT_LOGGING_CONFIG,
            ingress_network_connectors=[all_ingress_arn(self._config.aws_region)],
            egress_network_connectors=[internet_egress_arn(self._config.aws_region)],
        )

        logger.info(
            "launched microvm_id={} for session_id={}",
            launched.microvm_id,
            event.session_id,
        )
        return {"microvm_id": launched.microvm_id}

    def handle(self, event: WebhookEvent) -> dict[str, Any]:
        """Handle one parsed, verified webhook event. Returns an API-Gateway-style response."""
        if event.data_type != SESSION_RUN_STARTED:
            logger.info("ignoring non-start event type={}", event.data_type)
            return {"statusCode": 200, "body": "ignored"}

        # Validate required fields. Return 200 (not 4xx) for malformed events
        # so Anthropic doesn't retry (a malformed event won't become valid).

        if not event.event_id:
            logger.warning("ignoring event: missing event_id (cannot dedupe)")
            return {"statusCode": 200, "body": "ignored"}

        if not event.session_id:
            logger.warning("ignoring event id={}: missing session_id", event.event_id)
            return {"statusCode": 200, "body": "ignored"}

        # Loose shape sanity — log-only, never rejects.
        if not (
            event.session_id.startswith(_SESSION_ID_PREFIX)
            and len(event.session_id) <= _SESSION_ID_MAX_LEN
        ):
            logger.warning(
                "event id={} has an implausible session_id shape (proceeding): {!r}",
                event.event_id,
                event.session_id,
            )

        try:
            result = self._executor(event)
        except IdempotencyAlreadyInProgressError:
            logger.info("event id={} already in progress; not re-launching", event.event_id)
            return {"statusCode": 200, "body": "in progress"}
        except LaunchMicroVmError as exc:
            logger.error("RunMicrovm failed for session_id={}: {}", event.session_id, exc)
            return {
                "statusCode": 502,
                "body": json.dumps({"error": "run_microvm_failed", "session_id": event.session_id}),
            }

        return {
            "statusCode": 200,
            "body": json.dumps(
                {"microvm_id": result.get("microvm_id"), "session_id": event.session_id}
            ),
        }


# --- Idempotency -----------------------------------------------------------

_idempotent_run: Callable[..., dict[str, Any]] | None = None


def _make_idempotent_run(persistence_layer: Any) -> Callable[..., dict[str, Any]]:
    """Build the idempotent wrapper around the launch side effect."""
    config = IdempotencyConfig(
        event_key_jmespath="event_id",
        expires_after_seconds=_IDEMPOTENCY_TTL_SECONDS,
    )

    @idempotent_function(
        data_keyword_argument="event_record",
        persistence_store=persistence_layer,
        config=config,
    )
    def _run(
        event_record: dict[str, Any], *, launch: Callable[[], dict[str, Any]]
    ) -> dict[str, Any]:
        return launch()

    return _run


def build_idempotency_with(persistence_layer: Any) -> None:
    """Install an idempotent executor backed by ``persistence_layer``.

    Prod passes a ``DynamoDBPersistenceLayer``; tests pass an in-memory layer.
    """
    global _idempotent_run
    _idempotent_run = _make_idempotent_run(persistence_layer)


def reset_idempotency() -> None:
    """Clear the installed idempotent executor (test helper)."""
    global _idempotent_run
    _idempotent_run = None


def _build_idempotency(table_name: str) -> None:
    """Construct the DynamoDB persistence layer and idempotent wrapper once."""
    if _idempotent_run is not None:
        return
    build_idempotency_with(
        DynamoDBPersistenceLayer(table_name=table_name, expiry_attr="expiration")
    )


def _idempotent_executor(launcher: Launcher) -> Callable[[WebhookEvent], dict[str, Any]]:
    """Wrap the launch side effect in DynamoDB idempotency (no Lambda context)."""

    def executor(event: WebhookEvent) -> dict[str, Any]:
        assert _idempotent_run is not None
        return _idempotent_run(
            event_record={"event_id": event.event_id},
            launch=lambda: launcher._launch_and_dispatch(event),
        )

    return executor


# --- Composition -----------------------------------------------------------


def make_client(config: LauncherConfig) -> MicroVmClient:
    """Return the MicroVM client: a stub locally, boto3 in AWS."""
    if os.environ.get("LAUNCHER_USE_STUB") == "1":
        from launcher.shared.stub_client import StubMicroVmClient

        return StubMicroVmClient()
    return Boto3MicroVmClient(region_name=config.aws_region)


def process_webhook(
    raw_body: str,
    headers: dict[str, str],
    config: LauncherConfig,
    client: MicroVmClient,
) -> dict[str, Any]:
    """Full blocking webhook flow. The ASGI route offloads this to a thread.

    Verifies the signature (if a signing secret is configured), builds the
    Launcher with optional DynamoDB idempotency, and returns an API-Gateway-style
    response dict ``{"statusCode": ..., "body": ...}``.
    """
    if config.signing_secret_arn:
        signing_secret = parameters.get_secret(
            config.signing_secret_arn, max_age=_SECRET_CACHE_SECONDS
        )
        if not verify_signature(raw_body, headers, signing_secret):
            logger.info("denying webhook: signature verification failed")
            return {"statusCode": 401, "body": "signature verification failed"}

    launcher = Launcher(config, client)

    table_name = os.environ.get("IDEMPOTENCY_TABLE")
    if table_name:
        _build_idempotency(table_name)
        launcher.set_executor(_idempotent_executor(launcher))

    payload = json.loads(raw_body) if raw_body else {}
    return launcher.handle(WebhookEvent.from_payload(payload))
