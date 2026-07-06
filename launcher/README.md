# claude-microvm-launcher

The launcher: a FastAPI + Mangum app packaged as an AWS Lambda **container
image**. One OCI image runs two ways — under `uvicorn` locally and under Mangum
in AWS — preserving dev/prod parity (constitution Factor X).

## Run

```bash
just sync          # uv sync (install deps) — run from the repo root
just run-local     # uvicorn on :8000 with the stub MicroVM client (no AWS)
just test          # pytest
just lint          # ruff
```

The Lambda container image is built from the repo root (build context) using
[`../container/Dockerfile`](../container/Dockerfile); the control plane that
deploys it is defined in CDK at [`../utils/cdk/`](../utils/cdk/).

## Layout

```
launcher/
├── pyproject.toml          # UV project (runtime + dev deps)
├── uv.lock
├── src/launcher/           # the package: app.py, launcher.py, config.py, shared/
├── scripts/                # operator-side: verify.py, build-image.sh
└── tests/                  # contract / integration / unit
```

See the repo root [`README.md`](../README.md) and [`CLAUDE.md`](../CLAUDE.md)
for the full architecture, the credential boundary, and the control-plane
request flow.