from collections.abc import Callable

from engine.ingestion.entity_resolver import ResolvedEvent
from engine.spine.types import Confidence, MemoryRecord, MemoryStore, Scope, ScopeLevel


class WriteGuardrailError(Exception):
    pass


class MemoryWriter:
    def __init__(
        self,
        live_owned_fields: frozenset[str] = frozenset(),
        on_write: Callable[[str, str, str | None], None] | None = None,
    ):
        self._live_owned = live_owned_fields
        self._on_write = on_write
        self._episodic: list[MemoryRecord] = []
        self._review_queue: list[ResolvedEvent] = []
        self._written: set[tuple[str, str]] = set()

    def write(self, resolved: ResolvedEvent) -> MemoryRecord | None:
        event = resolved.event

        # Guardrail 1: no live-owned identity fields in the payload
        overlap = self._live_owned & event.body.keys()
        if overlap:
            raise WriteGuardrailError(
                f"Payload contains live-owned fields: {overlap}"
            )

        # Guardrail 2: idempotent — no duplicate writes
        dedup_key = (event.id, event.source_system)
        if dedup_key in self._written:
            return None

        # Guardrail 3: low-confidence events go to review queue, not episodic store
        if resolved.routed_to_review:
            self._review_queue.append(resolved)
            return None

        record = MemoryRecord(
            store=MemoryStore.episodic,
            payload=event.body | {
                "source_event_id": event.id,
                "event_type": event.event_type,
            },
            provenance=f"{event.source_system}:{event.id}",
            temporal_validity={
                "as_of": event.timestamp.isoformat(),
                "lifespan_days": 365,
            },
            scope=resolved.scope,
            confidence=resolved.confidence,
        )
        self._episodic.append(record)
        self._written.add(dedup_key)
        if self._on_write is not None:
            self._on_write(event.id, event.source_system, resolved.scope.entity_ref)
        return record

    @property
    def review_queue(self) -> list[ResolvedEvent]:
        return list(self._review_queue)

    def recall(self, entity_ref: str, caller_scope: Scope) -> list[MemoryRecord]:
        results = []
        for record in self._episodic:
            scope = record.scope
            if scope.level == ScopeLevel.entity and scope.entity_ref == entity_ref:
                if _caller_can_read(caller_scope, scope):
                    results.append(record)
        return results


def _caller_can_read(caller: Scope, record_scope: Scope) -> bool:
    if caller.level == ScopeLevel.org:
        return True
    if caller.level == ScopeLevel.entity:
        return caller.entity_ref == record_scope.entity_ref
    if caller.level == ScopeLevel.team:
        return caller.team_ref == record_scope.team_ref
    return False
