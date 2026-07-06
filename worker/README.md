# cma-microvm-worker (scaffold)

In-MicroVM lifecycle-hook worker — **Python port scaffold**.

The current, running worker is the TypeScript HTTP lifecycle-hook server at
[`../src/microvm-image/`](../src/microvm-image/) (`worker/worker.mjs`). Porting
it to Python — using the Anthropic SDK's first-party managed-agents
`EnvironmentWorker` / work-poller helpers (confirmed to exist in the Python SDK;
see `KNOWLEDGE.md`) — is a **separate, out-of-scope follow-up spec** for a later
cycle. This project exists so the repo layout is ready (`launcher/`, `worker/`,
`utils/cdk/` as independent UV projects).

Run what's here:

```bash
cd worker
uv sync
uv run pytest -q
uv run ruff check .
```