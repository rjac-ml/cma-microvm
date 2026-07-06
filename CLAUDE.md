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

## Two independent codebases

This repo contains **two separate runtimes** that never share code. Understand
which one you are touching before editing:

1. **Launcher** (Python) — `src/launcher/`. A FastAPI app that verifies the
   inbound webhook and calls `RunMicrovm`. One OCI image runs two ways: under
   `uvicorn` locally and under **Mangum** as a Lambda container image. The
   control plane is defined in **CDK** at `utils/cdk/` (the SAM `template.yaml`
   is retained only as a parity reference and is superseded).
2. **In-MicroVM worker** (Node.js) — `src/microvm-image/`. An HTTP lifecycle-hook
   server baked into the MicroVM image. Built with `npm` inside the Dockerfile
   and snapshotted at image-build time. Has its own `package.json`; do not mix
   its deps with the Python side. **Porting this worker to Python is a separate,
   out-of-scope follow-up spec** (this cycle implements the launcher only).

The root `pyproject.toml` is a UV project holding the launcher's runtime + dev
deps (including the vendored boto3/botocore wheels at
`src/launcher/wheels/`, wired via `[tool.uv.sources]`). `src/scripts/verify.py`
is an operator-side script run from a developer's machine (uses the org API key).

## Commands (Justfile)

```bash
just sync            # uv sync (install deps)
just run-local       # uvicorn launcher.app:app with LAUNCHER_USE_STUB=1 (no AWS)
just test            # pytest -q  (18 launcher tests)
just test-one tests/contract/test_webhook.py::test_signed_start_returns_200_with_microvm_id
just lint            # ruff check .
just format          # ruff format .
just verify          # lint + format-check + test gate
just docker-build    # build the Lambda container image
just docker-up      # compose: DynamoDB Local + launcher (uvicorn) on :8080
just cdk-synth      # synthesize the CDK control-plane template (no Docker)
just cdk-test       # CDK construct tests (needs Node on PATH — see note)
just cdk-deploy     # DELEGATED: needs Docker + `cdk` CLI + AWS creds + bootstrap
```

Do **not** run `make` targets — ask the user. Do not run `just cdk-deploy` /
`docker push` yourself; those touch AWS/external registries.

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
`tests/unit/test_payload.py` and `tests/unit` boundary checks; CDK env checked
in `utils/cdk/tests/test_control_plane.py`).

## Key files and why they exist

- `src/launcher/app.py` — FastAPI app + `handler = Mangum(app)`. The webhook
  route is `async def`; the blocking `process_webhook` flow is offloaded to a
  worker thread via `anyio.to_thread.run_sync` (constitution Principle III).
- `src/launcher/launcher.py` — `verify_signature`, the pure `Launcher` class,
  idempotency builders (`build_idempotency_with`/`reset_idempotency` let tests
  inject an in-memory persistence layer), `make_client` (stub vs boto3), and
  `process_webhook` (the full blocking flow).
- `src/launcher/config.py` — `LauncherConfig` (Pydantic-settings, env-driven;
  env var aliases match the CDK/SAM template).
- `src/launcher/shared/microvm_client.py` — `Boto3MicroVmClient` calling the
  `lambda-microvms` service through **vendored** boto3/botocore wheels in
  `src/launcher/wheels/` (the Lambda runtime lacks this service model).
- `src/launcher/shared/rate_limiter.py` — `TokenBucket` enforcing the 5 TPS
  limit.
- `container/Dockerfile` — single-stage build on the AWS Lambda Python base;
  `uv sync --no-dev` installs runtime deps (ABI-matched to the runtime), then
  the app source is copied to `${LAMBDA_TASK_ROOT}/launcher`.
- `utils/cdk/` — the CDK control plane (stack + constructs). `app.py` pins
  `outdir="cdk.out"` and gates the real Docker image build behind
  `CDK_BUILD_IMAGE=1` (default) so `just cdk-synth` works without Docker.
- `template.yaml` — **superseded** SAM reference; kept for parity diffing
  against the CDK output (FR-007).
- `src/microvm-image/worker/worker.mjs` — the in-VM hook server (Node.js).
- `src/scripts/build-image.sh` / `verify.py` — operator-side image build and
  end-to-end verify (use the org API key, never AWS compute).

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