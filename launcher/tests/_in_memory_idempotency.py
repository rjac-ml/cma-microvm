"""Minimal in-memory idempotency persistence layer for tests.

Mirrors the contract of ``DynamoDBPersistenceLayer`` closely enough to exercise
the dedupe path without DynamoDB Local. Not for production use.
"""

from __future__ import annotations

from aws_lambda_powertools.utilities.idempotency.exceptions import (
    IdempotencyItemAlreadyExistsError,
    IdempotencyItemNotFoundError,
)
from aws_lambda_powertools.utilities.idempotency.persistence.base import (
    BasePersistenceLayer,
)
from aws_lambda_powertools.utilities.idempotency.persistence.datarecord import (
    DataRecord,
)


class InMemoryPersistenceLayer(BasePersistenceLayer):
    """A ``BasePersistenceLayer`` backed by a plain dict."""

    def __init__(self) -> None:
        super().__init__()
        self._store: dict[str, DataRecord] = {}

    def _get_record(self, idempotency_key: str) -> DataRecord:
        record = self._store.get(idempotency_key)
        if record is None or record.is_expired:
            if record is not None:
                self._store.pop(idempotency_key, None)
            raise IdempotencyItemNotFoundError(idempotency_key)
        return record

    def _put_record(self, data_record: DataRecord) -> None:
        existing = self._store.get(data_record.idempotency_key)
        if existing is not None and not existing.is_expired:
            raise IdempotencyItemAlreadyExistsError(old_data_record=existing)
        self._store[data_record.idempotency_key] = data_record

    def _update_record(self, data_record: DataRecord) -> None:
        self._store[data_record.idempotency_key] = data_record

    def _delete_record(self, data_record: DataRecord) -> None:
        self._store.pop(data_record.idempotency_key, None)
