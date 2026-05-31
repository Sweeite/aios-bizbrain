import json
import uuid
from datetime import datetime, timezone

from engine.spine.types import Scope, ScopeLevel, Span, SpanOp

REASONING_MODEL = "claude-sonnet-4-6"
ROUTING_MODEL = "claude-haiku-4-5-20251001"


class CommsAgent:
    name = "comms-agent"

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
        from engine.agent.agents.account import AccountAgent, AgentStepResult

        email_summary = "\n".join(
            f"- {r.payload.get('subject', '(no subject)')}: "
            f"from={r.payload.get('from', '?')}, "
            f"snippet={r.payload.get('snippet', '')[:80]}"
            for r in memory_records
        ) or "(no email records)"

        # --- Classification step (cheap model) ---
        classify_content = (
            f"Email context:\n{email_summary}\n"
            f"Subject: {live_context.get('email_subject', '')}\n"
            f"From: {live_context.get('email_from', '')}\n"
            f"Snippet: {live_context.get('email_snippet', '')}\n\n"
            'Is this a substantive client email requiring account management? '
            'Respond with JSON only: {"is_client_substantive": true/false, "client_ref": "<ref or null>"}'
        )

        classify_resp = anthropic_client.messages.create(
            model=ROUTING_MODEL,
            max_tokens=64,
            system="You classify emails for routing. Respond with JSON only.",
            messages=[{"role": "user", "content": classify_content}],
        )

        try:
            classification = json.loads(classify_resp.content[0].text)
        except (json.JSONDecodeError, IndexError):
            classification = {"is_client_substantive": False, "client_ref": None}

        # --- Handoff to AccountAgent for substantive client emails ---
        if classification.get("is_client_substantive") and classification.get("client_ref"):
            client_ref = classification["client_ref"]
            entity_scope = Scope(level=ScopeLevel.entity, entity_ref=client_ref)
            return AccountAgent().run(
                entity_ref=client_ref,
                memory_records=memory_records,
                live_context={**live_context, "entity_ref": client_ref},
                scope=entity_scope,
                run_id=run_id,
                anthropic_client=anthropic_client,
                tool_executor=tool_executor,
                idempotency_key=idempotency_key,
                parent_span_id=parent_span_id,
            )

        # --- Routine reply (strong model) ---
        user_content = (
            f"Principal's inbox summary:\n{email_summary}\n"
            f"Latest email — Subject: {live_context.get('email_subject', '')}, "
            f"From: {live_context.get('email_from', '')}\n\n"
            "Draft a brief, professional routine reply."
        )

        started_at = datetime.now(timezone.utc)
        response = anthropic_client.messages.create(
            model=REASONING_MODEL,
            max_tokens=256,
            system=(
                "You are an AI chief-of-staff managing the principal's inbox. "
                "Draft concise, professional replies to routine emails."
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
            input_ref=f"inbox:{entity_ref}",
            output_ref=f"routine_reply:{entity_ref}",
            started_at=started_at,
            ended_at=ended_at,
            model_tier=REASONING_MODEL,
            token_in=response.usage.input_tokens,
            token_out=response.usage.output_tokens,
            scope=scope,
            status="ok",
            outcome="routine_reply",
        )

        return AgentStepResult(agent_name=self.name, draft=draft_text, span=span)
