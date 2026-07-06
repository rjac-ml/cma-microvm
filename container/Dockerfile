# Lambda container image for the launcher.
#
# One image, dev/prod parity (constitution Factor X):
#   - Same ASGI app runs under uvicorn locally and under Mangum in AWS.
#   - Built on the official AWS Lambda Python base so compiled wheels
#     (pydantic-core, uvloop, ...) match the runtime ABI exactly.
#
# Build:  docker build -t claude-microvm-launcher -f container/Dockerfile .
#         (run from the repo root; .dockerignore limits the context to launcher/)
# Local: docker compose up   (compose overrides the entrypoint to run uvicorn)
# Deploy: pushed to ECR, referenced by the CDK DockerImageFunction construct.

FROM public.ecr.aws/lambda/python:3.12

COPY --from=ghcr.io/astral-sh/uv:0.11.3 /uv /usr/local/bin/uv

WORKDIR /app

# Reproducible, lock-driven install of runtime dependencies (no dev tools).
# The AWS Lambda Python base ships its interpreter at /var/lang/bin/python3.12
# (NOT /var/lang/python3.12/bin/python3.12) — pin it so uv builds an ABI-matched
# venv. boto3/botocore come from upstream (>= 1.43.40 ships lambda-microvms),
# so no vendored wheels are copied.
ENV UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_PYTHON=/var/lang/bin/python3.12 \
    UV_FROZEN=1

COPY launcher/pyproject.toml launcher/uv.lock ./

RUN uv sync --no-dev

# Place dependencies on the Lambda task root so they're importable at runtime,
# then add the application source as the `launcher` package.
RUN cp -R /opt/venv/lib/python3.12/site-packages/* "${LAMBDA_TASK_ROOT}/"

COPY launcher/src/launcher "${LAMBDA_TASK_ROOT}/launcher"

# Lambda entrypoint: the Mangum adapter wrapping the FastAPI app.
CMD [ "launcher.app.handler" ]