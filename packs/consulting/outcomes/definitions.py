"Outcome labels and ROI metric definitions for consulting engagements."

OUTCOME_LABELS: dict[str, str] = {
    "deal_won": "Deal closed-won",
    "deal_lost": "Deal closed-lost",
    "stall_resolved": "Stalled deal unblocked",
    "invoice_collected": "Invoice collected on time",
    "late_payment_recovered": "Late payment recovered",
    "scope_breach_caught": "Scope breach caught before over-delivery",
    "meeting_brief_generated": "Pre-meeting brief generated",
    "qbr_prep_generated": "QBR brief generated",
    "routine_reply_sent": "Routine email reply sent autonomously",
    "approval_approved": "Approval reviewed and approved",
    "approval_rejected": "Approval reviewed and rejected with reason",
}

ROI_METRICS: dict[str, dict] = {
    "autonomous_actions_taken": {
        "description": "T0/T1/T2 actions executed without human review",
        "unit": "count",
    },
    "approvals_routed": {
        "description": "T3 actions parked for human approval",
        "unit": "count",
    },
    "avg_approval_latency_mins": {
        "description": "Minutes from park to approval/rejection",
        "unit": "minutes",
    },
    "deals_nudged": {
        "description": "Stalled deals where a nudge was drafted",
        "unit": "count",
    },
    "ar_days_saved": {
        "description": "Estimated days saved on invoice follow-up",
        "unit": "days",
    },
    "spend_per_client_usd": {
        "description": "LLM token spend attributed per client",
        "unit": "usd",
    },
    "spend_per_agent_usd": {
        "description": "LLM token spend attributed per agent",
        "unit": "usd",
    },
}
