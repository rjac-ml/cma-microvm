# Justfile — automation for the launcher (constitution: reproducible envs & automation).
#
# Run any recipe with `just <recipe>`. AWS/deploy recipes (cdk-deploy, docker push)
# are delegated to the operator; local recipes (sync, test, lint, synth) run here.

default:
    @just --list

# --- Python environment (UV) ---

sync:
    uv sync

lock:
    uv lock

# --- Local run (uvicorn, stub MicroVM client, no AWS) ---

run-local:
    LAUNCHER_USE_STUB=1 uv run uvicorn launcher.app:app --reload --host 0.0.0.0 --port 8000

# --- Quality & tests ---

test:
    uv run pytest -q

test-one target:
    uv run pytest -q {{target}}

lint:
    uv run ruff check .

format:
    uv run ruff format .

format-check:
    uv run ruff format --check .

lint-fix:
    uv run ruff check --fix .
    uv run ruff format .

# Full local verification gate.
verify: lint format-check test
    @echo "verify OK"

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