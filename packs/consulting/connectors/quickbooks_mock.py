from datetime import datetime, timezone

from engine.ingestion.base_connector import BaseConnector
from engine.spine.types import BusinessEvent


class QuickBooksMockConnector(BaseConnector):
    source_system = "quickbooks"

    def pull(self) -> list[BusinessEvent]:
        return [
            BusinessEvent(
                id="qb-inv-007-issued-2025-03-01",
                source_system=self.source_system,
                event_type="invoice.issued",
                timestamp=datetime(2025, 3, 1, 11, 0, tzinfo=timezone.utc),
                actor="quickbooks-webhook",
                entities=["client-meridian-001"],
                raw_ref="qb-inv-007",
                body={
                    "invoice_number": "INV-007",
                    "client": "Meridian Capital",
                    "amount_usd": 24500.00,
                    "due_date": "2025-03-31",
                    "line_items": ["Advisory retainer — March", "Workshop facilitation"],
                },
            ),
            BusinessEvent(
                id="qb-inv-006-paid-2025-03-01",
                source_system=self.source_system,
                event_type="invoice.paid",
                timestamp=datetime(2025, 3, 1, 15, 30, tzinfo=timezone.utc),
                actor="quickbooks-webhook",
                entities=["client-vertex-002"],
                raw_ref="qb-inv-006",
                body={
                    "invoice_number": "INV-006",
                    "client": "Vertex Partners",
                    "amount_usd": 18000.00,
                    "paid_on": "2025-03-01",
                    "payment_method": "wire",
                },
            ),
        ]
