from datetime import datetime, timezone

from engine.consolidation.consolidator import Consolidator
from engine.spine.types import (
    Confidence, MemoryRecord, MemoryStore, Scope, ScopeLevel,
)
from engine.worker.celery_app import celery_app


def _record_from_dict(d: dict) -> MemoryRecord:
    scope_d = d["scope"]
    return MemoryRecord(
        store=MemoryStore(d["store"]),
        payload=d["payload"],
        provenance=d["provenance"],
        temporal_validity=d["temporal_validity"],
        scope=Scope(
            level=ScopeLevel(scope_d["level"]),
            entity_ref=scope_d.get("entity_ref"),
            team_ref=scope_d.get("team_ref"),
            user_ref=scope_d.get("user_ref"),
        ),
        confidence=Confidence(d["confidence"]),
    )


@celery_app.task(name="engine.worker.tasks.consolidation.consolidate_memory")
def consolidate_memory(
    entity_ref: str,
    pattern_key: str,
    records_payload: list[dict],
) -> dict:
    records = [_record_from_dict(d) for d in records_payload]
    result = Consolidator().consolidate(entity_ref, pattern_key, records, datetime.now(tz=timezone.utc))
    return {"promoted": len(result.promoted), "superseded": len(result.superseded)}
