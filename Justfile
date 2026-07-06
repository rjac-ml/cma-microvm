# Justfile — automation for the launcher, worker, and CDK control plane
# (constitution: reproducible envs & automation).
#
# Run any recipe with `just <recipe>` from the repo root. The launcher and
# worker are independent UV projects (launcher/, worker/); CDK lives in
# utils/cdk/. AWS/deploy recipes (cdk-deploy, docker push) are delegated to the
# operator; local recipes (sync, test, lint, synth) run here.

default:
    @just --list

# --- Launcher (Python) ---

sync:
    cd launcher && uv sync

lock:
    cd launcher && uv lock

# Local run: uvicorn + stub MicroVM client, no AWS.
run-local:
    cd launcher && LAUNCHER_USE_STUB=1 uv run uvicorn launcher.app:app --reload --host 0.0.0.0 --port 8000

test:
    cd launcher && uv run pytest -q

test-one target:
    cd launcher && uv run pytest -q {{target}}

lint:
    cd launcher && uv run ruff check .

format:
    cd launcher && uv run ruff format .

format-check:
    cd launcher && uv run ruff format --check .

lint-fix:
    cd launcher && uv run ruff check --fix .
    cd launcher && uv run ruff format .

# Full local verification gate (launcher).
verify: lint format-check test
    @echo "verify OK"

# --- Worker (Python port scaffold) ---

worker-sync:
    cd worker && uv sync

worker-test:
    cd worker && uv run pytest -q

worker-lint:
    cd worker && uv run ruff check .

# --- Container (builds the Lambda image; same image deploys to AWS) ---

docker-build:
    docker build -t claude-microvm-launcher -f container/Dockerfile .

docker-up:
    docker compose up --build

docker-down:
    docker compose down

# --- CDK control plane (utils/cdk) ---

cdk-sync:
    cd utils/cdk && uv sync

# Synthesize the control-plane template without Docker (structural view).
# The real OCI image is built only on deploy (CDK_BUILD_IMAGE=1 by default).
cdk-synth:
    cd utils/cdk && CDK_BUILD_IMAGE=0 uv run python app.py

cdk-test:
    cd utils/cdk && PATH="$$HOME/.asdf/installs/nodejs/22.1.0/bin:$$PATH" uv run pytest -q

# Deploys to AWS — run this yourself. Needs Docker, the `cdk` CLI (npm i -g aws-cdk),
# AWS credentials, and a bootstrapped environment.
cdk-deploy:
    cd utils/cdk && uv run cdk deploy --require-approval never

cdk-destroy:
    cd utils/cdk && uv run cdk destroy --force