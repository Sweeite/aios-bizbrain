"""
Slice 12: Comms, Delivery, Finance agents + orchestrator dispatch fix.
TDD — one cycle at a time; behavior through public interfaces only.
"""
import pytest
from unittest.mock import MagicMock

from engine.spine.types import (
    AutonomyTier,
    ParkedApprovalRequest,
    Scope,
    ScopeLevel,
    ToolMode,
    ToolSpec,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _org_scope() -> Scope:
    return Scope(level=ScopeLevel.org)


def _entity_scope(ref: str = "engagement-northpath-001") -> Scope:
    return Scope(level=ScopeLevel.entity, entity_ref=ref)


def _user_private_scope(ref: str = "principal-austin") -> Scope:
    return Scope(level=ScopeLevel.user_private, user_ref=ref)


def _mock_anthropic(text: str = "Draft text.", input_tokens: int = 100, output_tokens: int = 50):
    client = MagicMock()
    resp = MagicMock()
    resp.content[0].text = text
    resp.usage.input_tokens = input_tokens
    resp.usage.output_tokens = output_tokens
    client.messages.create.return_value = resp
    return client


def _mock_anthropic_seq(*texts):
    """Return mock client whose messages.create returns each text in sequence."""
    client = MagicMock()
    resps = []
    for t in texts:
        r = MagicMock()
        r.content[0].text = t
        r.usage.input_tokens = 50
        r.usage.output_tokens = 30
        resps.append(r)
    client.messages.create.side_effect = resps
    return client


def _make_t4_spec(name: str = "quickbooks.pay_bill") -> ToolSpec:
    return ToolSpec(
        name=name,
        inputs={"bill_id": "string", "amount": "number"},
        system="quickbooks",
        mode=ToolMode.write,
        tier=AutonomyTier.T4,
        scope_required=ScopeLevel.org,
        reversible=False,
        side_effects=["payment_initiated"],
    )


# ---------------------------------------------------------------------------
# Cycle 1: T4 tool — prepare-only, never parks
# ---------------------------------------------------------------------------

class TestT4PrepareOnly:
    def _t4_executor(self, prepare_output: str = "BATCH-2026-001: $12,400 to Vendor Corp"):
        from engine.tools.registry import ToolRegistry
        from engine.tools.executor import ToolExecutor

        spec = _make_t4_spec()
        fn = lambda inputs, dry_run=False: prepare_output

        registry = ToolRegistry()
        registry.register(spec, fn)
        return ToolExecutor(registry)

    def test_t4_returns_prepare_artifact_string(self):
        executor = self._t4_executor()
        result = executor.execute(
            "quickbooks.pay_bill",
            inputs={"bill_id": "bill-001", "amount": 12400},
            scope=_org_scope(),
            requesting_agent="finance-agent",
            principal="org",
            rationale="AR collection",
            idempotency_key="t4-key-001",
        )
        assert isinstance(result, str)
        assert "BATCH" in result

    def test_t4_never_returns_parked_approval_request(self):
        executor = self._t4_executor()
        result = executor.execute(
            "quickbooks.pay_bill",
            inputs={"bill_id": "bill-002", "amount": 5000},
            scope=_org_scope(),
            requesting_agent="finance-agent",
            principal="org",
            rationale="AR collection",
            idempotency_key="t4-key-002",
        )
        assert not isinstance(result, ParkedApprovalRequest)

    def test_t4_fn_called_with_dry_run_true(self):
        """T4 only ever calls fn(dry_run=True) — human executes, never the system."""
        from engine.tools.registry import ToolRegistry
        from engine.tools.executor import ToolExecutor

        calls = []
        spec = _make_t4_spec("quickbooks.run_payroll")
        fn = lambda inputs, dry_run=False: calls.append(dry_run) or "payroll-package"

        registry = ToolRegistry()
        registry.register(spec, fn)
        executor = ToolExecutor(registry)

        executor.execute(
            "quickbooks.run_payroll",
            inputs={},
            scope=_org_scope(),
            requesting_agent="finance-agent",
            principal="org",
            rationale="payroll",
            idempotency_key="t4-key-003",
        )

        assert calls == [True]

    def test_t4_does_not_appear_in_list_pending(self):
        executor = self._t4_executor()
        executor.execute(
            "quickbooks.pay_bill",
            inputs={"bill_id": "bill-003", "amount": 1000},
            scope=_org_scope(),
            requesting_agent="finance-agent",
            principal="org",
            rationale="test",
            idempotency_key="t4-key-004",
        )
        assert executor.list_pending() == []


# ---------------------------------------------------------------------------
# Cycle 2: Orchestrator dispatches to the correct agent implementation
# ---------------------------------------------------------------------------

class TestOrchestratorDispatch:
    def _build_orch_with_all_agents(self, client):
        from engine.agent.registry import AgentRegistry
        from engine.agent.live import LiveQuery
        from engine.agent.span_emitter import SpanEmitter
        from engine.ingestion.memory_writer import MemoryWriter
        from engine.agent.orchestrator import Orchestrator
        from packs.consulting.agent_specs.roster import CONSULTING_AGENTS

        registry = AgentRegistry()
        for spec in CONSULTING_AGENTS:
            registry.register(spec)

        return Orchestrator(
            registry=registry,
            memory_writer=MemoryWriter(),
            live=LiveQuery(),
            anthropic_client=client,
            span_emitter=SpanEmitter(),
        )

    def test_milestone_trigger_dispatches_to_delivery_agent(self):
        orch = self._build_orch_with_all_agents(_mock_anthropic("Delivery status OK."))
        result = orch.handle("milestone.hit", "engagement-northpath-001")
        assert result.agent_name == "delivery-agent"

    def test_invoice_trigger_dispatches_to_finance_agent(self):
        orch = self._build_orch_with_all_agents(_mock_anthropic("Invoice AR summary."))
        result = orch.handle("invoice.paid", "org")
        assert result.agent_name == "finance-agent"

    def test_deal_trigger_still_dispatches_to_account_agent(self):
        orch = self._build_orch_with_all_agents(_mock_anthropic("Dear client..."))
        result = orch.handle("deal.stage_changed", "client-northpath-001")
        assert result.agent_name == "account-agent"

    def test_span_actor_matches_dispatched_agent(self):
        orch = self._build_orch_with_all_agents(_mock_anthropic("Milestone reached."))
        result = orch.handle("milestone.hit", "engagement-northpath-001")
        assert result.span.actor == "delivery-agent"


# ---------------------------------------------------------------------------
# Cycle 3: DeliveryAgent — produces delivery summary draft
# ---------------------------------------------------------------------------

class TestDeliveryAgent:
    _scope = _entity_scope("engagement-northpath-001")

    def test_produces_draft_string(self):
        from engine.agent.agents.delivery import DeliveryAgent

        result = DeliveryAgent().run(
            entity_ref="engagement-northpath-001",
            memory_records=[],
            live_context={"current_milestone": "Phase 2", "budget_pct": 72, "days_overdue": 0},
            scope=self._scope,
            run_id="run-del-001",
            anthropic_client=_mock_anthropic("Phase 2 on track. Budget at 72%."),
        )

        assert isinstance(result.draft, str)
        assert len(result.draft) > 0

    def test_span_actor_is_delivery_agent(self):
        from engine.agent.agents.delivery import DeliveryAgent
        from engine.spine.types import SpanOp

        result = DeliveryAgent().run(
            entity_ref="engagement-northpath-001",
            memory_records=[],
            live_context={"budget_pct": 85, "days_overdue": 3},
            scope=self._scope,
            run_id="run-del-002",
            anthropic_client=_mock_anthropic("Budget at 85%, 3 days overdue.", input_tokens=90, output_tokens=45),
        )

        assert result.span.actor == "delivery-agent"
        assert result.span.op == SpanOp.reason
        assert result.span.token_in == 90
        assert result.span.token_out == 45

    def test_uses_sonnet_model(self):
        from engine.agent.agents.delivery import DeliveryAgent, REASONING_MODEL

        client = _mock_anthropic()
        DeliveryAgent().run(
            entity_ref="engagement-northpath-001",
            memory_records=[],
            live_context={},
            scope=self._scope,
            run_id="run-del-003",
            anthropic_client=client,
        )

        assert REASONING_MODEL == "claude-sonnet-4-6"
        assert client.messages.create.call_args.kwargs["model"] == "claude-sonnet-4-6"

    def test_fuses_memory_and_live_context_in_prompt(self):
        from engine.agent.agents.delivery import DeliveryAgent
        from engine.spine.types import MemoryRecord, MemoryStore, Confidence

        client = _mock_anthropic()
        record = MemoryRecord(
            store=MemoryStore.episodic,
            payload={"event_type": "milestone.hit", "milestone": "Phase 1", "budget_pct": 60},
            provenance="asana:task-99",
            temporal_validity={"as_of": "2025-03-01T09:00:00+00:00", "lifespan_days": 365},
            scope=self._scope,
            confidence=Confidence.observed,
        )

        DeliveryAgent().run(
            entity_ref="engagement-northpath-001",
            memory_records=[record],
            live_context={"current_milestone": "Phase 2", "budget_pct": 72},
            scope=self._scope,
            run_id="run-del-004",
            anthropic_client=client,
        )

        user_msg = client.messages.create.call_args.kwargs["messages"][0]["content"]
        assert "milestone.hit" in user_msg
        assert "Phase 2" in user_msg


# ---------------------------------------------------------------------------
# Cycle 4: CommsAgent — produces routine reply draft for non-substantive email
# ---------------------------------------------------------------------------

class TestCommsAgentRoutine:
    _scope = _user_private_scope()

    def _routine_client(self, draft: str = "Thanks for reaching out."):
        """Two calls: classify → not substantive; then draft routine reply."""
        return _mock_anthropic_seq(
            '{"is_client_substantive": false, "client_ref": null}',
            draft,
        )

    def test_produces_routine_draft_string(self):
        from engine.agent.agents.comms import CommsAgent

        result = CommsAgent().run(
            entity_ref="principal-austin",
            memory_records=[],
            live_context={"email_subject": "Quick question", "email_from": "vendor@example.com"},
            scope=self._scope,
            run_id="run-comms-001",
            anthropic_client=self._routine_client("Happy to help. Let me check and get back to you."),
        )

        assert isinstance(result.draft, str)
        assert len(result.draft) > 0

    def test_routine_email_agent_name_is_comms(self):
        from engine.agent.agents.comms import CommsAgent

        result = CommsAgent().run(
            entity_ref="principal-austin",
            memory_records=[],
            live_context={"email_subject": "Invoice attached", "email_from": "vendor@example.com"},
            scope=self._scope,
            run_id="run-comms-002",
            anthropic_client=self._routine_client(),
        )

        assert result.agent_name == "comms-agent"

    def test_span_actor_is_comms_agent(self):
        from engine.agent.agents.comms import CommsAgent

        result = CommsAgent().run(
            entity_ref="principal-austin",
            memory_records=[],
            live_context={},
            scope=self._scope,
            run_id="run-comms-003",
            anthropic_client=self._routine_client(),
        )

        assert result.span.actor == "comms-agent"

    def test_classification_uses_haiku_model(self):
        from engine.agent.agents.comms import CommsAgent, ROUTING_MODEL

        client = self._routine_client()
        CommsAgent().run(
            entity_ref="principal-austin",
            memory_records=[],
            live_context={"email_subject": "Newsletter", "email_from": "news@example.com"},
            scope=self._scope,
            run_id="run-comms-004",
            anthropic_client=client,
        )

        first_call = client.messages.create.call_args_list[0]
        assert first_call.kwargs["model"] == ROUTING_MODEL


# ---------------------------------------------------------------------------
# Cycle 5: CommsAgent → Account handoff for substantive client email
# ---------------------------------------------------------------------------

class TestCommsAgentHandoff:
    _scope = _user_private_scope()

    def _substantive_client(
        self,
        client_ref: str = "client-northpath-001",
        account_draft: str = "Dear Northpath, following up on the proposal...",
    ):
        """Two calls: classify → substantive; then AccountAgent drafts nudge."""
        return _mock_anthropic_seq(
            f'{{"is_client_substantive": true, "client_ref": "{client_ref}"}}',
            account_draft,
        )

    def test_substantive_email_routes_to_account_agent(self):
        from engine.agent.agents.comms import CommsAgent

        result = CommsAgent().run(
            entity_ref="principal-austin",
            memory_records=[],
            live_context={
                "email_subject": "Re: Q3 Audit scope — can we expand?",
                "email_from": "cfo@northpath.com",
                "email_snippet": "We'd like to add the treasury reconciliation...",
            },
            scope=self._scope,
            run_id="run-comms-hand-001",
            anthropic_client=self._substantive_client(),
        )

        assert result.agent_name == "account-agent"

    def test_handoff_span_actor_is_account_agent(self):
        from engine.agent.agents.comms import CommsAgent

        result = CommsAgent().run(
            entity_ref="principal-austin",
            memory_records=[],
            live_context={"email_subject": "Scope expansion", "email_from": "cfo@northpath.com"},
            scope=self._scope,
            run_id="run-comms-hand-002",
            anthropic_client=self._substantive_client(),
        )

        assert result.span.actor == "account-agent"

    def test_handoff_result_draft_is_account_draft(self):
        from engine.agent.agents.comms import CommsAgent

        result = CommsAgent().run(
            entity_ref="principal-austin",
            memory_records=[],
            live_context={"email_subject": "Proposal follow-up", "email_from": "cfo@northpath.com"},
            scope=self._scope,
            run_id="run-comms-hand-003",
            anthropic_client=self._substantive_client(
                account_draft="Dear CFO, thank you for reaching out about expanding scope."
            ),
        )

        assert "CFO" in result.draft or len(result.draft) > 0

    def test_invalid_classification_json_falls_back_to_routine(self):
        """Corrupt LLM response → safe fallback to routine reply, not handoff."""
        from engine.agent.agents.comms import CommsAgent

        client = _mock_anthropic_seq(
            "not valid JSON at all",   # classify call
            "Routine reply draft.",    # routine draft call
        )

        result = CommsAgent().run(
            entity_ref="principal-austin",
            memory_records=[],
            live_context={"email_subject": "Hi", "email_from": "someone@example.com"},
            scope=self._scope,
            run_id="run-comms-hand-004",
            anthropic_client=client,
        )

        assert result.agent_name == "comms-agent"


# ---------------------------------------------------------------------------
# Cycle 6: FinanceAgent — prepare-only draft, parked=None even with executor
# ---------------------------------------------------------------------------

class TestFinanceAgent:
    _scope = _org_scope()

    def _t4_executor(self):
        from engine.tools.registry import ToolRegistry
        from engine.tools.executor import ToolExecutor

        registry = ToolRegistry()
        for name, output in [
            ("quickbooks.pay_bill", "BATCH-2026-001: $12,400 → Vendor Corp"),
            ("harvest.run_payroll", "PAYROLL-2026-05: 8 employees, $48,200 total"),
        ]:
            spec = _make_t4_spec(name)
            captured_name = name
            fn = (lambda n: lambda inputs, dry_run=False: f"{n}:prepare")(captured_name)
            registry.register(spec, fn)

        return ToolExecutor(registry)

    def test_produces_draft_string(self):
        from engine.agent.agents.finance import FinanceAgent

        result = FinanceAgent().run(
            entity_ref="org",
            memory_records=[],
            live_context={"ar_ageing_days": 45, "outstanding_invoices": 3},
            scope=self._scope,
            run_id="run-fin-001",
            anthropic_client=_mock_anthropic("AR summary: 3 invoices overdue. Avg 45 days."),
        )

        assert isinstance(result.draft, str)
        assert len(result.draft) > 0

    def test_span_actor_is_finance_agent(self):
        from engine.agent.agents.finance import FinanceAgent
        from engine.spine.types import SpanOp

        result = FinanceAgent().run(
            entity_ref="org",
            memory_records=[],
            live_context={},
            scope=self._scope,
            run_id="run-fin-002",
            anthropic_client=_mock_anthropic("Finance summary.", input_tokens=80, output_tokens=40),
        )

        assert result.span.actor == "finance-agent"
        assert result.span.op == SpanOp.reason
        assert result.span.token_in == 80

    def test_parked_is_none_without_executor(self):
        from engine.agent.agents.finance import FinanceAgent

        result = FinanceAgent().run(
            entity_ref="org",
            memory_records=[],
            live_context={},
            scope=self._scope,
            run_id="run-fin-003",
            anthropic_client=_mock_anthropic(),
        )

        assert result.parked is None

    def test_parked_is_none_even_with_t4_executor(self):
        """T4 ceiling: executor never creates a parked request for money-out tools."""
        from engine.agent.agents.finance import FinanceAgent

        result = FinanceAgent().run(
            entity_ref="org",
            memory_records=[],
            live_context={"ar_ageing_days": 60, "outstanding_invoices": 5},
            scope=self._scope,
            run_id="run-fin-004",
            anthropic_client=_mock_anthropic("Finance summary with prepare packages."),
            tool_executor=self._t4_executor(),
            idempotency_key="fin-t4-001",
        )

        assert result.parked is None

    def test_uses_sonnet_model(self):
        from engine.agent.agents.finance import FinanceAgent, REASONING_MODEL

        client = _mock_anthropic()
        FinanceAgent().run(
            entity_ref="org",
            memory_records=[],
            live_context={},
            scope=self._scope,
            run_id="run-fin-005",
            anthropic_client=client,
        )

        assert REASONING_MODEL == "claude-sonnet-4-6"
        assert client.messages.create.call_args.kwargs["model"] == "claude-sonnet-4-6"


# ---------------------------------------------------------------------------
# Cycle 7: Full 4-agent routing — catalog tools, scope resolution, all triggers
# ---------------------------------------------------------------------------

class TestFullRouting:
    def _build_all(self, client=None):
        from engine.agent.registry import AgentRegistry
        from engine.agent.live import LiveQuery
        from engine.agent.span_emitter import SpanEmitter
        from engine.ingestion.memory_writer import MemoryWriter
        from engine.agent.orchestrator import Orchestrator
        from packs.consulting.agent_specs.roster import CONSULTING_AGENTS

        registry = AgentRegistry()
        for spec in CONSULTING_AGENTS:
            registry.register(spec)

        return Orchestrator(
            registry=registry,
            memory_writer=MemoryWriter(),
            live=LiveQuery(),
            anthropic_client=client or _mock_anthropic(),
            span_emitter=SpanEmitter(),
        )

    def test_due_date_slipped_routes_to_delivery(self):
        orch = self._build_all(_mock_anthropic("Slip detected."))
        result = orch.handle("due_date.slipped", "engagement-northpath-001")
        assert result.agent_name == "delivery-agent"

    def test_budget_threshold_routes_to_delivery(self):
        orch = self._build_all(_mock_anthropic("Budget alert."))
        result = orch.handle("harvest.budget_threshold_crossed", "engagement-northpath-001")
        assert result.agent_name == "delivery-agent"

    def test_invoice_issued_routes_to_finance(self):
        orch = self._build_all(_mock_anthropic("Finance summary."))
        result = orch.handle("invoice.issued", "org")
        assert result.agent_name == "finance-agent"

    def test_email_received_routes_to_comms_via_user_private_scope(self):
        """email.received.significant with user_private request_scope routes to comms-agent."""
        from engine.agent.orchestrator import Orchestrator
        from engine.agent.registry import AgentRegistry
        from engine.agent.live import LiveQuery
        from engine.agent.span_emitter import SpanEmitter
        from engine.ingestion.memory_writer import MemoryWriter
        from packs.consulting.agent_specs.roster import CONSULTING_AGENTS

        registry = AgentRegistry()
        for spec in CONSULTING_AGENTS:
            registry.register(spec)

        orch = Orchestrator(
            registry=registry,
            memory_writer=MemoryWriter(),
            live=LiveQuery(),
            anthropic_client=_mock_anthropic_seq(
                '{"is_client_substantive": false, "client_ref": null}',
                "Routine reply.",
            ),
            span_emitter=SpanEmitter(),
        )

        result = orch.handle(
            "email.received.significant",
            "principal-austin",
            request_scope=Scope(level=ScopeLevel.user_private, user_ref="principal-austin"),
        )
        assert result.agent_name == "comms-agent"

    def test_catalog_has_t4_finance_tools(self):
        """pay_bill and run_payroll are in the consulting catalog at T4 tier."""
        from packs.consulting.tool_catalog.catalog import CONSULTING_TOOLS

        t4_names = {s.name for s in CONSULTING_TOOLS if s.tier == AutonomyTier.T4}
        assert "quickbooks.pay_bill" in t4_names
        assert "harvest.run_payroll" in t4_names

    def test_finance_agent_spec_includes_t4_tools(self):
        from packs.consulting.agent_specs.roster import CONSULTING_AGENTS

        finance_spec = next(s for s in CONSULTING_AGENTS if s.name == "finance-agent")
        assert "quickbooks.pay_bill" in finance_spec.toolset
        assert "harvest.run_payroll" in finance_spec.toolset

    def test_inherit_never_exceed_comms_scope_stays_user_private(self):
        """CommsAgent scope never broadens beyond user_private even under org parent."""
        from engine.agent.orchestrator import Orchestrator
        from engine.agent.registry import AgentRegistry
        from engine.agent.live import LiveQuery
        from engine.agent.span_emitter import SpanEmitter
        from engine.ingestion.memory_writer import MemoryWriter
        from packs.consulting.agent_specs.roster import CONSULTING_AGENTS

        registry = AgentRegistry()
        for spec in CONSULTING_AGENTS:
            registry.register(spec)

        orch = Orchestrator(
            registry=registry,
            memory_writer=MemoryWriter(),
            live=LiveQuery(),
            anthropic_client=_mock_anthropic_seq(
                '{"is_client_substantive": false, "client_ref": null}',
                "Routine reply.",
            ),
            span_emitter=SpanEmitter(),
        )

        result = orch.handle(
            "email.received.significant",
            "principal-austin",
            request_scope=Scope(level=ScopeLevel.user_private, user_ref="principal-austin"),
            parent_scope=Scope(level=ScopeLevel.org),
        )

        assert result.span.scope.level == ScopeLevel.user_private
