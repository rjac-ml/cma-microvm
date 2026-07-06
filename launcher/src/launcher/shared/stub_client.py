"""A stub ``MicroVmClient`` for local development and tests.

The launcher's ``MicroVmClient`` Protocol (see ``shared/microvm_client.py``) is
the seam that makes the control flow exercisable without AWS. In local Docker
Compose we cannot call the real ``lambda-microvms`` service, so this stub
returns a deterministic ``LaunchedMicroVm`` instead. It is selected when the
``LAUNCHER_USE_STUB`` environment variable is set (see ``make_client``).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from launcher.shared.microvm_client import LaunchedMicroVm


class StubMicroVmClient:
    """A ``MicroVmClient`` that never touches AWS."""

    def __init__(self, *, microvm_id: str = "stub-microvm-0001") -> None:
        self._microvm_id = microvm_id
        self.launches: list[dict[str, Any]] = []

    def launch_microvm(
        self,
        image_identifier: str,
        run_hook_payload: str | None = None,
        max_lifetime_seconds: int | None = None,
        execution_role_arn: str | None = None,
        idle_policy: Mapping[str, Any] | None = None,
        logging_config: Mapping[str, Any] | None = None,
        ingress_network_connectors: Sequence[str] | None = None,
        egress_network_connectors: Sequence[str] | None = None,
    ) -> LaunchedMicroVm:
        self.launches.append(
            {
                "image_identifier": image_identifier,
                "run_hook_payload": run_hook_payload,
                "max_lifetime_seconds": max_lifetime_seconds,
                "execution_role_arn": execution_role_arn,
            }
        )
        return LaunchedMicroVm(
            microvm_id=self._microvm_id,
            endpoint=f"http://stub.{self._microvm_id}.local",
        )
