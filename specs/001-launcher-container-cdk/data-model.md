# Data Model: Launcher Container Image & CDK IaC

Phase 1 output. The launcher has no relational database (constitution: Alembic/
SQLModels only "if working with databases" — not applicable here). The "data"
is the in-memory request model plus the CDK construct tree. State is held in
backing services (DynamoDB idempotency, Secrets Manager), not in the process.

## In-memory entities (launcher)

### WebhookEvent
Parsed Anthropic webhook delivery. Unchanged from current implementation.
- `event_id: str` — Anthropic event id; the idempotency key.
- `data_type: str` — event subtype; only `session.status_run_started` is acted on.
- `session_id: str` — the session to dispatch (`sesn_...`).
- **Parse rule**: `WebhookEvent.from_payload(payload)` reads `payload.id`,
  `payload.data.type`, `payload.data.id`.
- **Validation**: loose shape sanity (prefix/length) is log-only, never rejects.

### LauncherConfig
Launcher configuration, loaded from the environment via **Pydantic-settings**
(replaces the plain dataclass in `shared/types.py`).
- `environment_id: str`
- `image_identifier: str` — full MicroVM image ARN.
- `environment_key_secret_id: str` — secret ARN (reference only; never read by launcher).
- `execution_role_arn: str`
- `aws_region: str`
- `signing_secret_arn: str | None`
- `base_url: str | None`
- `max_lifetime_seconds: int` (default 28800)
- `launch_tps_limit: int` (default 5)
- **Source**: environment variables (Factor III); same names as today
  (`ANTHROPIC_ENVIRONMENT_ID`, `MICROVM_IMAGE_IDENTIFIER`, etc.).

### RunHookDispatch
The non-secret per-session dispatch blob placed in `runHookPayload`.
- `ANTHROPIC_SESSION_ID`, `ANTHROPIC_ENVIRONMENT_ID`, `AWS_REGION`,
  `ENVIRONMENT_KEY_SECRET_ID` (reference, not the key), optional `ANTHROPIC_BASE_URL`.
- **Invariant**: `_FORBIDDEN_KEYS = (ANTHROPIC_API_KEY, ANTHROPIC_ENVIRONMENT_KEY)`
  MUST never appear. Asserted by a test (FR-004).

### LaunchedMicroVm
Result of a successful `RunMicrovm`.
- `microvm_id: str`, `endpoint: str`.

## Injected collaborator

### MicroVmClient (Protocol)
`launch_microvm(...)` — the seam that enables a **stub** for local parity and
for tests. `Boto3MicroVmClient` is the prod implementation; `StubMicroVmClient`
is the local/test implementation. No behavior change to the Protocol.

## State transitions

### Webhook → dispatch (per event)
```
ARRIVED → SIGNATURE_VERIFIED? ─ no ─→ 401 (deny, no launch)
                │ yes
                ▼
        PARSED → event type? ─ non-start ─→ 200 "ignored"
                │ start
                ▼
        IDEMPOTENCY_CHECK ─ already-in-progress/done ─→ 200 (no re-launch)
                │ new
                ▼
        RATE_LIMIT_ACQUIRE (token bucket, 5 TPS)
                ▼
        RUNMICROVM (stub locally / real in AWS)
                │ ok ─→ 200 { microvm_id }
                │ fail ─→ 502 (Anthropic retries)
```

### Idempotency record (DynamoDB, AWS only)
- Partition key: `id` = webhook event id.
- TTL attribute: `expiration` (= `DEFAULT_MAX_LIFETIME_SECONDS`).
- States: `IN_PROGRESS` → `COMPLETED` (or expired). Concurrent same-id deliveries
  raise `IdempotencyAlreadyInProgressError` → 200 "in progress".

## CDK construct tree (ControlPlaneStack)
- `LauncherFunction` — `DockerImageFunction` from `src/launcher/container/`.
- `WebhookApi` — REST API + `AnthropicWebhookEvent` model + request validator.
- `WebhookWebACL` + `WebhookWebACLLogGroup` + `WebhookWebACLAssociation`.
- `IdempotencyTable` — DynamoDB, `PAY_PER_REQUEST`, TTL on `expiration`.
- `EnvironmentKeySecret`, `SigningSecret` — Secrets Manager.
- `MicroVmExecutionRole`, `BuildRole` — IAM with least-privilege statements.
- `ArtifactBucket` — S3 (versioning, SSE, public-access block).
- Stack outputs: `WebhookUrl`, `LauncherFunctionArn`, `ArtifactBucketName`,
  `BuildRoleArn`, `MicroVmExecutionRoleArn`, `EnvironmentKeySecretArn`,
  `SigningSecretArn` — equivalent to the current SAM outputs.