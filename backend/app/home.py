from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, Query

from engine.connectors.calendar import CalendarConnector, Meeting
from engine.observability.flag_store import FlagStore, get_flag_store
from engine.tools.executor import ToolExecutor
from app.deps import get_executor

router = APIRouter(prefix="/home", tags=["home"])


def _meeting_brief(meeting: Meeting) -> str:
    if meeting.entity_ref:
        return f"Client meeting — check recent notes for {meeting.entity_ref} before joining."
    return "Internal — no client brief needed."


@router.get("/summary")
def home_summary(
    scope: str | None = Query(default=None),
    executor: ToolExecutor = Depends(get_executor),
    flag_store: FlagStore = Depends(get_flag_store),
):
    connector = CalendarConnector()
    raw_meetings = connector.get_todays_meetings(date.today())

    if scope:
        raw_meetings = [m for m in raw_meetings if m.entity_ref == scope]

    meetings = [
        {
            "time": m.time,
            "title": m.title,
            "attendees": m.attendees,
            "brief": _meeting_brief(m),
        }
        for m in raw_meetings
    ]

    flags = flag_store.list_flags(entity_ref=scope)
    flagged = [
        {
            "type": f.type,
            "entity_ref": f.entity_ref,
            "label": f.label,
            "since": f.since.isoformat(),
        }
        for f in flags
    ]

    return {
        "pending_count": len(executor.list_pending()),
        "meetings": meetings,
        "flagged": flagged,
    }
