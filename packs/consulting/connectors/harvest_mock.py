from datetime import datetime, timezone

from engine.ingestion.base_connector import BaseConnector
from engine.spine.types import BusinessEvent


class HarvestMockConnector(BaseConnector):
    source_system = "harvest"

    def pull(self) -> list[BusinessEvent]:
        return [
            BusinessEvent(
                id="harvest-proj-12-budget-80pct-2025-03-01",
                source_system=self.source_system,
                event_type="harvest.budget_threshold_crossed",
                timestamp=datetime(2025, 3, 1, 7, 0, tzinfo=timezone.utc),
                actor="harvest-sync",
                entities=["client-meridian-001"],
                raw_ref="harvest-proj-12",
                body={
                    "engagement": "Meridian Capital Q3 Advisory",
                    "budget_usd": 50000.00,
                    "spent_usd": 40200.00,
                    "threshold_pct": 80,
                    "remaining_usd": 9800.00,
                },
            ),
            BusinessEvent(
                id="harvest-proj-9-closed-2025-03-01",
                source_system=self.source_system,
                event_type="harvest.engagement_closed",
                timestamp=datetime(2025, 3, 1, 18, 0, tzinfo=timezone.utc),
                actor="harvest-sync",
                entities=["client-northpath-001"],
                raw_ref="harvest-proj-9",
                body={
                    "engagement": "Northpath Internal Ops Review",
                    "budget_usd": 12000.00,
                    "spent_usd": 11450.00,
                    "hours_logged": 95.5,
                    "closed_by": "Rachel Moore",
                },
            ),
        ]
