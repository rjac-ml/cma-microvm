# Feature Specification: Launcher Container Image & CDK IaC

**Feature Branch**: `001-launcher-container-cdk—launcher-image-cdk`

**Created**: 2026-07-06

**Status**: Draft

**Input**: User description: "Set up this repo as a full Python implementation of CMA and MicroVM — start with packaging the launcher as a Lambda container image (FastAPI + Mangum), fully use CDK to generate the deploy template (the launcher is strictly a Docker Image), use a Justfile to automate run/test/build/deploy, reorganize the repo as needed to accommodate the launcher and the worker, then focus on implementing the launcher as discussed."

## Scope (this cycle vs. later)

**In scope** (this cycle): reorganize the repo to accommodate a Python launcher and the (still-TypeScript) worker; package the launcher as an OCI container image that runs both locally (uvicorn, via Docker Compose) and in AWS Lambda (via Mangum); implement the CDK control plane at `utils/cdk/` reproducing the current SAM stack; add a Justfile automating run/test/build/deploy; implement and test the launcher control flow.

**Out of scope** (follow-up cycle): porting the in-MicroVM worker from TypeScript to Python. The repo reorganization MUST accommodate a future worker port but MUST NOT port or alter the worker this cycle.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Run the launcher locally without AWS (Priority: P1)

As a developer, I want to bring up the launcher with a single command in
Docker Compose and exercise the full webhook control flow (signature
verification → parse → idempotency → rate limit → dispatch) against a stub
MicroVM, with no AWS account or credentials, so I can develop and test the
control plane offline with dev/prod parity.

**Why this priority**: enables every other story and satisfies the
constitution's "run locally + replicate in Docker Compose" principle. Without
local parity, every change requires an AWS deploy to validate.

**Independent Test**: `just run-local` starts the launcher; sending a signed
webhook request returns the dispatch result with a stubbed `microvm_id`, and
an unsigned request returns 401. Verifiable without any AWS resource.

**Acceptance Scenarios**:

1. **Given** the launcher is running locally via Compose with a stub MicroVM
   client, **When** a developer sends a valid signed `session.status_run_started`
   webhook, **Then** the launcher returns 200 with a stub `microvm_id` and
   records the dispatch.
2. **Given** the launcher is running locally, **When** a developer sends an
   unsigned or tampered webhook, **Then** the launcher returns 401 before any
   dispatch occurs.
3. **Given** the same webhook event id is delivered twice concurrently,
   **When** both are processed, **Then** exactly one dispatch occurs.
4. **Given** the local run has no idempotency table configured, **When** a
   webhook is processed, **Then** the launcher proceeds without the
   DynamoDB-backed dedupe wrapper (degraded, by design, for local mode).

---

### User Story 2 - Deploy the control plane via CDK with a container-image Lambda (Priority: P1)

As an operator, I want to deploy the entire control plane from a CDK app at
`utils/cdk/` such that the launcher runs as a Lambda container image, so the
deploy path is reproducible, testable infrastructure that replaces the SAM
template with parity.

**Why this priority**: CDK is the mandated IaC and the deploy path must exist
for the launcher to run in AWS.

**Independent Test**: `cdk synth` produces a CloudFormation template whose
resources and stack outputs match the current SAM `template.yaml`; `cdk deploy`
produces a working webhook endpoint that launches a MicroVM on a real webhook.

**Acceptance Scenarios**:

1. **Given** the CDK app, **When** `cdk synth` runs, **Then** the synthesized
   template contains every resource currently in `template.yaml` (Lambda,
   API Gateway REST, WAFv2 WebACL + logging + association, DynamoDB
   idempotency table, two Secrets Manager secrets, MicroVM execution role,
   build role, S3 artifact bucket) with least-privilege IAM.
2. **Given** the synthesized template, **When** compared to the SAM output,
   **Then** the stack outputs (`WebhookUrl`, `EnvironmentKeySecretArn`,
   `SigningSecretArn`, `BuildRoleArn`, `MicroVmExecutionRoleArn`,
   `ArtifactBucketName`) are present and equivalent.
3. **Given** a deployed CDK stack with populated secrets and a built MicroVM
   image, **When** a real `session.status_run_started` webhook arrives,
   **Then** the launcher container image verifies the signature and launches
   one MicroVM (the existing end-to-end verify flow still passes).

---

### User Story 3 - One-command repo automation (Priority: P2)

As a contributor, I want a Justfile that wraps every common workflow — install,
lint, test, build the launcher image, run it locally, synthesize and deploy
CDK, build the MicroVM image, and verify — so I never run multi-step shell by
hand.

**Why this priority**: automation is the constitution's reproducibility lever
and de-risks the deploy/build stories.

**Independent Test**: each recipe executes its full flow with a single
`just <recipe>` and exits non-zero on failure.

**Acceptance Scenarios**:

1. **Given** the Justfile, **When** a contributor runs `just test`, **Then**
   the launcher behavioral tests run and pass (or report failures).
2. **Given** the Justfile, **When** a contributor runs `just run-local`,
   **Then** the launcher starts in Docker Compose ready to receive webhooks.
3. **Given** the Justfile, **When** a contributor runs `just cdk-synth`, **Then**
   CDK synthesizes a valid template.

---

### User Story 4 - Navigate a reorganized, launcher-and-worker-friendly repo (Priority: P2)

As a contributor, I want the repository laid out so the Python launcher is a
first-class package with its own container Dockerfile and FastAPI entrypoint,
the CDK lives under `utils/cdk/`, and the TypeScript worker remains in place and
untouched — so the structure reflects the Python-first direction without
breaking the worker or the existing build script.

**Why this priority**: structural clarity prevents the launcher, worker, and
IaC from entangling as both grow.

**Independent Test**: the existing `src/scripts/build-image.sh` still succeeds
against the (moved or preserved) worker source, and `just` recipes target the
new launcher paths.

**Acceptance Scenarios**:

1. **Given** the reorganized repo, **When** a contributor inspects the tree,
   **Then** the launcher Python package, its Dockerfile, the CDK app, and the
   worker are in clearly separated locations.
2. **Given** the reorganized repo, **When** `just build-microvm-image` runs,
   **Then** the existing image build still succeeds (worker source reachable).

---

### User Story 5 - CI builds the launcher container image (Priority: P3)

As a maintainer, I want CI to build the launcher container image and run the
test suite on every change, so the image is the reproducible artifact behind
every cloud-provider deploy.

**Why this priority**: the constitution requires CI that builds the image as
the base for cloud-provider deploys; this cycle delivers a minimal CI, with a
full multi-cloud matrix as a follow-up.

**Independent Test**: on push, CI builds the image and runs tests; a failing
test or broken build fails the pipeline.

**Acceptance Scenarios**:

1. **Given** a pull request, **When** CI runs, **Then** the launcher image
   builds and the behavioral tests pass.
2. **Given** a main commit, **When** CI runs, **Then** a container image
   artifact is produced and tagged.

---

### Edge Cases

- What happens when Anthropic delivers the same webhook event id concurrently
  or as a retry? → deduped to exactly one MicroVM launch (DynamoDB in AWS;
  acknowledged-degraded locally without the table).
- What happens when the webhook signature is invalid or the delivery is stale?
  → 401 before any launch.
- What happens when the RunMicrovm rate limit (5 TPS) is exceeded? → the token
  bucket blocks until a token is available (single-instance; multi-replica
  shared limiting is out of scope since prod is a single Lambda).
- What happens when `IDEMPOTENCY_TABLE` is unset (local)? → the idempotency
  wrapper is skipped and the executor runs unwrapped.
- What happens if the run-hook payload construction tries to include a secret?
  → the payload builder's forbidden-key guard rejects it (credential
  boundary invariant, asserted by a test).
- What happens on a malformed (non-`session.status_run_started`) event? →
  200 "ignored" so Anthropic does not retry.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The launcher MUST respond to `POST /webhook` with 401 when
  signature verification fails, and 200 when it passes and the event is handled
  or ignored, preserving the current behavior contract.
- **FR-002**: The launcher MUST dedupe by webhook event id so exactly one
  MicroVM is launched per event across retried and concurrent deliveries
  (DynamoDB-backed in AWS; skipped-by-design locally without the table).
- **FR-003**: The launcher MUST enforce the RunMicrovm 5 TPS rate limit via a
  token bucket before each launch.
- **FR-004**: The launcher MUST pass only a *reference* to the environment-key
  secret into the MicroVM; the organization API key and the environment key
  MUST never appear on AWS compute or in the run-hook payload. This invariant
  MUST be asserted by a test.
- **FR-005**: The launcher MUST be packaged as a single OCI container image
  that runs in AWS Lambda (event-handled via the ASGI adapter) and locally as
  a normal ASGI server in Docker Compose — same image, two entry modes.
- **FR-006**: A stub MicroVM client MUST be injectable so the local control
  flow can be exercised without calling the real `lambda-microvms` service.
- **FR-007**: The CDK app MUST reproduce every resource and least-privilege
  IAM statement currently in `template.yaml`, including the WAFv2 WebACL,
  its logging configuration, and its per-stage association, and the DynamoDB
  idempotency table with TTL.
- **FR-008**: The CDK app MUST package the launcher as a container-image Lambda
  and expose stack outputs equivalent to the current SAM outputs.
- **FR-009**: The Justfile MUST provide recipes for: dependency install,
  lint/format, tests, launcher image build, local run (Docker Compose), CDK
  synth, CDK deploy, MicroVM image build (wrapping the existing script), and
  operator verify (wrapping the existing script).
- **FR-010**: The repo MUST be reorganized so the launcher is a Python package
  with a container Dockerfile and ASGI entrypoint, the CDK app lives at
  `utils/cdk/`, and the TypeScript worker stays in place and unmodified this
  cycle; existing paths used by `build-image.sh` MUST remain valid (or be
  updated in lockstep) so the image build still succeeds.
- **FR-011**: Python dependencies MUST be managed with UV (`uv add`); the
  launcher MUST use Loguru for logging, Pydantic-settings for configuration,
  and ruff for lint/format, per the constitution.
- **FR-012**: The launcher control flow (signature verification, event
  parsing, idempotency, rate limiting, payload boundary) MUST be covered by
  tests that pass before the feature PR merges (TDD, applied at implementation
  and enforced at the final PR).

### Key Entities *(include if feature involves data)*

- **WebhookEvent**: the parsed Anthropic webhook delivery (event_id, data_type,
  session_id). Unchanged from the current implementation.
- **LauncherConfig**: launcher configuration loaded from the environment via
  Pydantic-settings (environment id, image identifier, secret ARNs, region,
  rate limit, max lifetime).
- **RunHookDispatch**: the non-secret per-session dispatch blob (session id,
  environment id, region, environment-key secret reference). Credential
  boundary enforced here.
- **ControlPlaneStack**: the CDK construct tree representing the deployable
  control plane (Lambda, API, WAF, DynamoDB, secrets, roles, bucket).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A developer can start the launcher locally with a single
  `just run-local` and observe a full signed-webhook → dispatch → stub-launch
  cycle in under 2 minutes, with no AWS credentials.
- **SC-002**: `cdk synth` output is resource-for-resource and output-for-output
  equivalent to the current SAM `template.yaml` (parity verified by diff), so
  the existing README operator workflow works unchanged against the CDK deploy.
- **SC-003**: The launcher container image passes the same behavioral test
  suite when run locally (ASGI server) and when invoked as a Lambda (container
  image), confirming dev/prod parity.
- **SC-004**: All launcher behavioral tests pass, and a dedicated test asserts
  the credential-boundary invariant (no org key or environment key in the
  run-hook payload or on compute).
- **SC-005**: Every common workflow (lint, test, build image, run local,
  synth, deploy, build MicroVM image, verify) is invocable as a single
  `just <recipe>` with no manual multi-step shell.

## Assumptions

- **CDK language and location**: CDK is written in Python (UV-managed) at
  `utils/cdk/`, per the constitution's Python-first stack. (Go is also
  supported by the helpers but Python is chosen for repo consistency.)
- **ASGI/Lambda bridge**: FastAPI + Mangum is the bridge; uvicorn serves the
  same app locally. These are mandated by the GOAL.
- **Worker is not ported this cycle**: the in-MicroVM worker remains
  TypeScript; reorganization accommodates a future Python port but does not
  perform it. A separate follow-up spec will cover the worker port (the
  Anthropic Python SDK has first-party `EnvironmentWorker`/`WorkPoller`
  parity, confirmed via web search).
- **SAM → CDK transition**: `template.yaml` is retained during CDK parity
  verification; CDK becomes canonical once parity is confirmed, and SAM is
  removed in a follow-up cleanup PR (not this cycle).
- **Local mode uses a stub client**: real `RunMicrovm` only happens in AWS; the
  injected `MicroVmClient` Protocol already supports a stub, so local Docker
  Compose exercises control flow, not real VM launches.
- **Pre-commit + Rust validator**: a pre-commit configuration wired to a
  Rust-backed Python validator is included as part of repo automation, per
  the constitution.
- **CI scope**: this cycle delivers a minimal CI that builds the image and
  runs tests; a full multi-cloud-provider deploy matrix is a follow-up.
- **Existing pure launcher core is reused**: the current `Launcher` class is
  already decoupled from AWS (injected client + swappable executor), so the
  container-image work is a repackaging + ASGI adapter, not a rewrite.