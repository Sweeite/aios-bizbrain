"""
Slice 4: Agent registry, orchestrator, agent loop, and Account agent.
Tests describe observable behavior through public interfaces only.
"""
import pytest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from engine.spine.types import AgentSpec, Scope, ScopeLevel


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _account_spec() -> AgentSpec:
    return AgentSpec(
        name="account-agent",
        role="Manages client relationships and deal state",
        scope=Scope(level=ScopeLevel.entity, entity_ref="__client__"),
        toolset=["hubspot.get_deal", "gmail.send_email"],
        model_tier={"default": "strong", "routing": "cheap"},
        wake_triggers=["deal.stage_changed", "deal.won", "human_directed"],
        playbooks=["nudge-stalled-deal"],
        spawn_policy={"may_spawn": True, "max_depth": 1},
    )


def _mock_anthropic(
    draft_text: str = "Dear Northpath team...",
    input_tokens: int = 100,
    output_tokens: int = 50,
):
    client = MagicMock()
    resp = MagicMock()
    resp.content[0].text = draft_text
    resp.usage.input_tokens = input_tokens
    resp.usage.output_tokens = output_tokens
    client.messages.create.return_value = resp
    return client


# ---------------------------------------------------------------------------
# Cycle 1: AgentRegistry — route by trigger + scope level
# ---------------------------------------------------------------------------

class TestAgentRegistry:
    def test_routes_to_registered_agent_by_trigger(self):
        from engine.agent.registry import AgentRegistry

        registry = AgentRegistry()
        registry.register(_account_spec())

        result = registry.route(
            "deal.stage_changed",
            Scope(level=ScopeLevel.entity, entity_ref="client-northpath-001"),
        )

        assert result.name == "account-agent"

    def test_raises_when_no_agent_matches_trigger(self):
        from engine.agent.registry import AgentRegistry, NoMatchingAgent

        registry = AgentRegistry()
        registry.register(_account_spec())

        with pytest.raises(NoMatchingAgent):
            registry.route(
                "invoice.paid",
                Scope(level=ScopeLevel.entity, entity_ref="client-001"),
            )

    def test_adding_new_agent_requires_no_orchestrator_code_change(self):
        """Two agents registered; each routes by its own wake_triggers."""
        from engine.agent.registry import AgentRegistry

        delivery_spec = AgentSpec(
            name="delivery-agent",
            role="Monitors engagement delivery",
            scope=Scope(level=ScopeLevel.entity, entity_ref="__engagement__"),
            toolset=[],
            model_tier={"default": "strong"},
            wake_triggers=["milestone.hit"],
            playbooks=[],
            spawn_policy={},
        )
        registry = AgentRegistry()
        registry.register(_account_spec())
        registry.register(delivery_spec)

        account = registry.route(
            "deal.stage_changed", Scope(level=ScopeLevel.entity, entity_ref="c-001")
        )
        delivery = registry.route(
            "milestone.hit", Scope(level=ScopeLevel.entity, entity_ref="e-001")
        )

        assert account.name == "account-agent"
        assert delivery.name == "delivery-agent"

    def test_org_scoped_agent_handles_any_scope_level(self):
        from engine.agent.registry import AgentRegistry

        finance_spec = AgentSpec(
            name="finance-agent",
            role="Firm financials",
            scope=Scope(level=ScopeLevel.org),
            toolset=[],
            model_tier={},
            wake_triggers=["invoice.paid"],
            playbooks=[],
            spawn_policy={},
        )
        registry = AgentRegistry()
        registry.register(finance_spec)

        result = registry.route(
            "invoice.paid", Scope(level=ScopeLevel.entity, entity_ref="c-001")
        )
        assert result.name == "finance-agent"

    def test_all_specs_returns_registered_specs(self):
        from engine.agent.registry import AgentRegistry

        registry = AgentRegistry()
        registry.register(_account_spec())

        assert len(registry.all_specs()) == 1
        assert registry.all_specs()[0].name == "account-agent"


# ---------------------------------------------------------------------------
# Cycle 2: LiveQuery — fixture deal state
# ---------------------------------------------------------------------------

class TestLiveQuery:
    def test_returns_current_stage(self):
        from engine.agent.live import LiveQuery

        result = LiveQuery().query("client-northpath-001")
        assert result["current_stage"] == "Proposal"

    def test_returns_days_in_stage_as_positive_int(self):
        from engine.agent.live import LiveQuery

        result = LiveQuery().query("client-northpath-001")
        assert isinstance(result["days_in_stage"], int)
        assert result["days_in_stage"] > 0

    def test_includes_entity_ref(self):
        from engine.agent.live import LiveQuery

        result = LiveQuery().query("client-northpath-001")
        assert result["entity_ref"] == "client-northpath-001"


# ---------------------------------------------------------------------------
# Cycle 3: SpanEmitter — emit and collect
# ---------------------------------------------------------------------------

class TestSpanEmitter:
    def _make_span(self):
        from engine.spine.types import Span, SpanOp

        return Span(
            span_id="span-001",
            run_id="run-001",
            actor="account-agent",
            op=SpanOp.reason,
            input_ref="recall:client-001+live:client-001",
            output_ref="draft:client-001",
            started_at=datetime(2025, 3, 1, tzinfo=timezone.utc),
            ended_at=datetime(2025, 3, 1, 0, 0, 1, tzinfo=timezone.utc),
            model_tier="claude-sonnet-4-6",
            token_in=100,
            token_out=50,
            scope=Scope(level=ScopeLevel.entity, entity_ref="client-001"),
            status="ok",
            outcome="draft_nudge",
        )

    def test_collects_emitted_spans(self):
        from engine.agent.span_emitter import SpanEmitter

        emitter = SpanEmitter()
        emitter.emit(self._make_span())
        assert len(emitter.spans()) == 1

    def test_preserves_span_fields(self):
        from engine.agent.span_emitter import SpanEmitter
        from engine.spine.types import SpanOp

        emitter = SpanEmitter()
        emitter.emit(self._make_span())

        s = emitter.spans()[0]
        assert s.actor == "account-agent"
        assert s.op == SpanOp.reason
        assert s.model_tier == "claude-sonnet-4-6"
        assert s.token_in == 100
        assert s.token_out == 50


# ---------------------------------------------------------------------------
# Cycle 4: AccountAgent — produces draft nudge via Anthropic API
# ---------------------------------------------------------------------------

class TestAccountAgent:
    _scope = Scope(level=ScopeLevel.entity, entity_ref="client-northpath-001")

    def test_produces_draft_string(self):
        from engine.agent.agents.account import AccountAgent

        client = _mock_anthropic(draft_text="Dear Northpath, following up on the proposal...")
        result = AccountAgent().run(
            entity_ref="client-northpath-001",
            memory_records=[],
            live_context={"current_stage": "Proposal", "days_in_stage": 21},
            scope=self._scope,
            run_id="run-001",
            anthropic_client=client,
        )

        assert isinstance(result.draft, str)
        assert len(result.draft) > 0

    def test_uses_sonnet_model(self):
        from engine.agent.agents.account import AccountAgent, REASONING_MODEL

        client = _mock_anthropic()
        AccountAgent().run(
            entity_ref="client-northpath-001",
            memory_records=[],
            live_context={"current_stage": "Proposal", "days_in_stage": 21},
            scope=self._scope,
            run_id="run-001",
            anthropic_client=client,
        )

        assert REASONING_MODEL == "claude-sonnet-4-6"
        assert client.messages.create.call_args.kwargs["model"] == "claude-sonnet-4-6"

    def test_span_has_model_tier_and_token_counts(self):
        from engine.agent.agents.account import AccountAgent
        from engine.spine.types import SpanOp

        client = _mock_anthropic(input_tokens=120, output_tokens=60)
        result = AccountAgent().run(
            entity_ref="client-northpath-001",
            memory_records=[],
            live_context={"current_stage": "Proposal", "days_in_stage": 21},
            scope=self._scope,
            run_id="run-001",
            anthropic_client=client,
        )

        assert result.span.model_tier == "claude-sonnet-4-6"
        assert result.span.token_in == 120
        assert result.span.token_out == 60
        assert result.span.op == SpanOp.reason
        assert result.span.actor == "account-agent"

    def test_fuses_memory_and_live_context_in_prompt(self):
        """Both recall records and live context must reach the Anthropic API."""
        from engine.agent.agents.account import AccountAgent
        from engine.spine.types import MemoryRecord, MemoryStore, Confidence

        client = _mock_anthropic()
        memory_record = MemoryRecord(
            store=MemoryStore.episodic,
            payload={"event_type": "deal.stage_changed", "to_stage": "Proposal", "days_in_stage": 21},
            provenance="hubspot:hs-deal-99",
            temporal_validity={"as_of": "2025-03-01T09:00:00+00:00", "lifespan_days": 365},
            scope=self._scope,
            confidence=Confidence.observed,
        )

        AccountAgent().run(
            entity_ref="client-northpath-001",
            memory_records=[memory_record],
            live_context={"current_stage": "Proposal", "days_in_stage": 21, "deal_name": "Q3 Audit"},
            scope=self._scope,
            run_id="run-001",
            anthropic_client=client,
        )

        user_msg = client.messages.create.call_args.kwargs["messages"][0]["content"]
        assert "deal.stage_changed" in user_msg   # from episodic memory
        assert "Proposal" in user_msg              # from live context


# ---------------------------------------------------------------------------
# Cycle 5: Orchestrator — routes by capability + scope, fuses context
# ---------------------------------------------------------------------------

class TestOrchestrator:
    def _build(self, draft="Dear Client...", memory_writer=None):
        from engine.agent.registry import AgentRegistry
        from engine.agent.live import LiveQuery
        from engine.agent.span_emitter import SpanEmitter
        from engine.ingestion.memory_writer import MemoryWriter
        from engine.agent.orchestrator import Orchestrator

        registry = AgentRegistry()
        registry.register(_account_spec())
        emitter = SpanEmitter()
        client = _mock_anthropic(draft_text=draft)

        orch = Orchestrator(
            registry=registry,
            memory_writer=memory_writer or MemoryWriter(),
            live=LiveQuery(),
            anthropic_client=client,
            span_emitter=emitter,
        )
        return orch, emitter, client

    def test_produces_draft_nudge(self):
        orch, _, _ = self._build(draft="Dear Northpath, following up...")
        result = orch.handle("deal.stage_changed", "client-northpath-001")
        assert isinstance(result.draft, str) and len(result.draft) > 0

    def test_routing_fails_with_empty_registry(self):
        """Proves routing goes through registry — no hardcoded agent fallback."""
        from engine.agent.registry import AgentRegistry, NoMatchingAgent
        from engine.agent.live import LiveQuery
        from engine.agent.span_emitter import SpanEmitter
        from engine.ingestion.memory_writer import MemoryWriter
        from engine.agent.orchestrator import Orchestrator

        orch = Orchestrator(
            registry=AgentRegistry(),   # empty — nothing registered
            memory_writer=MemoryWriter(),
            live=LiveQuery(),
            anthropic_client=_mock_anthropic(),
        )
        with pytest.raises(NoMatchingAgent):
            orch.handle("deal.stage_changed", "client-northpath-001")

    def test_emits_span_after_step(self):
        orch, emitter, _ = self._build()
        orch.handle("deal.stage_changed", "client-northpath-001")

        assert len(emitter.spans()) == 1
        s = emitter.spans()[0]
        assert s.token_in > 0
        assert s.token_out > 0
        assert s.model_tier == "claude-sonnet-4-6"

    def test_fuses_recall_and_live_context(self):
        """Both sources must contribute to the Anthropic prompt."""
        from engine.ingestion.memory_writer import MemoryWriter
        from engine.ingestion.entity_resolver import EntityResolver
        from engine.spine.types import BusinessEvent

        event = BusinessEvent(
            id="hs-deal-99-stage-changed-2025-03-01",
            source_system="hubspot",
            event_type="deal.stage_changed",
            timestamp=datetime(2025, 3, 1, 9, 0, tzinfo=timezone.utc),
            actor="hubspot-webhook",
            entities=["client-northpath-001"],
            raw_ref="hs-deal-99",
            body={"deal_name": "Northpath Q3 Audit", "to_stage": "Proposal", "days_in_stage": 21},
        )
        mw = MemoryWriter()
        mw.write(EntityResolver(known_entities={"client-northpath-001": "client"}).resolve(event))

        orch, _, client = self._build(memory_writer=mw)
        orch.handle("deal.stage_changed", "client-northpath-001")

        user_msg = client.messages.create.call_args.kwargs["messages"][0]["content"]
        assert "deal.stage_changed" in user_msg   # from recall
        assert "Proposal" in user_msg              # from live query


# ---------------------------------------------------------------------------
# Cycle 6: Scope isolation and spawn inheritance
# ---------------------------------------------------------------------------

class TestScopeIsolation:
    def test_recall_blocked_for_different_entity(self):
        """An agent scoped to client-A cannot read records for client-B."""
        from engine.ingestion.memory_writer import MemoryWriter
        from engine.ingestion.entity_resolver import EntityResolver
        from engine.spine.types import BusinessEvent

        event = BusinessEvent(
            id="hs-deal-99",
            source_system="hubspot",
            event_type="deal.stage_changed",
            timestamp=datetime(2025, 3, 1, tzinfo=timezone.utc),
            actor="hubspot-webhook",
            entities=["client-northpath-001"],
            raw_ref="hs-deal-99",
            body={"to_stage": "Proposal"},
        )
        writer = MemoryWriter()
        writer.write(
            EntityResolver(known_entities={"client-northpath-001": "client"}).resolve(event)
        )

        foreign = Scope(level=ScopeLevel.entity, entity_ref="client-rival-999")
        assert writer.recall("client-northpath-001", foreign) == []

    def test_spawned_agent_clamped_to_entity_when_parent_is_entity(self):
        """Org-scoped agent gets clamped to entity scope when parent is entity-scoped."""
        from engine.agent.registry import AgentRegistry
        from engine.agent.live import LiveQuery
        from engine.agent.span_emitter import SpanEmitter
        from engine.ingestion.memory_writer import MemoryWriter
        from engine.agent.orchestrator import Orchestrator

        org_agent = AgentSpec(
            name="org-agent",
            role="Org-level agent",
            scope=Scope(level=ScopeLevel.org),
            toolset=[],
            model_tier={"default": "strong"},
            wake_triggers=["deal.stage_changed"],
            playbooks=[],
            spawn_policy={},
        )
        registry = AgentRegistry()
        registry.register(org_agent)
        emitter = SpanEmitter()

        orch = Orchestrator(
            registry=registry,
            memory_writer=MemoryWriter(),
            live=LiveQuery(),
            anthropic_client=_mock_anthropic(),
            span_emitter=emitter,
        )
        parent_scope = Scope(level=ScopeLevel.entity, entity_ref="client-northpath-001")
        result = orch.handle(
            "deal.stage_changed", "client-northpath-001", parent_scope=parent_scope
        )

        assert result.span.scope.level == ScopeLevel.entity
        assert result.span.scope.entity_ref == "client-northpath-001"

    def test_entity_scoped_agent_keeps_scope_under_org_parent(self):
        """Entity-scoped agent is not broadened when parent is org-scoped."""
        from engine.agent.registry import AgentRegistry
        from engine.agent.live import LiveQuery
        from engine.agent.span_emitter import SpanEmitter
        from engine.ingestion.memory_writer import MemoryWriter
        from engine.agent.orchestrator import Orchestrator

        registry = AgentRegistry()
        registry.register(_account_spec())

        orch = Orchestrator(
            registry=registry,
            memory_writer=MemoryWriter(),
            live=LiveQuery(),
            anthropic_client=_mock_anthropic(),
            span_emitter=SpanEmitter(),
        )
        result = orch.handle(
            "deal.stage_changed",
            "client-northpath-001",
            parent_scope=Scope(level=ScopeLevel.org),
        )

        assert result.span.scope.level == ScopeLevel.entity
        assert result.span.scope.entity_ref == "client-northpath-001"


# ---------------------------------------------------------------------------
# Cycle 7: Reflection hook — evaluates agent step output
# ---------------------------------------------------------------------------

class TestReflectionHookUpgraded:
    def test_reflect_on_step_task_is_registered(self):
        from engine.worker.celery_app import celery_app
        from engine.worker import tasks  # noqa: F401 — side-effect

        assert "engine.worker.tasks.reflection.reflect_on_step" in celery_app.tasks

    def test_reflect_on_step_uses_haiku_model(self):
        from engine.worker.tasks import reflection as m

        assert m.EVALUATION_MODEL == "claude-haiku-4-5-20251001"

    def test_reflect_on_step_returns_should_write_flag(self):
        from engine.worker.tasks.reflection import reflect_on_step

        mock_resp = MagicMock()
        mock_resp.content[0].text = (
            '{"should_write": true, "store": "entity", "reason": "New deal stage noted."}'
        )

        with patch("engine.worker.tasks.reflection.anthropic") as mock_lib:
            mock_client = MagicMock()
            mock_lib.Anthropic.return_value = mock_client
            mock_client.messages.create.return_value = mock_resp

            result = reflect_on_step.apply(kwargs={
                "run_id": "run-001",
                "agent_name": "account-agent",
                "entity_ref": "client-northpath-001",
                "draft": "Dear team, following up on the stalled proposal...",
            })

        assert result.successful()
        outcome = result.get()
        assert "should_write" in outcome

    def test_reflect_on_step_calls_anthropic_with_haiku(self):
        from engine.worker.tasks.reflection import reflect_on_step, EVALUATION_MODEL

        mock_resp = MagicMock()
        mock_resp.content[0].text = '{"should_write": false, "store": null, "reason": "Routine."}'

        with patch("engine.worker.tasks.reflection.anthropic") as mock_lib:
            mock_client = MagicMock()
            mock_lib.Anthropic.return_value = mock_client
            mock_client.messages.create.return_value = mock_resp

            reflect_on_step.apply(kwargs={
                "run_id": "run-002",
                "agent_name": "account-agent",
                "entity_ref": "client-northpath-001",
                "draft": "Hi, just checking in.",
            })

        call_kwargs = mock_client.messages.create.call_args
        assert call_kwargs.kwargs["model"] == EVALUATION_MODEL


# ---------------------------------------------------------------------------
# Cycle 8: End-to-end — fixture event → trigger → draft nudge + span in Supabase
# ---------------------------------------------------------------------------

class TestEndToEnd:
    def test_deal_stalled_trigger_produces_draft_and_span(self):
        """Full path: episodic memory + trigger → orchestrator → draft nudge + cost span."""
        from engine.agent.registry import AgentRegistry
        from engine.agent.live import LiveQuery
        from engine.agent.span_emitter import SpanEmitter
        from engine.ingestion.memory_writer import MemoryWriter
        from engine.ingestion.entity_resolver import EntityResolver
        from engine.agent.orchestrator import Orchestrator
        from engine.spine.types import BusinessEvent, SpanOp

        event = BusinessEvent(
            id="hs-deal-99-stage-changed-2025-03-01",
            source_system="hubspot",
            event_type="deal.stage_changed",
            timestamp=datetime(2025, 3, 1, 9, 0, tzinfo=timezone.utc),
            actor="hubspot-webhook",
            entities=["client-northpath-001"],
            raw_ref="hs-deal-99",
            body={"deal_name": "Northpath Q3 Audit", "to_stage": "Proposal", "days_in_stage": 21},
        )
        mw = MemoryWriter()
        mw.write(EntityResolver(known_entities={"client-northpath-001": "client"}).resolve(event))

        registry = AgentRegistry()
        registry.register(_account_spec())
        emitter = SpanEmitter()
        client = _mock_anthropic(
            draft_text="Dear Northpath team, your proposal has been pending for 21 days...",
            input_tokens=200,
            output_tokens=80,
        )

        result = Orchestrator(
            registry=registry,
            memory_writer=mw,
            live=LiveQuery(),
            anthropic_client=client,
            span_emitter=emitter,
        ).handle("deal.stage_changed", "client-northpath-001")

        # Draft produced
        assert len(result.draft) > 10

        # Span emitted with full cost attribution
        assert len(emitter.spans()) == 1
        s = emitter.spans()[0]
        assert s.op == SpanOp.reason
        assert s.actor == "account-agent"
        assert s.model_tier == "claude-sonnet-4-6"
        assert s.token_in == 200
        assert s.token_out == 80
        assert s.scope.level == ScopeLevel.entity
        assert s.scope.entity_ref == "client-northpath-001"

    def test_consulting_pack_roster_registers_without_orchestrator_changes(self):
        """Pack's agent roster loads into the engine registry cleanly."""
        from engine.agent.registry import AgentRegistry
        from packs.consulting.agent_specs.roster import CONSULTING_AGENTS

        registry = AgentRegistry()
        for spec in CONSULTING_AGENTS:
            registry.register(spec)

        assert len(registry.all_specs()) == len(CONSULTING_AGENTS)

        routed = registry.route(
            "deal.stage_changed",
            Scope(level=ScopeLevel.entity, entity_ref="client-northpath-001"),
        )
        assert routed.name == "account-agent"


# ---------------------------------------------------------------------------
# Cycle 9: Orchestrator forwards tool_executor → result.parked is set
# ---------------------------------------------------------------------------

class TestOrchestratorWithToolExecutor:
    def _build_executor(self):
        from engine.tools.registry import ToolRegistry
        from engine.tools.executor import ToolExecutor
        from engine.tools.implementations.draft_email import DraftEmailTool, SPEC

        registry = ToolRegistry()
        registry.register(SPEC, DraftEmailTool().execute)
        return ToolExecutor(registry)

    def test_orchestrator_sets_parked_on_result_when_executor_given(self):
        from engine.agent.registry import AgentRegistry
        from engine.agent.live import LiveQuery
        from engine.agent.span_emitter import SpanEmitter
        from engine.ingestion.memory_writer import MemoryWriter
        from engine.agent.orchestrator import Orchestrator
        from engine.spine.types import ParkedApprovalRequest

        registry = AgentRegistry()
        registry.register(_account_spec())

        orch = Orchestrator(
            registry=registry,
            memory_writer=MemoryWriter(),
            live=LiveQuery(),
            anthropic_client=_mock_anthropic(draft_text="Confirming scope at 200 hours commencing June 1."),
            span_emitter=SpanEmitter(),
            tool_executor=self._build_executor(),
            idempotency_key="orch-park-test-001",
        )

        result = orch.handle("deal.stage_changed", "client-northpath-001")

        assert result.parked is not None
        assert isinstance(result.parked, ParkedApprovalRequest)
        assert result.parked.action == "gmail.draft_email"
        assert result.parked.idempotency_key == "orch-park-test-001"

    def test_orchestrator_without_executor_leaves_parked_none(self):
        from engine.agent.registry import AgentRegistry
        from engine.agent.live import LiveQuery
        from engine.agent.span_emitter import SpanEmitter
        from engine.ingestion.memory_writer import MemoryWriter
        from engine.agent.orchestrator import Orchestrator

        registry = AgentRegistry()
        registry.register(_account_spec())

        orch = Orchestrator(
            registry=registry,
            memory_writer=MemoryWriter(),
            live=LiveQuery(),
            anthropic_client=_mock_anthropic(),
            span_emitter=SpanEmitter(),
        )

        result = orch.handle("deal.stage_changed", "client-northpath-001")
        assert result.parked is None
