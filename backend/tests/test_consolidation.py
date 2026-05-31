"""
Slice 10: Consolidation + reconciliation — consolidation half.
"""
import pytest
from datetime import datetime, timezone

from engine.spine.types import (
    Confidence, MemoryRecord, MemoryStore, Scope, ScopeLevel,
)

NOW = datetime(2025, 3, 2, 0, 0, tzinfo=timezone.utc)
ENTITY = "client-vertex-002"
PATTERN = "invoice.paid_late"


def _paid_late_records(n: int) -> list[MemoryRecord]:
    scope = Scope(level=ScopeLevel.entity, entity_ref=ENTITY)
    return [
        MemoryRecord(
            store=MemoryStore.episodic,
            payload={"event_type": PATTERN, "days_late": 25 + i},
            provenance=f"quickbooks:qb-inv-{i:03d}",
            temporal_validity={"as_of": "2025-02-01", "lifespan_days": 365},
            scope=scope,
            confidence=Confidence.observed,
        )
        for i in range(n)
    ]


# ---------------------------------------------------------------------------
# Consolidator
# ---------------------------------------------------------------------------

class TestConsolidator:
    def test_ten_records_promote_to_one_entity_fact(self):
        from engine.consolidation.consolidator import Consolidator

        records = _paid_late_records(10)
        result = Consolidator().consolidate(ENTITY, PATTERN, records, NOW)

        assert len(result.promoted) == 1
        assert result.promoted[0].store == MemoryStore.entity

    def test_promoted_fact_carries_correct_fields(self):
        from engine.consolidation.consolidator import Consolidator

        records = _paid_late_records(10)
        fact = Consolidator().consolidate(ENTITY, PATTERN, records, NOW).promoted[0]

        assert "consolidation" in fact.provenance
        assert fact.confidence == Confidence.inferred
        assert fact.scope.entity_ref == ENTITY
        assert fact.payload["observation_count"] == 10
        assert fact.payload["pattern_key"] == PATTERN

    def test_originals_marked_superseded_not_deleted(self):
        from engine.consolidation.consolidator import Consolidator

        records = _paid_late_records(10)
        result = Consolidator().consolidate(ENTITY, PATTERN, records, NOW)

        assert len(result.superseded) == 10
        assert all(r.superseded_at == NOW for r in result.superseded)

    def test_below_threshold_no_promotion(self):
        from engine.consolidation.consolidator import Consolidator

        records = _paid_late_records(2)
        result = Consolidator(promotion_threshold=3).consolidate(ENTITY, PATTERN, records, NOW)

        assert result.promoted == []
        assert result.superseded == []

    def test_summarize_produces_digest_record(self):
        from engine.consolidation.consolidator import Consolidator

        since = datetime(2025, 1, 1, tzinfo=timezone.utc)
        records = _paid_late_records(5)
        digest = Consolidator().summarize(ENTITY, since, records, NOW)

        assert digest.store == MemoryStore.episodic
        assert digest.payload["digest"] is True
        assert digest.payload["record_count"] == 5


# ---------------------------------------------------------------------------
# Celery task
# ---------------------------------------------------------------------------

class TestConsolidationTask:
    def test_task_registered_with_celery_app(self):
        from engine.worker.celery_app import celery_app
        from engine.worker import tasks  # noqa: F401

        assert "engine.worker.tasks.consolidation.consolidate_memory" in celery_app.tasks

    def test_task_returns_promoted_and_superseded_counts(self):
        from engine.worker.tasks.consolidation import consolidate_memory

        records_payload = [
            {
                "store": "episodic",
                "payload": {"event_type": PATTERN, "days_late": 25 + i},
                "provenance": f"quickbooks:qb-inv-{i:03d}",
                "temporal_validity": {"as_of": "2025-02-01", "lifespan_days": 365},
                "scope": {"level": "entity", "entity_ref": ENTITY},
                "confidence": "observed",
            }
            for i in range(10)
        ]
        result = consolidate_memory.apply(args=[ENTITY, PATTERN, records_payload])

        assert result.successful()
        assert result.result["promoted"] == 1
        assert result.result["superseded"] == 10
