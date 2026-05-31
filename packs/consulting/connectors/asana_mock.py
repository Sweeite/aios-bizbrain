from datetime import datetime, timezone

from engine.ingestion.base_connector import BaseConnector
from engine.spine.types import BusinessEvent


class AsanaMockConnector(BaseConnector):
    source_system = "asana"

    def pull(self) -> list[BusinessEvent]:
        return [
            BusinessEvent(
                id="asana-task-42-completed-2025-03-01",
                source_system=self.source_system,
                event_type="task.completed",
                timestamp=datetime(2025, 3, 1, 16, 0, tzinfo=timezone.utc),
                actor="asana-webhook",
                entities=["client-meridian-001"],
                raw_ref="asana-task-42",
                body={
                    "task_name": "Draft SOW — Meridian Q3",
                    "project": "Meridian Capital Engagement",
                    "completed_by": "Austin Smith",
                    "due_date": "2025-03-01",
                },
            ),
            BusinessEvent(
                id="asana-task-55-slipped-2025-03-01",
                source_system=self.source_system,
                event_type="due_date.slipped",
                timestamp=datetime(2025, 3, 1, 17, 0, tzinfo=timezone.utc),
                actor="asana-webhook",
                entities=["client-vertex-002"],
                raw_ref="asana-task-55",
                body={
                    "task_name": "Deliver Phase 1 Report — Vertex",
                    "project": "Vertex Partners Advisory",
                    "original_due": "2025-02-28",
                    "slipped_to": "2025-03-07",
                    "days_overdue": 1,
                },
            ),
            BusinessEvent(
                id="asana-milestone-3-hit-2025-03-01",
                source_system=self.source_system,
                event_type="milestone.hit",
                timestamp=datetime(2025, 3, 1, 12, 0, tzinfo=timezone.utc),
                actor="asana-webhook",
                entities=["client-northpath-001"],
                raw_ref="asana-milestone-3",
                body={
                    "task_name": "Internal QA Framework — Complete",
                    "project": "Northpath Ops",
                    "milestone": "QA Phase 1",
                },
            ),
        ]
