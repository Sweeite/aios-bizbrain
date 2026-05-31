from datetime import datetime, timezone

from engine.ingestion.base_connector import BaseConnector
from engine.spine.types import BusinessEvent


class GmailMockConnector(BaseConnector):
    source_system = "gmail"

    def pull(self) -> list[BusinessEvent]:
        return [
            BusinessEvent(
                id="gmail-thread-1a2b-received-2025-03-01",
                source_system=self.source_system,
                event_type="email.received.significant",
                timestamp=datetime(2025, 3, 1, 8, 15, tzinfo=timezone.utc),
                actor="gmail-webhook",
                entities=["client-meridian-001"],
                raw_ref="gmail-thread-1a2b",
                body={
                    "subject": "Re: Q3 Engagement Scope",
                    "from": "sarah.chen@meridian.com",
                    "to": "austin@northpath.io",
                    "snippet": "We're happy to move forward — please send the SOW by Friday.",
                    "has_commitment": True,
                },
            ),
            BusinessEvent(
                id="gmail-thread-3c4d-sent-2025-03-01",
                source_system=self.source_system,
                event_type="email.sent.significant",
                timestamp=datetime(2025, 3, 1, 9, 30, tzinfo=timezone.utc),
                actor="gmail-webhook",
                entities=["client-vertex-002"],
                raw_ref="gmail-thread-3c4d",
                body={
                    "subject": "Vertex Partners — Proposal Draft",
                    "from": "austin@northpath.io",
                    "to": "david.kim@vertex.com",
                    "snippet": "Please find attached our proposal for the advisory engagement.",
                    "has_commitment": False,
                },
            ),
        ]
