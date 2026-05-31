"""
Slice 11: Full mock connector set — all 8 systems.
Tests verify behavior through public BaseConnector interface only.
"""
import pytest
from datetime import datetime, timezone

from engine.spine.types import BusinessEvent
from engine.ingestion.base_connector import BaseConnector


# ---------------------------------------------------------------------------
# Gmail
# ---------------------------------------------------------------------------

class TestGmailMockConnector:
    def test_pull_returns_business_events(self):
        from packs.consulting.connectors.gmail_mock import GmailMockConnector

        events = GmailMockConnector().pull()

        assert len(events) >= 1
        assert all(isinstance(e, BusinessEvent) for e in events)

    def test_event_envelope_is_correct(self):
        from packs.consulting.connectors.gmail_mock import GmailMockConnector

        events = GmailMockConnector().pull()
        source_systems = {e.source_system for e in events}
        event_types = {e.event_type for e in events}

        assert source_systems == {"gmail"}
        assert event_types >= {"email.received.significant"}
        for e in events:
            assert e.id
            assert e.timestamp is not None
            assert e.actor
            assert e.raw_ref
            assert isinstance(e.body, dict)

    def test_is_base_connector_with_source_system(self):
        from packs.consulting.connectors.gmail_mock import GmailMockConnector

        connector = GmailMockConnector()

        assert isinstance(connector, BaseConnector)
        assert connector.source_system == "gmail"


# ---------------------------------------------------------------------------
# Calendar
# ---------------------------------------------------------------------------

class TestCalendarMockConnector:
    def test_pull_returns_business_events(self):
        from packs.consulting.connectors.calendar_mock import CalendarMockConnector

        events = CalendarMockConnector().pull()

        assert len(events) >= 1
        assert all(isinstance(e, BusinessEvent) for e in events)

    def test_event_envelope_is_correct(self):
        from packs.consulting.connectors.calendar_mock import CalendarMockConnector

        events = CalendarMockConnector().pull()

        assert all(e.source_system == "calendar" for e in events)
        assert all(e.event_type == "meeting.occurred" for e in events)
        for e in events:
            assert e.id
            assert e.timestamp is not None
            assert e.actor
            assert e.raw_ref
            assert "title" in e.body
            assert "attendees" in e.body

    def test_is_base_connector_with_source_system(self):
        from packs.consulting.connectors.calendar_mock import CalendarMockConnector

        connector = CalendarMockConnector()

        assert isinstance(connector, BaseConnector)
        assert connector.source_system == "calendar"


# ---------------------------------------------------------------------------
# Asana
# ---------------------------------------------------------------------------

class TestAsanaMockConnector:
    def test_pull_returns_business_events(self):
        from packs.consulting.connectors.asana_mock import AsanaMockConnector

        events = AsanaMockConnector().pull()

        assert len(events) >= 1
        assert all(isinstance(e, BusinessEvent) for e in events)

    def test_event_envelope_is_correct(self):
        from packs.consulting.connectors.asana_mock import AsanaMockConnector

        events = AsanaMockConnector().pull()
        event_types = {e.event_type for e in events}

        assert all(e.source_system == "asana" for e in events)
        assert event_types >= {"task.completed", "due_date.slipped"}
        for e in events:
            assert e.id
            assert e.timestamp is not None
            assert e.actor
            assert e.raw_ref
            assert "task_name" in e.body

    def test_is_base_connector_with_source_system(self):
        from packs.consulting.connectors.asana_mock import AsanaMockConnector

        connector = AsanaMockConnector()

        assert isinstance(connector, BaseConnector)
        assert connector.source_system == "asana"


# ---------------------------------------------------------------------------
# Slack
# ---------------------------------------------------------------------------

class TestSlackMockConnector:
    def test_pull_returns_business_events(self):
        from packs.consulting.connectors.slack_mock import SlackMockConnector

        events = SlackMockConnector().pull()

        assert len(events) >= 1
        assert all(isinstance(e, BusinessEvent) for e in events)

    def test_event_envelope_is_correct(self):
        from packs.consulting.connectors.slack_mock import SlackMockConnector

        events = SlackMockConnector().pull()

        assert all(e.source_system == "slack" for e in events)
        assert all(e.event_type == "slack.decision_captured" for e in events)
        for e in events:
            assert e.id
            assert e.timestamp is not None
            assert e.actor
            assert e.raw_ref
            assert "decision" in e.body
            assert "channel" in e.body

    def test_is_base_connector_with_source_system(self):
        from packs.consulting.connectors.slack_mock import SlackMockConnector

        connector = SlackMockConnector()

        assert isinstance(connector, BaseConnector)
        assert connector.source_system == "slack"


# ---------------------------------------------------------------------------
# QuickBooks
# ---------------------------------------------------------------------------

class TestQuickBooksMockConnector:
    def test_pull_returns_business_events(self):
        from packs.consulting.connectors.quickbooks_mock import QuickBooksMockConnector

        events = QuickBooksMockConnector().pull()

        assert len(events) >= 1
        assert all(isinstance(e, BusinessEvent) for e in events)

    def test_event_envelope_is_correct(self):
        from packs.consulting.connectors.quickbooks_mock import QuickBooksMockConnector

        events = QuickBooksMockConnector().pull()
        event_types = {e.event_type for e in events}

        assert all(e.source_system == "quickbooks" for e in events)
        assert event_types >= {"invoice.issued", "invoice.paid"}
        for e in events:
            assert e.id
            assert e.timestamp is not None
            assert e.actor
            assert e.raw_ref
            assert "invoice_number" in e.body
            assert "amount_usd" in e.body

    def test_is_base_connector_with_source_system(self):
        from packs.consulting.connectors.quickbooks_mock import QuickBooksMockConnector

        connector = QuickBooksMockConnector()

        assert isinstance(connector, BaseConnector)
        assert connector.source_system == "quickbooks"


# ---------------------------------------------------------------------------
# Harvest
# ---------------------------------------------------------------------------

class TestHarvestMockConnector:
    def test_pull_returns_business_events(self):
        from packs.consulting.connectors.harvest_mock import HarvestMockConnector

        events = HarvestMockConnector().pull()

        assert len(events) >= 1
        assert all(isinstance(e, BusinessEvent) for e in events)

    def test_event_envelope_is_correct(self):
        from packs.consulting.connectors.harvest_mock import HarvestMockConnector

        events = HarvestMockConnector().pull()
        event_types = {e.event_type for e in events}

        assert all(e.source_system == "harvest" for e in events)
        assert event_types >= {"harvest.budget_threshold_crossed"}
        for e in events:
            assert e.id
            assert e.timestamp is not None
            assert e.actor
            assert e.raw_ref
            assert "engagement" in e.body
            assert "budget_usd" in e.body

    def test_is_base_connector_with_source_system(self):
        from packs.consulting.connectors.harvest_mock import HarvestMockConnector

        connector = HarvestMockConnector()

        assert isinstance(connector, BaseConnector)
        assert connector.source_system == "harvest"


# ---------------------------------------------------------------------------
# Zoom
# ---------------------------------------------------------------------------

class TestZoomMockConnector:
    def test_pull_returns_business_events(self):
        from packs.consulting.connectors.zoom_mock import ZoomMockConnector

        events = ZoomMockConnector().pull()

        assert len(events) >= 1
        assert all(isinstance(e, BusinessEvent) for e in events)

    def test_event_envelope_is_correct(self):
        from packs.consulting.connectors.zoom_mock import ZoomMockConnector

        events = ZoomMockConnector().pull()

        assert all(e.source_system == "zoom" for e in events)
        assert all(e.event_type == "zoom.meeting_ended" for e in events)
        for e in events:
            assert e.id
            assert e.timestamp is not None
            assert e.actor
            assert e.raw_ref
            assert "meeting_topic" in e.body
            assert "duration_minutes" in e.body

    def test_is_base_connector_with_source_system(self):
        from packs.consulting.connectors.zoom_mock import ZoomMockConnector

        connector = ZoomMockConnector()

        assert isinstance(connector, BaseConnector)
        assert connector.source_system == "zoom"

    def test_zoom_event_type_registered_in_taxonomy(self):
        from packs.consulting.event_taxonomy.events import ConsultingEventType

        event_values = {e.value for e in ConsultingEventType}
        assert "zoom.meeting_ended" in event_values


# ---------------------------------------------------------------------------
# ConnectorRegistry
# ---------------------------------------------------------------------------

class TestConnectorRegistry:
    def test_all_returns_eight_connectors(self):
        from packs.consulting.connectors.registry import ConnectorRegistry

        registry = ConnectorRegistry()

        assert len(registry.all()) == 8
        assert all(isinstance(c, BaseConnector) for c in registry.all())

    def test_pull_all_returns_events_from_all_source_systems(self):
        from packs.consulting.connectors.registry import ConnectorRegistry

        events = ConnectorRegistry().pull_all()
        source_systems = {e.source_system for e in events}

        assert source_systems == {
            "hubspot", "gmail", "calendar", "asana",
            "slack", "quickbooks", "harvest", "zoom",
        }

    def test_pull_all_deduplicates_by_event_id(self):
        from packs.consulting.connectors.registry import ConnectorRegistry
        from packs.consulting.connectors.gmail_mock import GmailMockConnector

        # Build a registry with gmail registered twice — same events, same IDs
        registry = ConnectorRegistry(extra_connectors=[GmailMockConnector()])
        events = registry.pull_all()
        ids = [e.id for e in events]

        assert len(ids) == len(set(ids)), "duplicate event IDs found after pull_all"
