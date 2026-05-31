from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date


@dataclass
class Meeting:
    time: str
    title: str
    attendees: list[str]
    entity_ref: str | None = None


_MEETINGS: list[Meeting] = [
    Meeting(
        time="09:00",
        title="Meridian Capital — Q3 Engagement Kickoff",
        attendees=["Sarah Chen", "James Ortega"],
        entity_ref="client-meridian-001",
    ),
    Meeting(
        time="11:30",
        title="Northpath Internal — Capacity Planning",
        attendees=["Austin Smith", "Rachel Moore"],
        entity_ref=None,
    ),
    Meeting(
        time="14:00",
        title="Vertex Partners — Proposal Review",
        attendees=["David Kim", "Lauren Brooks", "Mike Torres"],
        entity_ref="client-vertex-002",
    ),
]


class CalendarConnector:
    def get_todays_meetings(self, today: date) -> list[Meeting]:
        return list(_MEETINGS)
