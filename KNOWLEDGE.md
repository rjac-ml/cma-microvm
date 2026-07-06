# Institutional Knowledge

Issues encountered and resolutions for CMA-MicroVM. Per constitution Development Workflow (Learning annotations).

<!-- Entries below: newest date sections first -->

## 2026-07-06

### Lambda Python base: interpreter at /var/lang/bin/python3.12; entrypoint takes one arg

**Context**: spec `001-launcher-container-cdk`, packaging the launcher as a
Lambda container image + local Docker Compose parity.

**Issue**: Two bugs hid behind the same wrong guess. (a) The interpreter in
`public.ecr.aws/lambda/python:3.12` lives at `/var/lang/bin/python3.12` — NOT
`/var/lang/python3.12/bin/python3.12` (which doesn't exist); `UV_PYTHON` pointed
at the missing path, so `uv sync` failed with "No interpreter found at path".
(b) The base image's `/lambda-entrypoint.sh` does `if [ $# -ne 1 ]; then exit
142`, expecting the handler name as its single argument — so a compose
`command:` of `["/var/lang/python3.12/bin/python3", "-m", "uvicorn", ...]` would
`exit 142` even with the correct path. The base image also does NOT export
`PYTHONPATH`.

**Resolution**: Pin `UV_PYTHON=/var/lang/bin/python3.12` in the Dockerfile. In
`docker-compose.yml`, override `entrypoint:` to `["/var/lang/bin/python3"]` and
pass uvicorn / the init script via `command:`; set `PYTHONPATH=/var/task`
explicitly (the Dockerfile lays deps + the `launcher` package flat in
`${LAMBDA_TASK_ROOT}`).

**Prevention**: Don't guess interpreter paths in AWS Lambda base images —
`docker run --entrypoint /bin/sh <image> -c 'which python3.12'` to confirm. And
remember the Lambda base entrypoint is handler-only; to run anything else
(uvicorn, a one-shot script) override `entrypoint:`, not just `command:`.

**Refs**: `container/Dockerfile`, `docker-compose.yml`, `container/dynamodb_init.py`.

---

### standardwebhooks ↔ anthropic webhooks unwrap is a clean round-trip for tests

**Context**: spec `001-launcher-container-cdk`, implementing the webhook
contract tests (T013–T014b).

**Issue**: How to produce a *valid* signed Anthropic webhook body in tests to
exercise the 200 path (the launcher only verifies, it never signs).

**Resolution**: `anthropic[webhooks]` pulls in `standardwebhooks`. Sign with
`Webhook(secret).sign(msg_id, ts, body)` and send headers `webhook-id`,
`webhook-timestamp` (`str(int(ts.timestamp()))`), `webhook-signature`; the
launcher's `client.beta.webhooks.unwrap(body, headers=..., key=secret)` accepts
them verbatim. Tamper any header → 401.

**Prevention**: For Anthropic webhook tests, sign with `standardwebhooks`, not a
hand-rolled HMAC — the header scheme (id/timestamp/signature) must match exactly.

**Refs**: `tests/conftest.py` (`sign_webhook`), `src/launcher/launcher.py`
(`verify_signature`).

---

### WebhookEvent must read the top-level `type`, not `data.type`

**Context**: spec `001-launcher-container-cdk`, implementing the launcher.

**Issue**: `WebhookEvent.from_payload` originally read `data.type`, which is
`"session"` (the resource kind), not `"session.status_run_started"`. Every event
was therefore treated as non-start and ignored (200, no launch) — silently.

**Resolution**: `from_payload` now reads `payload["type"]` (the top-level event
type) into `data_type`; `session_id` stays `data["id"]`. TDD caught this: the
signed-start test expected a `microvm_id` and got a 200 "ignored" instead.

**Prevention**: The Anthropic webhook envelope is `{id, type, data:{type,id}}`.
`type` is the lifecycle event; `data.type` is the resource kind. Don't confuse
them — and assert on launch outcomes, not just status codes, in webhook tests.

**Refs**: `src/launcher/shared/types.py`, `tests/contract/test_webhook.py`.

---

### Powertools has no in-memory idempotency layer — subclass BasePersistenceLayer

**Context**: spec `001-launcher-container-cdk`, the dedupe unit test (T015).

**Issue**: Powertools Idempotency ships only `DynamoDBPersistenceLayer`; the
unit test needed to exercise dedupe without DynamoDB Local.

**Resolution**: A ~20-line `InMemoryPersistenceLayer(BasePersistenceLayer)`
(`tests/_in_memory_idempotency.py`) implements `_get_record` (raise
`IdempotencyItemNotFoundError`), `_put_record` (raise
`IdempotencyItemAlreadyExistsError(old_data_record=...)` on a non-expired
existing key), `_update_record`, `_delete_record`. The COMPLETED path replays the
cached response; launcher refactored to `build_idempotency_with(layer)` +
`reset_idempotency()` so tests inject a fresh layer per case.

**Prevention**: For Powertools idempotency tests, subclass `BasePersistenceLayer`
rather than standing up DynamoDB Local — and reset the module-global executor
between tests.

**Refs**: `tests/_in_memory_idempotency.py`, `src/launcher/launcher.py`
(`build_idempotency_with`, `reset_idempotency`).

---

### CDK (jsii) needs Node; DockerImageCode API + App outdir gotchas

**Context**: spec `001-launcher-container-cdk`, US2 (CDK control plane).

**Issue**: (a) `aws-cdk-lib` is jsii-backed and needs `node` on PATH — this
machine manages node via asdf with none active. (b) The container-image code
construct API is `DockerImageCode.from_image_asset(directory=..., file=..., cmd=...)`
and `from_ecr(repo, tag_or_digest=..., cmd=...)` — **not** `from_image` /
`from_ecr_image`. (c) `cdk.App()` with no `outdir` writes to a **temp staging
dir** when run without the `cdk` CLI, so `just cdk-synth` produced nothing.

**Resolution**: Pin `utils/cdk/.tool-versions` (`nodejs 22.1.0`) and prepend its
bin to PATH for `cdk-test`/synth. Use the correct `DockerImageCode` classmethods.
Pin `app = cdk.App(outdir="cdk.out")` so synthesis writes into the repo, and gate
the real Docker build behind `CDK_BUILD_IMAGE=1` (default) so synth/tests run
without Docker (`build_image=False` swaps in a dummy ECR ref).

**Prevention**: When using CDK Python, always ensure `node` is resolvable; don't
guess `DockerImageCode` method names (they changed across versions — inspect
`dir(...)`); and always set `outdir` explicitly if you synth without the CLI.

**Refs**: `utils/cdk/app.py`, `utils/cdk/control_plane/lambda_construct.py`,
`utils/cdk/.tool-versions`, `Justfile`.

---

### Lambda container base pinned to Python 3.12 (not 3.14) for wheel ABI safety

**Context**: spec `001-launcher-container-cdk`, container `Dockerfile`.

**Issue**: The plan targeted Python 3.14, but `public.ecr.aws/lambda/python:3.14`
and manylinux wheels for compiled deps (pydantic-core, uvloop) at 3.14 were not
reliably available; a 3.12 base + 3.12-built venv guarantees ABI-matched
site-packages copied to `${LAMBDA_TASK_ROOT}`.

**Resolution**: `container/Dockerfile` builds on `public.ecr.aws/lambda/python:3.12`,
pins `uv:0.11.3` (matches the lock-generating uv), runs `uv sync --no-dev` into
`/opt/venv` and copies `lib/python3.12/site-packages/*` to the task root. The
launcher `requires-python` is `>=3.11` so the source is unchanged.

**Prevention**: For Lambda container images, pin the base Python to a version
with mature manylinux wheel coverage and build the venv in the same base so
compiled extensions match the runtime ABI exactly.

**Refs**: `container/Dockerfile`, `launcher/pyproject.toml`.

---

### Anthropic Python SDK has first-party managed-agents helpers — worker is portable to Python

**Context**: spec `001-launcher-container-cdk`, deciding whether the in-MicroVM
worker could be ported from TypeScript to Python.

**Issue**: Whether `EnvironmentWorker`/`WorkPoller` (the beta managed-agents
environments helpers the TS worker depends on) exist in the Python SDK — the
deciding factor for a port.

**Resolution**: Web research confirmed the Python SDK ships full parity
(`anthropic.lib.environments.EnvironmentWorker`,
`client.beta.environments.work.poller`,
`client.beta.sessions.events.tool_runner`, `beta_agent_toolset_20260401`),
added in commit `e5625b0` (2026-05-19). Helpers exist in **Python, TypeScript,
and Go only — not Rust**. All are **async-only** (on `AsyncAnthropic`).

**Prevention**: When scoping a worker port, start from the SDK helpers, not raw
HTTP. A Rust worker would require reimplementing an undocumented beta protocol —
don't attempt it.

**Refs**: `specs/001-launcher-container-cdk/research.md`, `plan.md`; anthropic-sdk-python `helpers.md`.

---

### One container image for dev/prod parity (Lambda + local uvicorn via Mangum)

**Context**: spec `001-launcher-container-cdk`, launcher packaging decision.

**Issue**: How to satisfy the constitution's "run locally + replicate in Docker
Compose" (Principle V / Factor X) without maintaining two artifacts (a zip
Lambda + a separate FastAPI app).

**Resolution**: One OCI image on `public.ecr.aws/lambda/python:3.14` with a
FastAPI app; `handler = Mangum(app)` is the Lambda entrypoint, `uvicorn` serves
the same app locally (compose overrides the command). One image, two entry modes.

**Prevention**: For any future Lambda that needs local parity, prefer the
container-image + Mangum pattern over a zip Lambda + separate local adapter.

**Refs**: `specs/001-launcher-container-cdk/plan.md`, `contracts/webhook.md`.

---

### Async-first without rewriting Powertools idempotency

**Context**: spec `001-launcher-container-cdk`, constitution Principle III
(async-first).

**Issue**: Powertools Idempotency is synchronous; rewriting it as an async
DynamoDB layer is high-risk for a security-critical dedupe path.

**Resolution**: The FastAPI route is `async def`; blocking I/O (boto3
`RunMicrovm`, Powertools secret retrieval and idempotency) is offloaded with
`anyio.to_thread.run_sync`. Powertools idempotency stays sync (wrapped), not
reimplemented. Documented as a justified deviation in the plan's Complexity
Tracking.

**Prevention**: Don't rewrite battle-tested sync library features as async just
to satisfy "async-first" — offload them off the event loop instead. Async-first
means "the loop never blocks," not "every line is `await`."

**Refs**: `specs/001-launcher-container-cdk/plan.md` (Constitution Check, Complexity Tracking).

---

### Upstream botocore (>= 1.43.40) ships lambda-microvms — vendored wheels dropped

**Context**: spec `001-launcher-container-cdk`, dependency management.

**Issue**: The launcher depends on the boto3 `lambda-microvms` client. Earlier in
the cycle upstream `boto3`/`botocore` did NOT ship that service model, so the
repo vendored pinned wheels (`boto3`/`botocore` 1.43.34) wired via
`[tool.uv.sources]`. That was the original rationale for the wheels.

**Resolution**: As of `botocore` 1.43.40, upstream ships the `lambda-microvms`
service model (verified: `boto3.client("lambda-microvms", ...)` resolves to a
`LambdaMicroVMs` client from a plain PyPI install). The vendored wheels and
`[tool.uv.sources]` are removed; `launcher/pyproject.toml` pins
`boto3`/`botocore >= 1.43.40` from upstream. The container image installs boto3
straight from PyPI — no wheels to copy.

**Prevention**: Re-check whether a once-missing service model has landed upstream
before keeping vendored wheels pinned; boto3/botocore ship new models frequently.
Vendor only as a last resort, and revisit the decision each cycle.

**Refs**: `launcher/pyproject.toml`, `launcher/src/launcher/shared/microvm_client.py`,
`specs/001-launcher-container-cdk/research.md`.