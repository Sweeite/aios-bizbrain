import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from engine.spine.types import Scope, Span, SpanOp

REASONING_MODEL = "claude-sonnet-4-6"


@dataclass
class AgentStepResult:
    agent_name: str
    draft: str
    span: Span


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

        return AgentStepResult(
            agent_name=self.name,
            draft=response.content[0].text,
            span=Span(
                span_id=str(uuid.uuid4()),
                run_id=run_id,
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
            ),
        )
