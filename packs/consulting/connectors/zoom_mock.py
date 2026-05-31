from datetime import datetime, timezone

from engine.ingestion.base_connector import BaseConnector
from engine.spine.types import BusinessEvent


class ZoomMockConnector(BaseConnector):
    source_system = "zoom"

    def pull(self) -> list[BusinessEvent]:
        return [
            BusinessEvent(
                id="zoom-mtg-89012345-ended-2025-03-01",
                source_system=self.source_system,
                event_type="zoom.meeting_ended",
                timestamp=datetime(2025, 3, 1, 15, 0, tzinfo=timezone.utc),
                actor="zoom-webhook",
                entities=["client-vertex-002"],
                raw_ref="zoom-mtg-89012345",
                body={
                    "meeting_topic": "Vertex Partners — Proposal Walkthrough",
                    "host": "Austin Smith",
                    "participants": ["David Kim", "Lauren Brooks", "Austin Smith"],
                    "duration_minutes": 42,
                    "recording_url": "https://zoom.us/rec/share/mock-recording-id",
                    "has_transcript": True,
                },
            ),
        ]
