# Quickstart: Launcher Container Image & CDK IaC

Phase 1 output — a runnable validation guide. Implementation detail belongs in
`tasks.md`. See [spec.md](../spec.md) for requirements and
[contracts/webhook.md](../contracts/webhook.md) for the HTTP contract.

## Prerequisites

- UV installed (`curl -LsSf https://astral.sh/uv/install.sh | sh`)
- Docker + Docker Compose
- `just` (command runner)
- For AWS deploys: AWS CLI v2+ with the `lambda-microvms` service model, CDK CLI
  (`npm i -g aws-cdk`), and an Anthropic agent + `self_hosted` environment.

## Local run (no AWS) — validates US1

```bash
just install        # uv sync for the launcher project
just run-local      # docker compose up: launcher + (optional) DynamoDB Local
```

Then exercise the webhook:

```bash
# valid signed request (use the verify/stub helper) → 200 with stub microvm_id
# unsigned request → 401
just test           # runs the behavioral suite incl. the local flow
```

Expected: a signed `session.status_run_started` returns `200 {microvm_id,
session_id}`; an unsigned/tampered request returns `401` before any dispatch;
duplicate event ids resolve to a single dispatch.

## CDK deploy (AWS) — validates US2

```bash
just cdk-synth      # utils/cdk: cdk synth → CloudFormation template
                    # diff against the SAM-deployed stack for parity
just cdk-deploy -- AnthropicEnvironmentId=env_...   # cdk deploy
```

Populate secrets (out-of-band, operator-only) and build the MicroVM image:

```bash
aws secretsmanager put-secret-value --secret-id <EnvironmentKeySecretArn> --secret-string "<env-key>"
aws secretsmanager put-secret-value --secret-id <SigningSecretArn>        --secret-string "<whsec_...>"
just build-image    # wraps src/scripts/build-image.sh
```

## End-to-end verify (operator-side) — validates US2 acceptance 3

```bash
export ANTHROPIC_API_KEY="sk-ant-..." ANTHROPIC_ENVIRONMENT_ID="env_..." AGENT_ID="agent_..."
just verify         # wraps src/scripts/verify.py --create
aws lambda-microvms list-microvms --image-identifier <image>
```

Expected: a real webhook triggers the container-image Lambda, which verifies the
signature and launches one MicroVM; the MicroVM handles the session and exits.

## Automation — validates US3

```bash
just lint           # ruff check + format
just test           # pytest (unit + integration + contract)
just build-launcher # build the launcher container image
just run-local      # compose up
just cdk-synth      # CDK synth
just cdk-deploy     # CDK deploy
just build-image    # MicroVM image (wraps build-image.sh)
just verify         # end-to-end verify (wraps verify.py)
```

## Validation outcomes (maps to Success Criteria)

- **SC-001**: `just run-local` + one signed request shows a full
  webhook→dispatch→stub-launch cycle in under 2 minutes, no AWS credentials.
- **SC-002**: `just cdk-synth` output is resource/output-equivalent to the
  current SAM stack (parity diff passes).
- **SC-003**: the behavioral suite passes both under uvicorn (local) and as a
  Lambda container image (Mangum).
- **SC-004**: all behavioral tests pass, including the credential-boundary test.
- **SC-005**: every workflow above is a single `just <recipe>`.