from datetime import datetime, timezone

from engine.ingestion.base_connector import BaseConnector
from engine.spine.types import BusinessEvent


class CalendarMockConnector(BaseConnector):
    source_system = "calendar"

    def pull(self) -> list[BusinessEvent]:
        return [
            BusinessEvent(
                id="cal-event-q3-kickoff-2025-02-28",
                source_system=self.source_system,
                event_type="meeting.occurred",
                timestamp=datetime(2025, 2, 28, 9, 0, tzinfo=timezone.utc),
                actor="calendar-sync",
                entities=["client-meridian-001"],
                raw_ref="cal-event-q3-kickoff",
                body={
                    "title": "Meridian Capital — Q3 Engagement Kickoff",
                    "attendees": ["Sarah Chen", "James Ortega", "Austin Smith"],
                    "duration_minutes": 60,
                    "notes": "Agreed on scope, SOW to follow.",
                },
            ),
            BusinessEvent(
                id="cal-event-vertex-proposal-2025-03-01",
                source_system=self.source_system,
                event_type="meeting.occurred",
                timestamp=datetime(2025, 3, 1, 14, 0, tzinfo=timezone.utc),
                actor="calendar-sync",
                entities=["client-vertex-002"],
                raw_ref="cal-event-vertex-proposal",
                body={
                    "title": "Vertex Partners — Proposal Review",
                    "attendees": ["David Kim", "Lauren Brooks", "Austin Smith"],
                    "duration_minutes": 45,
                    "notes": "Client requested revised pricing by EOW.",
                },
            ),
        ]
