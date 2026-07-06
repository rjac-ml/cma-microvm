"""Core data types for the launcher.

``LauncherConfig`` now lives in ``launcher.config`` (Pydantic-settings); this
module keeps the parsed webhook event type.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class WebhookEvent:
    """A parsed Anthropic webhook event."""

    event_id: str
    data_type: str
    session_id: str

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> WebhookEvent:
        data = payload.get("data", {}) or {}
        return cls(
            event_id=payload.get("id", ""),
            data_type=payload.get("type", ""),
            session_id=data.get("id", ""),
        )
