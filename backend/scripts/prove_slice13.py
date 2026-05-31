"""
Slice 13 manual proving path — high-urgency notification via Resend + Slack.

Usage:
    cd backend
    python scripts/prove_slice13.py

Requires RESEND_API_KEY, SLACK_WEBHOOK_URL, NOTIFICATION_EMAIL_FROM in .env.
"""
import os

from dotenv import load_dotenv

from engine.notifications.router import NotificationRouter
from engine.notifications.senders import ResendEmailSender, SlackWebhookSender
from engine.spine.types import ParkedApprovalRequest, Scope, ScopeLevel, UrgencyLevel

load_dotenv()

config = {
    "urgent_via": ["slack", "email"],
    "routine_via": ["cockpit_queue"],
    "slack_channel_urgent": "#ai-brain-urgent",
    "email_address": os.getenv("DIGEST_EMAIL_ADDRESS", "partners@northpath.example.com"),
    "digest_email_address": os.getenv("DIGEST_EMAIL_ADDRESS", "partners@northpath.example.com"),
}

router = NotificationRouter(config, ResendEmailSender(), SlackWebhookSender())

req = ParkedApprovalRequest(
    action="draft_email.send",
    preview="Dear client, confirming engagement commencing June 1 at 200 hours.",
    requesting_agent="comms-agent",
    principal="partner@northpath.example.com",
    scope=Scope(level=ScopeLevel.entity, entity_ref="client-northpath-001"),
    rationale="Client escalation flagged by account agent",
    idempotency_key="prove-slice13-001",
    urgency=UrgencyLevel.high,
)

router.route(req)
print("High-urgency notification dispatched.")
print(f"  Email → {config['email_address']}")
print(f"  Slack → {config['slack_channel_urgent']}")
