from __future__ import annotations

from engine.spine.types import AuditRecord


class ImmutableRecordError(Exception):
    pass


class InMemoryAuditStore:
    def __init__(self) -> None:
        self._records: dict[str, AuditRecord] = {}

    def save(self, record: AuditRecord) -> None:
        self._records[record.idempotency_key] = record

    def get(self, idempotency_key: str) -> AuditRecord | None:
        return self._records.get(idempotency_key)

    def update(self, *args, **kwargs) -> None:
        raise ImmutableRecordError("audit records are immutable")

    def delete(self, *args, **kwargs) -> None:
        raise ImmutableRecordError("audit records are immutable")
