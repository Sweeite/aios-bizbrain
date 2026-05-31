"Seed roster for the consulting vertical pack."
from engine.spine.types import AgentSpec, Scope, ScopeLevel

CONSULTING_AGENTS: list[AgentSpec] = [
    AgentSpec(
        name="comms-agent",
        role="Manages principal's inbox, calendar, and internal comms; runs commitment-gate on all inbound email",
        scope=Scope(level=ScopeLevel.user_private, user_ref="__principal__"),
        toolset=[
            "gmail.get_thread",
            "gmail.send_email",
            "calendar.get_events",
            "slack.post_message",
        ],
        model_tier={"default": "strong", "routing": "cheap", "classification": "cheap"},
        wake_triggers=["email.received.significant", "human_directed"],
        playbooks=["commitment-gate", "routine-reply"],
        spawn_policy={"may_spawn": False, "max_depth": 0},
    ),
    AgentSpec(
        name="account-agent",
        role="Manages client relationships and deal state; monitors for stalled deals and proactive nudges",
        scope=Scope(level=ScopeLevel.entity, entity_ref="__client__"),
        toolset=[
            "hubspot.get_deal",
            "hubspot.update_deal_stage",
            "gmail.send_email",
            "calendar.get_events",
        ],
        model_tier={"default": "strong", "status_rollup": "cheap"},
        wake_triggers=["deal.stage_changed", "deal.won", "deal.lost", "human_directed"],
        playbooks=["nudge-stalled-deal", "pre-meeting-brief", "qbr-prep"],
        spawn_policy={"may_spawn": True, "max_depth": 1},
    ),
    AgentSpec(
        name="delivery-agent",
        role="Monitors engagement delivery, budget burn, and milestone health",
        scope=Scope(level=ScopeLevel.entity, entity_ref="__engagement__"),
        toolset=[
            "asana.get_project_status",
            "asana.create_task",
            "harvest.get_budget_status",
        ],
        model_tier={"default": "strong", "status_rollup": "cheap"},
        wake_triggers=["milestone.hit", "due_date.slipped", "harvest.budget_threshold_crossed", "human_directed"],
        playbooks=["budget-alert", "scope-conversation"],
        spawn_policy={"may_spawn": True, "max_depth": 1},
    ),
    AgentSpec(
        name="finance-agent",
        role="Monitors firm financials, invoice ageing, and AR; T4 ceiling on money-out actions",
        scope=Scope(level=ScopeLevel.org),
        toolset=[
            "quickbooks.get_invoice",
            "quickbooks.create_invoice",
            "harvest.get_budget_status",
            "quickbooks.pay_bill",
            "harvest.run_payroll",
        ],
        model_tier={"default": "strong", "invoice_status": "cheap"},
        wake_triggers=["invoice.issued", "invoice.paid", "human_directed"],
        playbooks=["ar-chase", "invoice-issuance"],
        spawn_policy={"may_spawn": False, "max_depth": 0},
    ),
]
