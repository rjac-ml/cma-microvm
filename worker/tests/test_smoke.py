"""Smoke test: the worker package imports (scaffold placeholder)."""

from __future__ import annotations

import worker


def test_worker_importable() -> None:
    """The scaffold package imports; real tests land with the Python port."""
    assert worker.__version__ == "0.0.0"
