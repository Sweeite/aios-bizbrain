import uuid
from datetime import datetime, timezone

from engine.spine.types import Scope, Span, SpanOp

REASONING_MODEL = "claude-sonnet-4-6"
ROUTING_MODEL = "claude-haiku-4-5-20251001"

_T4_FINANCE_TOOLS = ["quickbooks.pay_bill", "harvest.run_payroll"]


class FinanceAgent:
    name = "finance-agent"

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
            f"invoice={r.payload.get('invoice_id', '?')}, "
            f"amount={r.payload.get('amount', '?')}, "
            f"days_overdue={r.payload.get('days_overdue', '?')}"
            for r in memory_records
        ) or "(no prior finance records)"

        prepare_artifacts: list[str] = []
        if tool_executor is not None:
            idem_key = idempotency_key or str(uuid.uuid4())
            for i, tool_name in enumerate(_T4_FINANCE_TOOLS):
                try:
                    artifact = tool_executor.execute(
                        tool_name,
                        inputs={"engagement_ref": entity_ref},
                        scope=scope,
                        requesting_agent=self.name,
                        principal=entity_ref,
                        rationale="finance review",
                        idempotency_key=f"{idem_key}:{tool_name}",
                        run_id=run_id,
                        parent_span_id=parent_span_id,
                    )
                    if isinstance(artifact, str):
                        prepare_artifacts.append(f"[{tool_name}] {artifact}")
                except Exception:
                    pass

        artifacts_section = (
            "\n\nPrepare packages (human executes):\n" + "\n".join(prepare_artifacts)
            if prepare_artifacts
            else ""
        )

        user_content = (
            f"Firm financials review\n"
            f"AR ageing: {live_context.get('ar_ageing_days', 'unknown')} days avg\n"
            f"Outstanding invoices: {live_context.get('outstanding_invoices', 0)}\n\n"
            f"Episodic memory:\n{memory_summary}"
            f"{artifacts_section}\n\n"
            "Summarise the firm's financial health. List overdue invoices. "
            "Do NOT authorise any payments — produce a prepare package for human review only."
        )

        started_at = datetime.now(timezone.utc)
        response = anthropic_client.messages.create(
            model=REASONING_MODEL,
            max_tokens=512,
            system=(
                "You are an AI finance monitor. Summarise AR, invoice ageing, and budget status. "
                "Never authorise payments autonomously — output is for human review only."
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
            output_ref=f"finance_summary:{entity_ref}",
            started_at=started_at,
            ended_at=ended_at,
            model_tier=REASONING_MODEL,
            token_in=response.usage.input_tokens,
            token_out=response.usage.output_tokens,
            scope=scope,
            status="ok",
            outcome="finance_summary",
        )

        return AgentStepResult(agent_name=self.name, draft=draft_text, span=span, parked=None)
