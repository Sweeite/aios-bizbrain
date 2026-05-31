from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from engine.spine.types import (
    Confidence, MemoryRecord, MemoryStore, Scope, ScopeLevel,
)


@dataclass
class ConsolidationResult:
    promoted: list[MemoryRecord] = field(default_factory=list)
    superseded: list[MemoryRecord] = field(default_factory=list)


class Consolidator:
    def __init__(self, promotion_threshold: int = 3) -> None:
        self._threshold = promotion_threshold

    def consolidate(
        self,
        entity_ref: str,
        pattern_key: str,
        records: list[MemoryRecord],
        now: datetime,
    ) -> ConsolidationResult:
        if len(records) < self._threshold:
            return ConsolidationResult()

        days_values = [
            r.payload["days_late"]
            for r in records
            if "days_late" in r.payload
        ]
        avg_days = sum(days_values) / len(days_values) if days_values else 0.0

        promoted = MemoryRecord(
            store=MemoryStore.entity,
            payload={
                "pattern_key": pattern_key,
                "observation_count": len(records),
                "summary": f"pays ~{round(avg_days)} days late",
                "avg_days_late": avg_days,
            },
            provenance=f"consolidation/{pattern_key}",
            temporal_validity={"as_of": now.isoformat(), "lifespan_days": 365},
            scope=records[0].scope,
            confidence=Confidence.inferred,
        )

        for r in records:
            object.__setattr__(r, "superseded_at", now)

        return ConsolidationResult(promoted=[promoted], superseded=list(records))

    def summarize(
        self,
        entity_ref: str,
        since: datetime,
        records: list[MemoryRecord],
        now: datetime,
    ) -> MemoryRecord:
        since_iso = since.isoformat()
        filtered = [
            r for r in records
            if r.temporal_validity.get("as_of", "") >= since_iso
        ]
        return MemoryRecord(
            store=MemoryStore.episodic,
            payload={
                "digest": True,
                "entity_ref": entity_ref,
                "record_count": len(filtered),
                "since": since_iso,
            },
            provenance="consolidation/digest",
            temporal_validity={"as_of": now.isoformat(), "lifespan_days": 30},
            scope=Scope(level=ScopeLevel.entity, entity_ref=entity_ref),
            confidence=Confidence.inferred,
        )
