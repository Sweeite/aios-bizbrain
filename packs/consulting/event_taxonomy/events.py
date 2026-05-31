"Canonical consulting event types mapped from source systems."
from enum import Enum


class ConsultingEventType(str, Enum):
    # HubSpot — deals
    DEAL_STAGE_CHANGED = "deal.stage_changed"
    DEAL_CREATED = "deal.created"
    DEAL_WON = "deal.won"
    DEAL_LOST = "deal.lost"

    # Gmail — email
    EMAIL_RECEIVED_SIGNIFICANT = "email.received.significant"
    EMAIL_SENT_SIGNIFICANT = "email.sent.significant"

    # Calendar — meetings
    MEETING_OCCURRED = "meeting.occurred"

    # Asana — delivery
    TASK_COMPLETED = "task.completed"
    MILESTONE_HIT = "milestone.hit"
    DUE_DATE_SLIPPED = "due_date.slipped"

    # Slack — decisions
    DECISION_CAPTURED = "slack.decision_captured"

    # QuickBooks — finance
    INVOICE_ISSUED = "invoice.issued"
    INVOICE_PAID = "invoice.paid"

    # Harvest — time tracking
    BUDGET_THRESHOLD_CROSSED = "harvest.budget_threshold_crossed"
    ENGAGEMENT_CLOSED = "harvest.engagement_closed"

    # Zoom — video meetings
    MEETING_ENDED = "zoom.meeting_ended"


CONSULTING_EVENTS: list[str] = [e.value for e in ConsultingEventType]
