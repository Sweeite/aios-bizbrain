from datetime import datetime, timezone

from engine.ingestion.base_connector import BaseConnector
from engine.spine.types import BusinessEvent


class HubSpotMockConnector(BaseConnector):
    source_system = "hubspot"

    def pull(self) -> list[BusinessEvent]:
        return [
            BusinessEvent(
                id="hs-deal-99-stage-changed-2025-03-01",
                source_system=self.source_system,
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
        ]
