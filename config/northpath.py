"""
Northpath client config — all per-client tunables.
Swap this file when standing up a new client. Engine never imports from here.
"""
from engine.spine.types import AutonomyTier

CLIENT_NAME = "Northpath"
CLIENT_SLUG = "northpath"

# ── Autonomy tier overrides ──────────────────────────────────────────────────
# Default tiers live in the tool catalog. Override here per client.
AUTONOMY_OVERRIDES: dict[str, AutonomyTier] = {
    # Northpath is comfortable with Asana task creation running without approval
    "asana.create_task": AutonomyTier.T2,
    # Slack posts require approval at Northpath (partners are cautious about internal comms)
    "slack.post_message": AutonomyTier.T3,
}

# ── Agent roster edits ───────────────────────────────────────────────────────
# Adds or overrides agents from the consulting seed roster.
# Set to None to disable a seed agent.
AGENT_OVERRIDES: dict[str, dict | None] = {}

# ── Retention ────────────────────────────────────────────────────────────────
RETENTION = {
    "episodic_memory_days": 365,
    "telemetry_spans_days": 90,
    "audit_log_days": 2555,  # 7 years
    "approval_queue_days": 365,
}

# ── Consolidation cadence ────────────────────────────────────────────────────
CONSOLIDATION = {
    "light_pass_cron": "0 2 * * *",    # 02:00 nightly
    "deep_pass_cron": "0 3 * * 0",     # 03:00 Sunday
}

# ── Trust dial ───────────────────────────────────────────────────────────────
# Approval rate thresholds at which the system suggests escalating/relaxing tiers.
TRUST_DIAL = {
    "escalate_if_rejection_rate_above": 0.20,   # 20% rejection → suggest T3→T4
    "relax_if_approval_rate_above": 0.95,        # 95% approval → suggest T3→T2
}

# ── Notification routing ─────────────────────────────────────────────────────
NOTIFICATIONS = {
    "urgent_via": ["slack", "email"],
    "routine_via": ["cockpit_queue"],
    "slack_channel_urgent": "#ai-brain-urgent",
    "email_address": "partners@northpath.example.com",
    "digest_email_address": "partners@northpath.example.com",
    "digest_schedule_cron": "0 7 * * *",  # 07:00 daily
}

# ── Slack flags (what to capture from Slack) ─────────────────────────────────
SLACK_CAPTURE = {
    "channels": ["#client-work", "#deals", "#finance"],
    "capture_decisions": True,
    "capture_commitments": True,
    "firehose": False,
}

# ── Deal stall thresholds (days per stage) ────────────────────────────────────
DEAL_STALL_THRESHOLDS: dict[str, int] = {
    "Qualification": 7,
    "Proposal": 14,
    "Negotiation": 21,
    "default": 14,
}

# ── Budget alert thresholds ───────────────────────────────────────────────────
BUDGET_ALERT_THRESHOLDS = {
    "warn_at_pct": 80,
    "escalate_at_pct": 95,
}
