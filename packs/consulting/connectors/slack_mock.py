from datetime import datetime, timezone

from engine.ingestion.base_connector import BaseConnector
from engine.spine.types import BusinessEvent


class SlackMockConnector(BaseConnector):
    source_system = "slack"

    def pull(self) -> list[BusinessEvent]:
        return [
            BusinessEvent(
                id="slack-msg-C01-1709294400-decision-2025-03-01",
                source_system=self.source_system,
                event_type="slack.decision_captured",
                timestamp=datetime(2025, 3, 1, 10, 0, tzinfo=timezone.utc),
                actor="slack-webhook",
                entities=["client-meridian-001"],
                raw_ref="slack-msg-C01-1709294400",
                body={
                    "channel": "#meridian-engagement",
                    "decision": "Scope capped at 3 workstreams; no extension without sponsor sign-off.",
                    "captured_by": "Austin Smith",
                    "participants": ["Austin Smith", "Rachel Moore"],
                },
            ),
        ]
