"""
Slice 3: Celery worker + reflection hook tests.
"""
import logging
import pytest
from unittest.mock import MagicMock
from datetime import datetime, timezone

from engine.spine.types import BusinessEvent, Confidence, Scope, ScopeLevel
from engine.ingestion.entity_resolver import EntityResolver, ResolvedEvent


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def deal_event():
    return BusinessEvent(
        id="hs-deal-99-stage-changed-2025-03-01",
        source_system="hubspot",
        event_type="deal.stage_changed",
        timestamp=datetime(2025, 3, 1, 9, 0, tzinfo=timezone.utc),
        actor="hubspot-webhook",
        entities=["client-northpath-001"],
        raw_ref="hs-deal-99",
        body={"deal_name": "Northpath Q3 Audit", "to_stage": "Proposal", "days_in_stage": 21},
    )


@pytest.fixture
def resolved_observed(deal_event):
    return EntityResolver(
        known_entities={"client-northpath-001": "client"}
    ).resolve(deal_event)


@pytest.fixture
def resolved_review(deal_event):
    return EntityResolver(known_entities={}).resolve(deal_event)


# ---------------------------------------------------------------------------
# Celery app
# ---------------------------------------------------------------------------

class TestCeleryApp:
    def test_celery_app_is_importable_with_redis_broker(self):
        from engine.worker.celery_app import celery_app
        assert "redis" in celery_app.conf.broker_url


# ---------------------------------------------------------------------------
# Reflection task
# ---------------------------------------------------------------------------

class TestReflectionTask:
    def test_task_is_registered_with_celery_app(self):
        from engine.worker.celery_app import celery_app
        from engine.worker import tasks  # noqa: F401 — side-effect: register tasks
        assert "engine.worker.tasks.reflection.reflect_on_memory_write" in celery_app.tasks

    def test_task_runs_and_returns_successfully(self):
        from engine.worker.tasks.reflection import reflect_on_memory_write
        result = reflect_on_memory_write.apply(
            args=["evt-test-001", "hubspot", "client-northpath-001"]
        )
        assert result.successful()

    def test_task_logs_event_id_when_fired(self, caplog):
        from engine.worker.tasks.reflection import reflect_on_memory_write
        with caplog.at_level(logging.INFO, logger="engine.worker.tasks.reflection"):
            reflect_on_memory_write.apply(
                args=["evt-test-001", "hubspot", "client-northpath-001"]
            )
        assert "evt-test-001" in caplog.text


# ---------------------------------------------------------------------------
# MemoryWriter on_write callback
# ---------------------------------------------------------------------------

class TestMemoryWriterHook:
    def test_on_write_called_after_successful_write(self, resolved_observed):
        from engine.ingestion.memory_writer import MemoryWriter
        hook = MagicMock()
        writer = MemoryWriter(on_write=hook)
        record = writer.write(resolved_observed)
        assert record is not None
        hook.assert_called_once_with(
            resolved_observed.event.id,
            resolved_observed.event.source_system,
            resolved_observed.scope.entity_ref,
        )

    def test_on_write_not_called_on_duplicate_write(self, resolved_observed):
        from engine.ingestion.memory_writer import MemoryWriter
        hook = MagicMock()
        writer = MemoryWriter(on_write=hook)
        writer.write(resolved_observed)
        writer.write(resolved_observed)  # duplicate — should return None
        hook.assert_called_once()

    def test_on_write_not_called_when_routed_to_review(self, resolved_review):
        from engine.ingestion.memory_writer import MemoryWriter
        hook = MagicMock()
        writer = MemoryWriter(on_write=hook)
        result = writer.write(resolved_review)
        assert result is None
        hook.assert_not_called()

    def test_on_write_is_optional_no_error_without_hook(self, resolved_observed):
        from engine.ingestion.memory_writer import MemoryWriter
        writer = MemoryWriter()  # no on_write
        record = writer.write(resolved_observed)
        assert record is not None
