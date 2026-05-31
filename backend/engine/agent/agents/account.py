import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

from engine.spine.types import ParkedApprovalRequest, Scope, Span, SpanOp

REASONING_MODEL = "claude-sonnet-4-6"


@dataclass
class AgentStepResult:
    agent_name: str
    draft: str
    span: Span
    parked: ParkedApprovalRequest | None = field(default=None)


class AccountAgent:
    name = "account-agent"

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
    ) -> AgentStepResult:
        memory_summary = "\n".join(
            f"- {r.payload.get('event_type', 'event')}: "
            f"stage={r.payload.get('to_stage', '?')}, "
            f"days_in_stage={r.payload.get('days_in_stage', '?')}"
            for r in memory_records
        ) or "(no prior episodic records)"

        user_content = (
            f"Client: {entity_ref}\n"
            f"Deal: {live_context.get('deal_name', '')}\n"
            f"Current stage: {live_context.get('current_stage', 'unknown')}\n"
            f"Days in stage: {live_context.get('days_in_stage', 0)}\n\n"
            f"Episodic memory:\n{memory_summary}\n\n"
            "Draft a short, professional nudge email to re-engage this stalled deal."
        )

        started_at = datetime.now(timezone.utc)
        response = anthropic_client.messages.create(
            model=REASONING_MODEL,
            max_tokens=512,
            system=(
                "You are an AI business assistant helping manage client relationships. "
                "Draft professional, concise nudge emails."
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
            output_ref=f"draft:{entity_ref}",
            started_at=started_at,
            ended_at=ended_at,
            model_tier=REASONING_MODEL,
            token_in=response.usage.input_tokens,
            token_out=response.usage.output_tokens,
            scope=scope,
            status="ok",
            outcome="draft_nudge",
        )

        parked: ParkedApprovalRequest | None = None
        if tool_executor is not None:
            idem_key = idempotency_key or str(uuid.uuid4())
            result = tool_executor.execute(
                "gmail.draft_email",
                inputs={
                    "to": entity_ref,
                    "subject": f"Following up — {live_context.get('deal_name', entity_ref)}",
                    "body": draft_text,
                },
                scope=scope,
                requesting_agent=self.name,
                principal=entity_ref,
                rationale="nudge stalled deal",
                idempotency_key=idem_key,
                run_id=run_id,
                parent_span_id=span.span_id,
            )
            if isinstance(result, ParkedApprovalRequest):
                parked = result

        return AgentStepResult(agent_name=self.name, draft=draft_text, span=span, parked=parked)
