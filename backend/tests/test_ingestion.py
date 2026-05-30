"""
Slice 2: Mock ingestion pipeline tests.
Tests describe observable behavior through public interfaces only.
"""
import pytest
from datetime import datetime, timezone

from engine.spine.types import BusinessEvent, Confidence, MemoryStore, Scope, ScopeLevel


# ---------------------------------------------------------------------------
# Shared fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def deal_stalled_event():
    return BusinessEvent(
        id="hs-deal-99-stage-changed-2025-03-01",
        source_system="hubspot",
        event_type="deal.stage_changed",
        timestamp=datetime(2025, 3, 1, 9, 0, tzinfo=timezone.utc),
        actor="hubspot-webhook",
        entities=["client-northpath-001"],
        raw_ref="hs-deal-99",
        body={
            "deal_name": "Northpath Q3 Audit",
            "from_stage": "Discovery",
            "to_stage": "Proposal",
            "days_in_stage": 21,
        },
    )


# ---------------------------------------------------------------------------
# Slice 1 — tracer bullet: HubSpot mock pulls a BusinessEvent
# ---------------------------------------------------------------------------

class TestHubSpotMockConnector:
    def test_pull_returns_business_event(self):
        from packs.consulting.connectors.hubspot_mock import HubSpotMockConnector

        connector = HubSpotMockConnector()
        events = connector.pull()

        assert len(events) == 1
        assert isinstance(events[0], BusinessEvent)

    def test_event_envelope_carries_required_fields(self):
        from packs.consulting.connectors.hubspot_mock import HubSpotMockConnector

        event = HubSpotMockConnector().pull()[0]

        assert event.id
        assert event.source_system == "hubspot"
        assert event.event_type == "deal.stage_changed"
        assert event.timestamp is not None
        assert event.actor
        assert len(event.entities) > 0
        assert event.raw_ref
        assert isinstance(event.body, dict)
        assert "deal_name" in event.body
        assert "to_stage" in event.body

    def test_connector_is_base_connector_and_has_source_system(self):
        from engine.ingestion.base_connector import BaseConnector
        from packs.consulting.connectors.hubspot_mock import HubSpotMockConnector

        connector = HubSpotMockConnector()
        assert isinstance(connector, BaseConnector)
        assert connector.source_system == "hubspot"


# ---------------------------------------------------------------------------
# Slice 4-6 — EntityResolver
# ---------------------------------------------------------------------------

class TestEntityResolver:
    def test_known_entity_resolves_to_observed_with_entity_scope(self, deal_stalled_event):
        from engine.ingestion.entity_resolver import EntityResolver

        resolver = EntityResolver(known_entities={"client-northpath-001": "client"})
        resolved = resolver.resolve(deal_stalled_event)

        assert resolved.confidence == Confidence.observed
        assert resolved.scope.level == ScopeLevel.entity
        assert resolved.scope.entity_ref == "client-northpath-001"
        assert resolved.routed_to_review is False

    def test_unknown_entity_routes_to_review_with_stated_once(self, deal_stalled_event):
        from engine.ingestion.entity_resolver import EntityResolver

        resolver = EntityResolver(known_entities={})
        resolved = resolver.resolve(deal_stalled_event)

        assert resolved.confidence == Confidence.stated_once
        assert resolved.routed_to_review is True

    def test_partial_known_entities_yield_inferred_confidence(self):
        from engine.ingestion.entity_resolver import EntityResolver

        event = BusinessEvent(
            id="evt-partial",
            source_system="hubspot",
            event_type="deal.stage_changed",
            timestamp=datetime(2025, 3, 1, tzinfo=timezone.utc),
            actor="hubspot-webhook",
            entities=["client-northpath-001", "contact-jane-doe"],
            raw_ref="hs-deal-100",
            body={},
        )
        resolver = EntityResolver(known_entities={"client-northpath-001": "client"})
        resolved = resolver.resolve(event)

        assert resolved.confidence == Confidence.inferred
        assert resolved.routed_to_review is False
        assert resolved.scope.entity_ref == "client-northpath-001"


# ---------------------------------------------------------------------------
# Slice 7-9 — MemoryWriter guardrails
# ---------------------------------------------------------------------------

class TestWriteGuardrails:
    def _resolved(self, body=None, entities=None, event_id="evt-guard-001",
                  confidence=Confidence.observed, routed=False):
        from engine.ingestion.entity_resolver import ResolvedEvent
        ev = BusinessEvent(
            id=event_id,
            source_system="hubspot",
            event_type="deal.stage_changed",
            timestamp=datetime(2025, 3, 1, tzinfo=timezone.utc),
            actor="hubspot-webhook",
            entities=entities or ["client-northpath-001"],
            raw_ref="hs-deal-99",
            body=body or {"to_stage": "Proposal"},
        )
        return ResolvedEvent(
            event=ev,
            scope=Scope(level=ScopeLevel.entity, entity_ref="client-northpath-001"),
            confidence=confidence,
            routed_to_review=routed,
        )

    def test_live_owned_field_raises_guardrail_error(self):
        from engine.ingestion.memory_writer import MemoryWriter, WriteGuardrailError

        writer = MemoryWriter(live_owned_fields=frozenset({"email", "company_name"}))
        resolved = self._resolved(body={"company_name": "Northpath", "to_stage": "Proposal"})

        with pytest.raises(WriteGuardrailError):
            writer.write(resolved)

    def test_duplicate_event_returns_none_on_second_write(self):
        from engine.ingestion.memory_writer import MemoryWriter

        writer = MemoryWriter()
        resolved = self._resolved()

        first = writer.write(resolved)
        second = writer.write(resolved)

        assert first is not None
        assert second is None

    def test_review_routed_event_goes_to_review_queue_not_episodic(self):
        from engine.ingestion.memory_writer import MemoryWriter

        writer = MemoryWriter()
        resolved = self._resolved(
            event_id="evt-low-conf",
            confidence=Confidence.stated_once,
            routed=True,
        )

        result = writer.write(resolved)

        assert result is None
        assert len(writer.review_queue) == 1
        assert writer.review_queue[0].event.id == "evt-low-conf"


# ---------------------------------------------------------------------------
# Slice 10 — episodic write stamps all four universal properties
# ---------------------------------------------------------------------------

class TestMemoryWriter:
    def test_valid_write_stamps_all_four_universal_properties(self, deal_stalled_event):
        from engine.ingestion.entity_resolver import EntityResolver, ResolvedEvent
        from engine.ingestion.memory_writer import MemoryWriter

        resolved = EntityResolver(
            known_entities={"client-northpath-001": "client"}
        ).resolve(deal_stalled_event)
        writer = MemoryWriter()
        record = writer.write(resolved)

        assert record is not None
        assert record.store == MemoryStore.episodic
        # provenance
        assert "hubspot" in record.provenance
        # temporal validity
        assert "as_of" in record.temporal_validity
        assert "lifespan_days" in record.temporal_validity
        # scope
        assert record.scope.level == ScopeLevel.entity
        assert record.scope.entity_ref == "client-northpath-001"
        # confidence
        assert record.confidence == Confidence.observed


# ---------------------------------------------------------------------------
# Slices 11-12 — recall() scope filtering
# ---------------------------------------------------------------------------

class TestRecall:
    def _written_writer(self, deal_stalled_event):
        from engine.ingestion.entity_resolver import EntityResolver
        from engine.ingestion.memory_writer import MemoryWriter

        resolved = EntityResolver(
            known_entities={"client-northpath-001": "client"}
        ).resolve(deal_stalled_event)
        writer = MemoryWriter()
        writer.write(resolved)
        return writer

    def test_recall_with_matching_entity_scope_returns_record(self, deal_stalled_event):
        writer = self._written_writer(deal_stalled_event)
        caller = Scope(level=ScopeLevel.entity, entity_ref="client-northpath-001")

        results = writer.recall("client-northpath-001", caller)

        assert len(results) == 1
        assert results[0].store == MemoryStore.episodic

    def test_recall_from_different_entity_scope_returns_empty(self, deal_stalled_event):
        writer = self._written_writer(deal_stalled_event)
        caller = Scope(level=ScopeLevel.entity, entity_ref="client-other-999")

        results = writer.recall("client-northpath-001", caller)

        assert results == []

    def test_recall_from_org_scope_returns_record(self, deal_stalled_event):
        writer = self._written_writer(deal_stalled_event)
        caller = Scope(level=ScopeLevel.org)

        results = writer.recall("client-northpath-001", caller)

        assert len(results) == 1


# ---------------------------------------------------------------------------
# Slice 13 — end-to-end ingestion pipeline
# ---------------------------------------------------------------------------

class TestIngestionPipeline:
    def test_deal_stalled_fixture_flows_to_episodic_memory(self):
        """Full path: connector → resolver → writer → recall."""
        from engine.ingestion.entity_resolver import EntityResolver
        from engine.ingestion.memory_writer import MemoryWriter
        from packs.consulting.connectors.hubspot_mock import HubSpotMockConnector

        events = HubSpotMockConnector().pull()
        resolver = EntityResolver(known_entities={"client-northpath-001": "client"})
        writer = MemoryWriter()

        for event in events:
            resolved = resolver.resolve(event)
            writer.write(resolved)

        caller = Scope(level=ScopeLevel.entity, entity_ref="client-northpath-001")
        records = writer.recall("client-northpath-001", caller)

        assert len(records) == 1
        record = records[0]
        assert record.store == MemoryStore.episodic
        assert record.confidence == Confidence.observed
        assert record.scope.entity_ref == "client-northpath-001"
        assert "Proposal" in record.payload.get("to_stage", "")
        assert record.temporal_validity["lifespan_days"] == 365
