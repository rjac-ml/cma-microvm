"""In-MicroVM lifecycle-hook worker (Python port — scaffold only).

The current, running worker is the TypeScript HTTP lifecycle-hook server at
``src/microvm-image/`` (``worker/worker.mjs``). Porting it to Python — using the
Anthropic SDK's first-party managed-agents ``EnvironmentWorker`` / work-poller
helpers (confirmed to exist in the Python SDK; see ``KNOWLEDGE.md``) — is a
separate, out-of-scope follow-up spec. This package is a placeholder so the repo
layout is ready (``launcher/``, ``worker/``, ``utils/cdk/`` as independent UV
projects).
"""

__version__ = "0.0.0"
