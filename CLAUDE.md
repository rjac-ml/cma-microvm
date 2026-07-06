# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working in this repository.

<!-- SPECKIT START -->
For additional context about technologies to be used, project structure,
shell commands, and other important information, read the current plan:
`specs/001-launcher-container-cdk/plan.md` (feature: Launcher Container Image &
CDK IaC). Supporting artifacts live alongside it: `research.md`,
`data-model.md`, `contracts/webhook.md`, `quickstart.md`, `tasks.md`.
<!-- SPECKIT END -->

## What this is

A reference solution that runs [Claude self-hosted sandbox](https://platform.claude.com/docs/en/managed-agents/self-hosted-sandboxes)
tool execution inside [AWS Lambda MicroVMs](https://docs.aws.amazon.com/lambda/).
Pattern: **orchestrator + ephemeral MicroVM per session**. Anthropic's control
plane handles orchestration; an event-driven control plane in the user's AWS
account launches one fresh, isolated MicroVM per Claude session. See `README.md`
for the full narrative and `docs/architecture.png`.

## Three independent UV projects

The repo is a small monorepo. Each runtime is its own UV project with its own
`pyproject.toml` / `uv.lock`; the **root holds only orchestration** (Justfile,
`docker-compose.yml`, `container/Dockerfile`, CI, docs, specs). Do not mix deps
across projects. Understand which one you are touching before editing:

1. **Launcher** (Python) — `launcher/`. A FastAPI app that verifies the inbound
   webhook and calls `RunMicrovm`. One OCI image runs two ways: under `uvicorn`
   locally and under **Mangum** as a Lambda container image. Operator scripts
   (`launcher/scripts/verify.py`, `build-image.sh`) live here too.
2. **Worker** (Python scaffold) — `worker/`. A placeholder UV project for the
   future Python port of the in-MicroVM hook server. The **current, running
   worker is still TypeScript** at `src/microvm-image/` (`worker/worker.mjs`),
   built with `npm` inside its Dockerfile and snapshotted at image-build time.
   Porting it to Python is a separate, out-of-scope follow-up spec.
3. **CDK control plane** (Python) — `utils/cdk/`. The CDK stack + constructs that
   deploy the launcher. The SAM `template.yaml` at the root is retained only as a
   parity reference and is superseded.

`boto3`/`botocore` come from upstream PyPI (>= 1.43.40 ships the
`lambda-microvms` service model) — no vendored wheels.

## Commands (Justfile)

```bash
just sync            # launcher: uv sync (install deps)
just run-local       # launcher: uvicorn launcher.app:app with LAUNCHER_USE_STUB=1 (no AWS)
just test            # launcher: pytest -q  (18 tests)
just test-one tests/contract/test_webhook.py::test_signed_start_returns_200_with_microvm_id
just lint            # launcher: ruff check .
just format          # launcher: ruff format .
just verify          # launcher: lint + format-check + test gate
just worker-test     # worker scaffold: pytest -q  (1 test)
just worker-lint     # worker scaffold: ruff check .
just docker-build    # build the Lambda container image (context = repo root)
just docker-up       # compose: DynamoDB Local + launcher (uvicorn) on :8080
just cdk-synth       # synthesize the CDK control-plane template (no Docker)
just cdk-test        # CDK construct tests (6 tests; needs Node on PATH — see note)
just cdk-deploy      # DELEGATED: needs Docker + `cdk` CLI + AWS creds + bootstrap
```

Recipes `cd` into the right project themselves — run them from the repo root.

Do **not** run `make` targets — ask the user. Do not run `just docker-build` /
`just docker-up` / `just cdk-deploy` / `docker push` yourself — those build the
image or touch AWS/external registries; delegate them to the operator.

### CDK tests need Node

The CDK Python libs are jsii-backed and require `node` to synthesize. On this
machine node is managed by asdf; pin and expose it:

```bash
PATH="$HOME/.asdf/installs/nodejs/22.1.0/bin:$PATH" just cdk-test
# (pinned in utils/cdk/.tool-versions)
```

## Architecture: the request flow

The control plane is **event-driven with no poller**; the only inbound traffic
is the webhook. The credential boundary is the most important invariant —
preserve it in any change:

1. A Claude session reaches running state → Anthropic POSTs a
   `session.status_run_started` **webhook** to the HTTP API `/webhook`.
2. The **launcher** verifies the **webhook signature in-process**
   (`anthropic` SDK `client.beta.webhooks.unwrap`, signed in tests with
   `standardwebhooks`) using the signing secret from Secrets Manager. This HMAC
   check is the *only* authentication. Failure → 401 before any MicroVM
   launches.
3. The launcher calls `RunMicrovm` with the session dispatch delivered via
   `runHookPayload`. It **dedupes on webhook event id** (DynamoDB-backed
   Powertools Idempotency, so retried/concurrent deliveries launch exactly one
   VM) and enforces the 5 TPS RunMicrovm rate limit (token bucket).
4. The **MicroVM** receives the dispatch on its `/run` hook, fetches the
   environment key from Secrets Manager using its own execution role, claims
   the matching session, runs the agent's tool calls, posts results back, and
   exits; the idle policy suspends/terminates the VM.

**Credential boundary (must not break):** The organization API key is
operator-only and **never** reaches AWS compute or a MicroVM. The launcher reads
**only the signing secret** and passes only a *reference* (secret ARN) to the
environment-key secret into the VM. The **MicroVM's execution role** reads
**only** the environment key. `src/launcher/shared/payload.py` enforces this
with a `_FORBIDDEN_KEYS` guard — never put `ANTHROPIC_API_KEY` or
`ANTHROPIC_ENVIRONMENT_KEY` in the run-hook payload (test-asserted in
`launcher/tests/unit/test_payload.py` and `launcher/tests/unit` boundary checks;
CDK env checked in `utils/cdk/tests/test_control_plane.py`).

## Key files and why they exist

- `launcher/src/launcher/app.py` — FastAPI app + `handler = Mangum(app)`. The
  webhook route is `async def`; the blocking `process_webhook` flow is offloaded
  to a worker thread via `anyio.to_thread.run_sync` (constitution Principle III).
- `launcher/src/launcher/launcher.py` — `verify_signature`, the pure `Launcher`
  class, idempotency builders (`build_idempotency_with`/`reset_idempotency` let
  tests inject an in-memory persistence layer), `make_client` (stub vs boto3),
  and `process_webhook` (the full blocking flow).
- `launcher/src/launcher/config.py` — `LauncherConfig` (Pydantic-settings,
  env-driven; env var aliases match the CDK/SAM template).
- `launcher/src/launcher/shared/microvm_client.py` — `Boto3MicroVmClient` calling
  the `lambda-microvms` service via upstream boto3/botocore (>= 1.43.40 ships the
  model — no vendored wheels).
- `launcher/src/launcher/shared/rate_limiter.py` — `TokenBucket` enforcing the 5
  TPS limit.
- `container/Dockerfile` — single-stage build on the AWS Lambda Python base
  (`/var/lang/bin/python3.12`); `uv sync --no-dev` installs runtime deps
  (ABI-matched to the runtime) from `launcher/uv.lock`, then the app source is
  copied to `${LAMBDA_TASK_ROOT}/launcher`. `.dockerignore` limits the context to
  `launcher/`.
- `docker-compose.yml` — local parity; overrides the image `entrypoint:` to
  `/var/lang/bin/python3` to run uvicorn (the base `/lambda-entrypoint.sh` takes
  exactly one arg — the handler) and sets `PYTHONPATH=/var/task`.
- `utils/cdk/` — the CDK control plane (stack + constructs). `app.py` pins
  `outdir="cdk.out"` and gates the real Docker image build behind
  `CDK_BUILD_IMAGE=1` (default) so `just cdk-synth` works without Docker.
- `template.yaml` — **superseded** SAM reference; kept for parity diffing
  against the CDK output (FR-007).
- `src/microvm-image/worker/worker.mjs` — the in-VM hook server (Node.js; the
  current worker — `worker/` is the Python-port scaffold).
- `launcher/scripts/build-image.sh` / `verify.py` — operator-side MicroVM image
  build and end-to-end verify (use the org API key, never AWS compute).

## Conventions

- The launcher targets **Python 3.11+ / arm64**. `anthropic[webhooks]` +
  `aws-lambda-powertools` are imported at module scope so cold-start cost is
  paid once.
- Async-first: routes are `async def`; blocking I/O (boto3, Powertools secret
  fetch + idempotency) runs in a threadpool. Sync Powertools idempotency is a
  *justified deviation* (see the plan's Complexity Tracking), wrapped via
  `run_sync`.
- Malformed webhook events return **200** (not 4xx) so Anthropic does not
  retry — a malformed event will never become valid. Only launch failures and
  signature failures return non-2xx.
- This repo uses **Spec-Driven Development (speckit)** — the `/speckit-*` skills
  drive specify → plan → tasks → implement. TDD is applied during
  implementation and enforced at the final PR (per the constitution).
- Per the user's standing preferences: for Python, prefer `uv add` / `uv init`
  with `pydantic-settings` and `loguru`; do not add a `version:` key to
  docker-compose files; do not run `make` targets — ask the user.