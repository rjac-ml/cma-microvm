# Tasks: Launcher Container Image & CDK IaC

**Input**: Design documents from `/specs/001-launcher-container-cdk/`

**Prerequisites**: plan.md (required), spec.md (required), research.md, data-model.md, contracts/webhook.md, quickstart.md

**Tests**: INCLUDED — TDD is mandated by the constitution (Principle II). Within each
user story, test tasks precede their implementation counterparts (Red-Green-Refactor
applied during implementation; enforced at the final PR).

**Organization**: Tasks grouped by user story (US1–US5) to enable independent
implementation and testing. Setup + Foundational phases block all stories.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: parallelizable (different files, no dependency on incomplete tasks)
- **[Story]**: user story this task belongs to (US1–US5)
- Exact file paths in every description

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Repo reorganization, UV projects, automation skeleton, container base.

- [ ] T001 Create UV project at repo root via `uv init` + `uv add fastapi mangum "uvicorn[standard]" "anthropic[webhooks]" aws-lambda-powertools pydantic-settings loguru` and dev deps `uv add --dev ruff pytest anyio`; reference vendored wheels in `src/launcher/wheels/` — `pyproject.toml`
- [ ] T002 [P] Create CDK UV project: `cd utils/cdk && uv init && uv add aws-cdk-lib constructs` + `uv add --dev pytest` — `utils/cdk/pyproject.toml`
- [ ] T003 Reorganize repo: `git mv src/functions/launcher.py src/launcher/launcher.py`, move `shared/` and `wheels/` under `src/launcher/`, add `src/launcher/__init__.py`; fix imports to `launcher.shared.*`; then `git rm -r src/functions/` (remove the stale duplicate incl. its `requirements.txt`) — `src/launcher/`
- [ ] T004 [P] Add Justfile with recipe stubs (install, lint, test, run-local, build-launcher, cdk-synth, cdk-deploy, build-image, verify) — `justfile`
- [ ] T005 [P] Add `docker-compose.yml` (NO `version:` key) defining the local launcher service + DynamoDB Local — `docker-compose.yml`
- [ ] T006 [P] Add `.pre-commit-config.yaml` wiring `ruff` (Rust-backed Python validator) for lint+format — `.pre-commit-config.yaml`
- [ ] T007 [P] Add CI skeleton: UV install → lint → test → build launcher image — `.github/workflows/ci.yml`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core launcher adaptation shared by all user stories. MUST complete before any story.

- [ ] T008 Convert `LauncherConfig` to Pydantic-settings (env loader) in `src/launcher/config.py` (replaces the dataclass in `shared/types.py`)
- [ ] T009 Add Loguru logging setup in `src/launcher/logging.py`; route launcher logs to stdout (Factor XI)
- [ ] T010 Adapt `src/launcher/launcher.py` to the new package layout (`launcher.shared.*`), keep the pure `Launcher` core with injected `MicroVmClient` + swappable executor
- [ ] T011 Implement `StubMicroVmClient` (satisfies the `MicroVmClient` Protocol) returning a fixed `LaunchedMicroVm` — `src/launcher/shared/stub_client.py`
- [ ] T012 Add async-offload helper wrapping blocking I/O with `anyio.to_thread.run_sync` — `src/launcher/asyncio_utils.py`

**Checkpoint**: Foundation ready — user story implementation can begin.

---

## Phase 3: User Story 1 - Run the launcher locally without AWS (Priority: P1) 🎯 MVP

**Goal**: `just run-local` brings up the launcher in Docker Compose with a stub MicroVM; a signed webhook returns a stub `microvm_id`, an unsigned one returns 401.

**Independent Test**: `just run-local` then send a signed/unsigned webhook request; verify 200/401 without AWS.

### Tests for User Story 1 (write first, watch fail)

- [ ] T013 [P] [US1] Contract test for `POST /webhook` (401 bad sig, 200 start, 200 ignored non-start) in `tests/contract/test_webhook.py`
- [ ] T014 [P] [US1] Integration test: signed webhook → stub dispatch → 200 `{microvm_id, session_id}` in `tests/integration/test_dispatch_flow.py`
- [ ] T014b [P] [US1] Lambda-mode test: invoke the Mangum handler (`app.handler`) with a synthetic API Gateway proxy event and assert the same 401/200 behavior as the local route (dev/prod parity, SC-003) in `tests/contract/test_mangum_handler.py`
- [ ] T015 [P] [US1] Unit test: idempotency dedupe (concurrent same event id → exactly one launch) in `tests/unit/test_idempotency.py`
- [ ] T016 [P] [US1] Unit test: rate limiter + credential-boundary forbidden-key guard in `tests/unit/test_payload.py`

### Implementation for User Story 1

- [ ] T017 [US1] Implement FastAPI app + `handler = Mangum(app)` in `src/launcher/app.py` (`async def /webhook`, verify signature via threadpool, delegate to `Launcher.handle`)
- [ ] T018 [US1] Implement `src/launcher/container/Dockerfile` (`public.ecr.aws/lambda/python:3.14`, `uv` install, `CMD ["app.handler"]`; uvicorn available for local override)
- [ ] T019 [US1] Wire `docker-compose.yml` to run the launcher image with `uvicorn` + `StubMicroVmClient` + DynamoDB Local; inject signing secret via env
- [ ] T020 [US1] Implement `just run-local` and `just test` recipes in `justfile`

**Checkpoint**: User Story 1 fully functional and testable locally with no AWS.

---

## Phase 4: User Story 2 - Deploy via CDK with a container-image Lambda (Priority: P1)

**Goal**: `just cdk-synth` produces a CloudFormation template resource/output-equivalent to the current SAM stack; `just cdk-deploy` runs a working webhook endpoint that launches a MicroVM.

**Independent Test**: `cdk synth` diff vs SAM; `cdk deploy` then `just verify` end-to-end.

### Tests for User Story 2 (write first, watch fail)

- [ ] T021 [P] [US2] CDK construct unit test: container-image Lambda + least-privilege IAM (`lambda:RunMicroVm`, `iam:PassRole`, `lambda:PassNetworkConnector`, scoped DynamoDB, signing-secret-only GetSecretValue) in `utils/cdk/tests/test_lambda_construct.py`
- [ ] T022 [P] [US2] CDK construct unit test: WAFv2 WebACL + logging + stage association in `utils/cdk/tests/test_waf_construct.py`
- [ ] T023 [P] [US2] CDK stack test: outputs match SAM outputs (`WebhookUrl`, `EnvironmentKeySecretArn`, `SigningSecretArn`, `BuildRoleArn`, `MicroVmExecutionRoleArn`, `ArtifactBucketName`) in `utils/cdk/tests/test_stack_parity.py`

### Implementation for User Story 2

- [ ] T024 [US2] Implement CDK entry `utils/cdk/app.py` (App + `ControlPlaneStack`)
- [ ] T025 [US2] Implement secrets + idempotency constructs in `utils/cdk/control_plane/secrets_construct.py` and `idempotency_construct.py`
- [ ] T026 [US2] Implement container-image Lambda construct (`DockerImageFunction` from `src/launcher/container/`) + IAM in `utils/cdk/control_plane/lambda_construct.py`
- [ ] T027 [US2] Implement API Gateway REST + `AnthropicWebhookEvent` model + request validator in `utils/cdk/control_plane/api_construct.py`
- [ ] T028 [US2] Implement WAFv2 WebACL (managed rule sets + per-IP rate limit) + logging + stage association (`node.addDependency` on the stage) in `utils/cdk/control_plane/waf_construct.py`
- [ ] T029 [US2] Implement S3 artifact bucket + build role in `utils/cdk/control_plane/image_build_construct.py`
- [ ] T030 [US2] Compose all constructs + outputs in `utils/cdk/control_plane/stack.py`
- [ ] T031 [US2] Implement `just cdk-synth` and `just cdk-deploy` recipes; run parity diff vs SAM-deployed stack

**Checkpoint**: Control plane deployable via CDK with parity to SAM.

---

## Phase 5: User Story 3 - One-command repo automation (Priority: P2)

**Goal**: Every common workflow is a single `just <recipe>`.

**Independent Test**: each recipe executes its full flow with one command and exits non-zero on failure.

- [ ] T032 [US3] Complete all Justfile recipes: `install`, `lint`, `test`, `build-launcher`, `run-local`, `cdk-synth`, `cdk-deploy`, `build-image`, `verify` — `justfile`
- [ ] T033 [US3] Smoke-verify each recipe runs end-to-end (document results in `quickstart.md`)

**Checkpoint**: All workflows automated.

---

## Phase 6: User Story 4 - Reorganized, launcher-and-worker-friendly repo (Priority: P2)

**Goal**: Repo layout clearly separates Python launcher, CDK, and the untouched TypeScript worker; existing image build still works.

**Independent Test**: `just build-image` succeeds (worker source reachable); tree matches plan.

- [ ] T034 [US4] Verify `src/scripts/build-image.sh` still succeeds against `src/microvm-image/` (worker unchanged)
- [ ] T035 [US4] Update `README.md` deploy section to point at CDK (`utils/cdk`) and Justfile; note SAM retained as parity reference only
- [ ] T036 [US4] Add header comment to `template.yaml` marking it superseded by CDK (parity reference; not built/deployed)

**Checkpoint**: Repo reorganized and consistent.

---

## Phase 7: User Story 5 - CI builds the launcher image (Priority: P3)

**Goal**: CI builds the launcher container image and runs tests on every change.

**Independent Test**: on push, CI builds the image and runs tests; a failing test fails the pipeline.

- [ ] T037 [US5] Complete `.github/workflows/ci.yml`: UV install → `just lint` → `just test` → `just build-launcher` → `just cdk-synth`; tag the image on `main`
- [ ] T038 [US5] Document CI in `README.md`

**Checkpoint**: CI green; image artifact produced.

---

## Phase N: Polish & Cross-Cutting Concerns

**Purpose**: Invariants, parity, and repo hygiene across all stories.

- [ ] T039 [P] Credential-boundary test asserting neither `ANTHROPIC_API_KEY` nor `ANTHROPIC_ENVIRONMENT_KEY` appears in the run-hook payload (FR-004) in `tests/unit/test_payload.py`
- [ ] T040 [P] Parity verification: `cdk synth` diff vs SAM-deployed resources; record result in `quickstart.md`
- [ ] T041 [P] Run `ruff` + pre-commit clean across the repo
- [ ] T042 [P] Update `CLAUDE.md` architecture notes to reflect the new launcher/CDK layout
- [ ] T043 Final end-to-end validation: `just run-local` (local) and `just verify` (operator, AWS) — run by the user

---

## Dependencies & Execution Order

### Phase Dependencies
- **Setup (Phase 1)**: no dependencies; start immediately.
- **Foundational (Phase 2)**: depends on Setup; BLOCKS all user stories.
- **US1 (Phase 3)**: depends on Foundational — MVP, do first.
- **US2 (Phase 4)**: depends on Foundational; the launcher image from US1 is the
  CDK `DockerImageFunction` source, so US1 should land first.
- **US3 (Phase 5)**: depends on US1 + US2 recipes existing.
- **US4 (Phase 6)**: mostly satisfied by Setup; verification after US1+US2.
- **US5 (Phase 7)**: depends on US1+US2+US3 recipes.
- **Polish (Final)**: after all desired stories.

### Within Each User Story
- Tests written FIRST and watched FAIL before implementation (Principle II).
- Config/models before services; services before endpoints/constructs.
- Story complete before next priority.

### Parallel Opportunities
- Phase 1: T002, T004, T005, T006, T007 are mutually parallel.
- Phase 2: T011, T012 parallel after T008–T010.
- US1 tests T013–T016 parallel; US2 tests T021–T023 parallel.
- US2 constructs T025–T029 parallel where independent (different files).

---

## Implementation Strategy

### MVP First (User Story 1 only)
1. Phase 1 Setup → Phase 2 Foundational → Phase 3 US1 → STOP and validate locally.
2. `just run-local` + `just test` green = MVP delivered (local parity, no AWS).

### Incremental Delivery
1. US1 (local) → validate.
2. US2 (CDK deploy) → parity diff, then `just verify` end-to-end.
3. US3 (automation) → US4 (reorg verify + docs) → US5 (CI).
4. Polish: credential-boundary test, parity record, lint clean.

### Notes
- Tests are NOT optional here (constitution Principle II). Every story ships tests.
- The worker (TypeScript) is deliberately untouched this cycle.
- `sam build`/`sam deploy` are no longer the deploy path; CDK is. SAM is a parity reference only.

## Notes

- [P] tasks = different files, no dependencies.
- [Story] label maps a task to its user story for traceability.
- Verify tests fail before implementing (Red-Green-Refactor).
- Commit after each task or logical group; merge via PR, never directly to `main`.

---

## Implementation Status (cycle 001 — Phase 10 complete)

Tests: **24 passing** (18 launcher + 6 CDK construct), `ruff check`/`ruff format`
clean, `just cdk-synth` produces the control-plane template. See `KNOWLEDGE.md`
for post-implementation learnings.

**Completed (core):** T001, T002, T003, T004, T005, T006, T007, T008, T009, T010,
T011, T012, T013, T014, T014b, T015, T017, T018, T019, T020, T024, T025, T026,
T030, T032, T035, T036, T037, T039, T041, T042.

**Partial / with deviations:**

- T016 — credential-boundary forbidden-key guard done (`test_payload.py`);
  a dedicated `TokenBucket` rate-limiter unit test is deferred (covered
  indirectly via the dispatch flow).
- T021/T023 — construct/stack tests done in `utils/cdk/tests/test_control_plane.py`
  (resource counts + env/credential assertions). Least-privilege IAM action
  assertions (`lambda:RunMicroVm`, `iam:PassRole`, …) and the full SAM output
  parity set are deferred.
- T027 — API Gateway implemented as an **HTTP API** (`HttpApi`), not a REST API
  with a request validator + `AnthropicWebhookEvent` model. The signature is
  verified in the Lambda (the documented rationale for no authorizer), so a
  request validator is not strictly needed; revisiting as REST is a follow-up.
- T031 — `just cdk-synth` works (CLI-free, structural template); `just cdk-deploy`
  is a delegated recipe (needs the `cdk` CLI + AWS creds). SAM parity diff not
  run automatically (T040).
- T033/T038 — quickstart/CI documented in `README.md` (banner + quickstart); the
  dedicated `quickstart.md` update is pending.
- T034 — `src/scripts/build-image.sh` (Node worker, unchanged) was **not** run
  this cycle (delegated to the operator); the worker is untouched as scoped.

**Deferred (out of this cycle's scope, follow-up):**

- T022 / T028 — WAFv2 WebACL construct + tests. The SAM WAF (managed rule sets
  + per-IP rate limit + `aws-waf-logs-` log group) is not yet reproduced in CDK.
- T029 — S3 artifact bucket + build role construct. CDK builds the image via
  `DockerImageFunction` asset (no separate S3/build-role construct needed for
  the launcher); the MicroVM image build still uses `src/scripts/build-image.sh`.
- T040 — automated `cdk synth` vs SAM parity diff.
- T043 — final end-to-end validation (`just run-local` local + `just verify`
  operator/AWS) — run by the user.

**Key deviation vs plan:** the container base is
`public.ecr.aws/lambda/python:3.12` (not 3.14) for manylinux wheel ABI safety;
`requires-python` stays `>=3.11`. See `KNOWLEDGE.md`.

---

## Post-cycle restructure (2026-07-06, PR #1 follow-up)

After the cycle closed, PR #1 review surfaced three fixes applied as a
follow-up commit on the same branch:

- **Per-component UV projects.** The repo is now a small monorepo: `launcher/`
  (the launcher — its own UV project + tests + operator scripts), `worker/`
  (empty Python-port scaffold; the running worker is still the TypeScript
  `src/microvm-image/`), and `utils/cdk/` (CDK). The root holds only
  orchestration (Justfile, `docker-compose.yml`, `container/Dockerfile`, CI,
  docs). The old root `pyproject.toml` / `uv.lock` moved into `launcher/`.
- **Vendored wheels dropped.** Upstream `botocore` >= 1.43.40 ships the
  `lambda-microvms` service model (verified — a `LambdaMicroVMs` client is
  creatable from a plain PyPI install), so the vendored `boto3`/`botocore`
  1.43.34 wheels and `[tool.uv.sources]` are removed; `launcher/pyproject.toml`
  pins `boto3`/`botocore >= 1.43.40`. See `KNOWLEDGE.md`.
- **Container build fixed.** The Dockerfile's `UV_PYTHON` pointed at a
  non-existent path; the correct interpreter is `/var/lang/bin/python3.12`.
  `docker-compose.yml` also overrode only `command:` — but the Lambda base
  `/lambda-entrypoint.sh` exits 142 unless it receives exactly one arg (the
  handler), so compose now overrides `entrypoint:` to `/var/lang/bin/python3`
  and sets `PYTHONPATH=/var/task`. See `KNOWLEDGE.md`.
- **CDK test import fix.** `utils/cdk/pyproject.toml` gained
  `pythonpath = ["."]` so `uv run pytest` can import `control_plane` (matching
  `uv run python app.py`, which puts the script dir on `sys.path`).
- **CI** adds a `worker` (scaffold) lint+test job; the `lint-test` job runs in
  `launcher/` (`working-directory`).

Verified locally: 18 launcher + 6 CDK + 1 worker tests pass; `ruff` clean;
`just cdk-synth` writes the template. `just docker-build` / `just docker-up` /
`just cdk-deploy` remain operator-delegated.