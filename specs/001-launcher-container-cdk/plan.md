# Implementation Plan: Launcher Container Image & CDK IaC

**Branch**: `001-launcher-container-cdk—launcher-image-cdk` | **Date**: 2026-07-06 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/001-launcher-container-cdk/spec.md`

## Summary

Repackage the Claude self-hosted sandbox launcher as a single OCI container image
that runs both locally (uvicorn in Docker Compose, with a stub MicroVM client) and
in AWS Lambda (via Mangum over the Lambda Runtime API), backed by a CDK control
plane at `utils/cdk/` that reproduces the current SAM stack. Add a Justfile for
all run/test/build/deploy workflows and a minimal CI that builds the image. The
repo is reorganized so the launcher is a first-class Python package (UV,
Pydantic-settings, Loguru, ruff, async-first) and the TypeScript worker stays
untouched this cycle. The existing pure `Launcher` core is reused, not rewritten.

## Technical Context

**Language/Version**: Python 3.14 (arm64) for the launcher Lambda runtime; CDK
app in Python 3.11+ (CDK tooling). TypeScript worker unchanged (Node 22+, AL2023).

**Primary Dependencies**: `fastapi`, `mangum`, `uvicorn[standard]`,
`anthropic[webhooks]`, `aws-lambda-powertools` (Logger, parameters, Idempotency),
`pydantic-settings`, `loguru`, `ruff`, and the vendored `boto3`/`botocore` wheels
that carry the `lambda-microvms` service model (kept; standard boto3 lacks it).
CDK: `aws-cdk-lib` (Python). Pre-commit wired to a Rust-backed Python validator.

**Storage**: No relational DB — therefore no Alembic/SQLModels this cycle.
Backing services (all externalized per Factor IV): DynamoDB (idempotency, TTL),
Secrets Manager (signing secret + environment key), S3 (image artifacts).

**Testing**: `pytest` (+ `anyio` for async) for the launcher control flow
(signature, parse, idempotency, rate limit, payload boundary, credential
invariant). CDK construct unit tests via `aws_cdk.assertions` (`Template`/
`Capture`). A stub `MicroVmClient` (the existing Protocol) drives local
end-to-end tests without AWS.

**Target Platform**: AWS Lambda (container image) behind API Gateway REST +
WAFv2; local reproduction in Docker Compose.

**Project Type**: web-service control plane + IaC (CDK) + repo automation
(Justfile) + CI.

**Performance Goals**: webhook response within a few seconds; cold start is
non-critical (Anthropic retries on non-2xx; webhook is off the user's latency
path). RunMicrovm 5 TPS enforced by the token bucket.

**Constraints**: 5s lifecycle-hook timeouts (worker side, unchanged); single
Lambda instance in prod (per-instance token bucket is sufficient — multi-replica
shared limiting is out of scope); credential boundary invariant (no org key /
env key on compute or in the run-hook payload) MUST hold and be test-asserted.

**Scale/Scope**: rare, bursty webhook volume (~1 delivery per session start);
one MicroVM per session. No high-throughput concerns.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Twelve-Factor by Default** — PASS. Config via env + Pydantic-settings
  (Factor III); backing services externalized (IV); stateless process (VI);
  self-bound port locally via uvicorn (VII); disposable, fast shutdown (IX);
  dev/prod parity via one container image (X); logs to stdout via Loguru (XI);
  admin/verify scripts run in identical env (XII). No exceptions.
- **II. Test-Driven Development** — PASS. Tests are written during
  implementation and enforced at the final PR (FR-012); the credential-boundary
  invariant is explicitly test-asserted (FR-004). Not a plan-time gate.
- **III. Async-First Microservices** — PASS WITH ONE JUSTIFIED DEVIATION. The
  FastAPI webhook route is `async def`; blocking I/O (boto3 `RunMicrovm`,
  Powertools secret retrieval and idempotency) is offloaded via
  `anyio.to_thread.run_sync` so the event loop is never blocked. **Deviation**:
  Powertools idempotency is used in its synchronous form (wrapped in a
  threadpool) rather than reimplemented as async. Justification: rewriting a
  custom async idempotency layer adds risk without benefit for a rare,
  single-instance webhook; the loop is still never blocked. See Complexity
  Tracking.
- **IV. Modularity & Readability** — PASS. `shared/` modules preserved;
  `MicroVmClient` Protocol injection retained (enables the stub for local
  parity and for tests). ASGI adapter is a thin `app.py`, not a rewrite of the
  core.
- **V. Reproducible Environments & Automation** — PASS. One container image
  runs locally (uvicorn) and in Lambda (Mangum); `docker-compose.yml` is the
  canonical local topology (no `version:` key per the rule); Justfile wraps
  all workflows; pre-commit + Rust validator included.

No Constitution MUST violations remain unresolved.

## Project Structure

### Documentation (this feature)

```text
specs/001-launcher-container-cdk/
├── spec.md              # Feature spec (/speckit-specify output)
├── plan.md              # This file (/speckit-plan output)
├── research.md          # Phase 0 output (decisions + alternatives)
├── data-model.md        # Phase 1 output (entities + transitions)
├── quickstart.md        # Phase 1 output (run/validate guide)
├── contracts/           # Phase 1 output (HTTP webhook contract)
│   └── webhook.md
└── tasks.md             # Phase 2 output (/speckit-tasks — not created by /speckit-plan)
```

### Source Code (repository root)

```text
.
├── justfile                       # recipes: install/lint/test/run-local/cdk-synth/cdk-deploy/build-image/verify
├── docker-compose.yml             # local launcher + stub; NO version: key
├── pyproject.toml                 # UV project: launcher app + tests
├── .pre-commit-config.yaml        # Rust-backed Python validator
├── .github/workflows/ci.yml       # build image + run tests
├── src/
│   ├── launcher/                  # Python launcher package (moved from src/functions/)
│   │   ├── __init__.py
│   │   ├── app.py                 # FastAPI app + Mangum handler (ASGI entrypoint)
│   │   ├── launcher.py            # pure Launcher core (reused, lightly adapted)
│   │   ├── config.py              # Pydantic-settings LauncherConfig (was shared/types.py)
│   │   ├── logging.py             # Loguru setup (replaces Powertools-only logging)
│   │   ├── container/
│   │   │   └── Dockerfile         # Lambda python base; uvicorn-capable; CMD = Mangum handler
│   │   ├── shared/                # payload, rate_limiter, microvm_client, types, constants
│   │   └── wheels/                # vendored boto3/botocore (lambda-microvms model) — kept
│   ├── microvm-image/             # UNCHANGED TypeScript worker (this cycle)
│   │   ├── Dockerfile
│   │   └── worker/worker.mjs
│   └── scripts/
│       ├── build-image.sh         # unchanged (references microvm-image/ only)
│       └── verify.py              # operator-side verify (unchanged behavior)
├── tests/
│   ├── unit/                      # signature, payload, rate limiter, config
│   ├── integration/               # webhook → dispatch flow with stub client (local + Lambda modes)
│   └── contract/                  # /webhook HTTP contract conformance
├── utils/
│   └── cdk/                       # CDK app (Python, UV) — the deploy template generator
│       ├── pyproject.toml         # UV: aws-cdk-lib, constructs
│       ├── app.py                 # CDK App + ControlPlaneStack
│       └── control_plane/
│           ├── __init__.py
│           ├── stack.py           # composes the constructs below
│           ├── lambda_construct.py# container-image Lambda (DockerImageFunction) + IAM
│           ├── api_construct.py   # API Gateway REST + request model/validator
│           ├── waf_construct.py   # WAFv2 WebACL + logging + stage association
│           ├── idempotency_construct.py  # DynamoDB table + TTL
│           ├── secrets_construct.py      # two Secrets Manager secrets
│           └── image_build_construct.py  # S3 artifact bucket + build role
├── template.yaml                  # SAM — RETAINED as parity reference only; not built/deployed
└── README.md                      # deploy section updated to point at CDK
```

**Structure Decision**: The launcher moves from `src/functions/` to
`src/launcher/` as a UV-managed Python package with its own container Dockerfile
and FastAPI/ASGI entrypoint. CDK lives at `utils/cdk/` as a separate UV project.
The TypeScript worker stays at `src/microvm-image/` untouched. SAM
`template.yaml` is retained solely as the resource/parity reference (CDK synth is
diffed against its deployed-equivalent); it is not built or deployed this cycle
and is removed in a follow-up cleanup PR. `build-image.sh` needs no path change
(it references `microvm-image/` only).

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| Synchronous Powertools idempotency wrapped in a threadpool (not reimplemented async) | Rewriting idempotency as an async layer is high-risk for a security-critical dedupe path | A custom async idempotency layer would own DynamoDB lease/heartbeat/TTL semantics currently handled by Powertools; the rare single-instance webhook gains no throughput from async idempotency, and the event loop is already protected by `anyio.to_thread.run_sync`. |
| Two UV projects (launcher + cdk) instead of one | CDK has a distinct, heavy dependency tree (`aws-cdk-lib`) that should not ship in the Lambda image | A single project would either bundle CDK into the runtime image (bloat, cold start) or require awkward optional-dependency management; separate projects keep the Lambda image minimal. |
| Vendored boto3/botocore wheels retained in the image | The `lambda-microvms` service model is not in upstream boto3 | Using upstream boto3 would lose the `lambda-microvms` client the launcher depends on; vendoring the pinned wheels that carry the model preserves exact behavior. |