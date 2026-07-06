# Research: Launcher Container Image & CDK IaC

Phase 0 output. Resolves every Technical Context unknown and locks the
technology choices behind the plan. Each entry: Decision / Rationale /
Alternatives considered.

## 1. Lambda container image runtime + ASGI bridge

**Decision**: Package the launcher as an OCI container image on the AWS-provided
`public.ecr.aws/lambda/python:3.14` base, with FastAPI as the app and **Mangum**
as the ASGI→Lambda event adapter (`handler = Mangum(app)`). Locally the same
image runs under `uvicorn` (compose overrides the command).

**Rationale**: One image, two entry modes = true dev/prod parity (constitution
Principle V / Factor X). The AWS base image already embeds the Lambda Runtime
Interface Client, so no manual RIC wiring. Mangum is the canonical, stable
FastAPI↔Lambda bridge (3-line shim). The current `handler()` is a Lambda/API-GW
adapter — Mangum replaces exactly that seam; the pure `Launcher` core is reused.

**Alternatives**:
- Zip Lambda + a separate FastAPI adapter (two artifacts) — rejected: violates
  dev/prod parity and doubles the surface.
- ALB + always-on Fargate container instead of Lambda — rejected: the webhook is
  rare/bursty (~1/session); always-on compute is wasteful and adds ops burden;
  Lambda scales to zero and is the reference design.

## 2. CDK language and project layout

**Decision**: CDK in **Python**, as a separate UV project at `utils/cdk/`, using
`aws_lambda.DockerImageFunction` with `DockerImageCode.from_image_asset()`.

**Rationale**: Constitution is Python-first; one language across repo + launcher.
A separate UV project keeps `aws-cdk-lib` (heavy) out of the Lambda image. CDK
gives imperative, composable, **unit-testable** infra (TDD applies to constructs
too via `aws_cdk.assertions.Template`), which SAM's declarative YAML cannot.

**Alternatives**:
- CDK in TypeScript (most CDK docs/examples are TS) — rejected: adds a second
  language and breaks repo Python-first consistency.
- Stay on SAM — rejected: GOAL mandates CDK as the deploy template generator.
- Pulumi (multi-cloud) — rejected: Lambda MicroVMs is AWS-only; no multi-cloud
  portability to preserve for the control plane.

## 3. Async strategy for the launcher

**Decision**: The `/webhook` route is `async def`; all blocking I/O — boto3
`RunMicrovm`, Powertools `get_secret`, and Powertools idempotency — is offloaded
with `anyio.to_thread.run_sync`. Powertools idempotency stays in its synchronous
form (wrapped), not reimplemented async.

**Rationale**: Constitution Principle III (async-first) requires the event loop
never blocks; offloading achieves that without rewriting a security-critical
dedupe layer. The webhook is rare and runs on a single Lambda instance, so async
idempotency yields no throughput gain and only adds risk.

**Alternatives**:
- Reimplement idempotency as an async DynamoDB layer — rejected: re-owns lease/
  heartbeat/TTL semantics Powertools already handles correctly; high risk, low
  reward (see Complexity Tracking).
- Use sync `def` routes (FastAPI auto-threadpools) — rejected: less explicit
  about async intent; `async def` + explicit `run_sync` matches the constitution
  language and is clearer to future readers.

## 4. boto3 / lambda-microvms service model

**Decision**: Keep the **vendored `boto3`/`botocore` wheels** (the pinned
versions that include the `lambda-microvms` service model) and install them
into the image via UV (path/wheel reference), exactly as today.

**Rationale**: Upstream boto3 does not ship the `lambda-microvms` service model;
the vendored wheels are the known-good client. A container image lets us install
them cleanly (no 250 MB unzipped zip limit), but the model source is the same.

**Alternatives**:
- Use upstream boto3 and `aws configure add-model` at runtime — rejected:
  non-deterministic in a function env and adds cold-start cost; vendoring is
  reproducible.

## 5. Idempotency in local (no-DynamoDB) mode

**Decision**: When `IDEMPOTENCY_TABLE` is unset, the launcher skips the
DynamoDB-backed idempotency wrapper and runs the executor unwrapped (as today).
Local tests that need to assert dedupe run against a local DynamoDB (Docker
Compose service) or a fake persistence layer.

**Rationale**: Local parity should exercise the real control flow; DynamoDB
Local in compose gives true parity for the dedupe path. Keeping the
"unset → skip" behavior preserves the existing, tested fallback.

**Alternatives**:
- Always require DynamoDB Local locally — partial; keep the skip fallback for
  fast unit tests and use DynamoDB Local only for the integration/dedupe test.

## 6. Repo reorganization and SAM transition

**Decision**: Move the launcher from `src/functions/` to `src/launcher/`
(UV package + container Dockerfile + `app.py`). Keep `src/microvm-image/`
(worker) untouched. Place CDK at `utils/cdk/`. Retain `template.yaml` as the
**parity reference** only — not built/deployed; remove in a follow-up PR.

**Rationale**: GOAL asks to reorder to accommodate launcher + worker. CDK becomes
the deploy path, so SAM need not keep building the (now image-based) launcher;
retaining it as a reference lets us diff CDK synth against the SAM-deployed
resources for parity, then delete it.

**Alternatives**:
- Update SAM to `PackageType: Image` too and keep it buildable — rejected:
  double-maintains two IaC for one image; the GOAL makes CDK canonical.
- Delete SAM immediately — rejected: lose the parity reference mid-migration.

## 7. Pre-commit + Rust-backed Python validation

**Decision**: `.pre-commit-config.yaml` runs `ruff` (lint+format) and a
**Rust-backed** validator hook for Python (e.g., a Rust binary/clippy-style gate
over the Python AST or a Rust-wrapped ruff), as the constitution requires.

**Rationale**: Constitution mandates "pre-commit connected with Rust to validate
Python." Concretely: a small Rust hook (or a Rust-built linter like `ruff`
itself, which is written in Rust) invoked by pre-commit. Using `ruff` (Rust
implementation) as the pre-commit Python validator satisfies both letters: the
Python validator *is* a Rust tool. If a custom gate is desired, a tiny Rust
crate wrapping the check is added; default to `ruff` to avoid scope creep.

**Alternatives**:
- A bespoke Rust AST checker — deferred; `ruff` (Rust) covers the spirit with
  far less code. Revisit if custom rules are needed.

## 8. CI scope this cycle

**Decision**: Minimal GitHub Actions workflow: install UV, `uv sync`, `just
lint`, `just test`, build the launcher container image, (optionally) `cdk synth`
to assert the template generates. Multi-cloud deploy matrix is a follow-up.

**Rationale**: Constitution requires CI that builds the image as the base for
cloud-provider deploys; this cycle delivers the image-build + test gate. The
multi-cloud matrix depends on choices outside this cycle's scope.

No `NEEDS CLARIFICATION` markers remain.