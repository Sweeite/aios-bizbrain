import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

from engine.spine.types import Scope, Span, SpanOp

REASONING_MODEL = "claude-sonnet-4-6"
ROUTING_MODEL = "claude-haiku-4-5-20251001"


class DeliveryAgent:
    name = "delivery-agent"

    def run(
        self,
        entity_ref: str,
        memory_records: list,
        live_context: dict,
        scope: Scope,
        run_id: str,
        anthropic_client,
        tool_executor=None,
        idempotency_key: str | None = None,
        parent_span_id: str | None = None,
    ):
        from engine.agent.agents.account import AgentStepResult

        memory_summary = "\n".join(
            f"- {r.payload.get('event_type', 'event')}: "
            f"milestone={r.payload.get('milestone', '?')}, "
            f"budget_pct={r.payload.get('budget_pct', '?')}"
            for r in memory_records
        ) or "(no prior delivery records)"

        user_content = (
            f"Engagement: {entity_ref}\n"
            f"Current milestone: {live_context.get('current_milestone', 'unknown')}\n"
            f"Budget used: {live_context.get('budget_pct', 0)}%\n"
            f"Days overdue: {live_context.get('days_overdue', 0)}\n\n"
            f"Episodic memory:\n{memory_summary}\n\n"
            "Summarise delivery health and flag any risks. "
            "If budget exceeds 80% or milestones are overdue, draft a scope conversation starter."
        )

        started_at = datetime.now(timezone.utc)
        response = anthropic_client.messages.create(
            model=REASONING_MODEL,
            max_tokens=512,
            system=(
                "You are an AI delivery manager. Summarise engagement health concisely. "
                "Flag budget overruns and slipped milestones."
            ),
            messages=[{"role": "user", "content": user_content}],
        )
        ended_at = datetime.now(timezone.utc)

        draft_text = response.content[0].text
        span = Span(
            span_id=str(uuid.uuid4()),
            run_id=run_id,
            parent_span_id=parent_span_id,
            actor=self.name,
            op=SpanOp.reason,
            input_ref=f"recall:{entity_ref}+live:{entity_ref}",
            output_ref=f"delivery_summary:{entity_ref}",
            started_at=started_at,
            ended_at=ended_at,
            model_tier=REASONING_MODEL,
            token_in=response.usage.input_tokens,
            token_out=response.usage.output_tokens,
            scope=scope,
            status="ok",
            outcome="delivery_summary",
        )

        return AgentStepResult(agent_name=self.name, draft=draft_text, span=span)
