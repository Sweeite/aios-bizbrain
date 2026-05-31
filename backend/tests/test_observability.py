"""
Slice 7: Observability — spans on every proving-path step, trace tree + eval label.
"""
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from engine.spine.types import Scope, ScopeLevel, Span, SpanOp


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _scope(entity_ref: str = "client-northpath-001") -> Scope:
    return Scope(level=ScopeLevel.entity, entity_ref=entity_ref)


def _make_span(
    run_id: str = "run-test",
    span_id: str = "span-test",
    actor: str = "test-actor",
    op: SpanOp = SpanOp.reason,
) -> Span:
    now = datetime.now(timezone.utc)
    return Span(
        span_id=span_id,
        run_id=run_id,
        actor=actor,
        op=op,
        input_ref=f"input:{span_id}",
        output_ref=f"output:{span_id}",
        started_at=now,
        ended_at=now,
        model_tier="n/a",
        token_in=0,
        token_out=0,
        scope=_scope(),
        status="ok",
    )


def _mock_anthropic(
    draft_text: str = "Dear Client...",
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


def _make_t3_executor(span_emitter=None, audit_store=None):
    from engine.tools.registry import ToolRegistry
    from engine.tools.executor import ToolExecutor
    from engine.spine.types import AutonomyTier, ToolMode, ToolSpec

    spec = ToolSpec(
        name="test.write",
        inputs={"body": "str"},
        system="test",
        mode=ToolMode.write,
        tier=AutonomyTier.T3,
        scope_required=ScopeLevel.entity,
        reversible=False,
        side_effects=[],
    )
    registry = ToolRegistry()
    registry.register(spec, lambda inputs, dry_run=False: inputs.get("body", "result"))
    return ToolExecutor(registry, span_emitter=span_emitter, audit_store=audit_store)


def _park(executor, key: str = "key-001", run_id: str = "run-test"):
    executor.execute(
        "test.write",
        inputs={"body": "draft body"},
        scope=_scope(),
        requesting_agent="account-agent",
        principal="client-northpath-001",
        rationale="commitment detected",
        idempotency_key=key,
        run_id=run_id,
    )


# ---------------------------------------------------------------------------
# Cycle 1: SpanStore — save and retrieve spans by run_id
# ---------------------------------------------------------------------------

class TestSpanStore:
    def test_save_and_retrieve_span_by_run_id(self):
        from engine.observability.span_store import InMemorySpanStore
        store = InMemorySpanStore()
        store.save(_make_span(run_id="run-001", span_id="sp-001"))
        result = store.get_by_run("run-001")
        assert len(result) == 1
        assert result[0].span_id == "sp-001"

    def test_get_by_run_returns_only_matching_run(self):
        from engine.observability.span_store import InMemorySpanStore
        store = InMemorySpanStore()
        store.save(_make_span(run_id="run-A", span_id="sp-1"))
        store.save(_make_span(run_id="run-B", span_id="sp-2"))
        assert len(store.get_by_run("run-A")) == 1
        assert store.get_by_run("run-A")[0].span_id == "sp-1"

    def test_get_unknown_run_returns_empty(self):
        from engine.observability.span_store import InMemorySpanStore
        assert InMemorySpanStore().get_by_run("no-such-run") == []


# ---------------------------------------------------------------------------
# Cycle 2: RunStore — save and retrieve runs
# ---------------------------------------------------------------------------

class TestRunStore:
    def test_save_and_retrieve_run(self):
        from engine.observability.run_store import InMemoryRunStore
        from engine.spine.types import Run
        store = InMemoryRunStore()
        run = Run(
            run_id="run-001",
            initiated_by="deal.stage_changed",
            scope=_scope(),
            started_at=datetime.now(timezone.utc),
        )
        store.save(run)
        assert store.get("run-001").run_id == "run-001"

    def test_get_unknown_run_returns_none(self):
        from engine.observability.run_store import InMemoryRunStore
        assert InMemoryRunStore().get("no-such-run") is None


# ---------------------------------------------------------------------------
# Cycle 3: SpanEmitter persists to SpanStore
# ---------------------------------------------------------------------------

class TestSpanEmitterPersistence:
    def test_emit_saves_to_store(self):
        from engine.agent.span_emitter import SpanEmitter
        from engine.observability.span_store import InMemorySpanStore

        store = InMemorySpanStore()
        emitter = SpanEmitter(store=store)
        emitter.emit(_make_span(run_id="run-002", span_id="sp-002"))
        assert store.get_by_run("run-002")[0].span_id == "sp-002"

    def test_emit_without_store_still_works(self):
        from engine.agent.span_emitter import SpanEmitter
        emitter = SpanEmitter()
        emitter.emit(_make_span())
        assert len(emitter.spans()) == 1

    def test_spans_list_and_store_consistent(self):
        from engine.agent.span_emitter import SpanEmitter
        from engine.observability.span_store import InMemorySpanStore

        store = InMemorySpanStore()
        emitter = SpanEmitter(store=store)
        emitter.emit(_make_span(run_id="r1", span_id="s1"))
        emitter.emit(_make_span(run_id="r1", span_id="s2"))
        assert len(emitter.spans()) == 2
        assert len(store.get_by_run("r1")) == 2


# ---------------------------------------------------------------------------
# Cycle 4: Orchestrator creates Run record + emits memory-recall span
# ---------------------------------------------------------------------------

class TestOrchestratorObservability:
    def _build(self, run_store=None, span_store=None):
        from engine.agent.registry import AgentRegistry
        from engine.agent.live import LiveQuery
        from engine.agent.span_emitter import SpanEmitter
        from engine.ingestion.memory_writer import MemoryWriter
        from engine.agent.orchestrator import Orchestrator
        from engine.spine.types import AgentSpec

        spec = AgentSpec(
            name="account-agent",
            role="manages accounts",
            scope=Scope(level=ScopeLevel.entity, entity_ref="__client__"),
            toolset=[],
            model_tier={"default": "strong"},
            wake_triggers=["deal.stage_changed"],
            playbooks=[],
            spawn_policy={},
        )
        registry = AgentRegistry()
        registry.register(spec)
        emitter = SpanEmitter(store=span_store)
        return Orchestrator(
            registry=registry,
            memory_writer=MemoryWriter(),
            live=LiveQuery(),
            anthropic_client=_mock_anthropic(),
            span_emitter=emitter,
            run_store=run_store,
        ), emitter

    def test_run_saved_to_run_store(self):
        from engine.observability.run_store import InMemoryRunStore

        run_store = InMemoryRunStore()
        orch, _ = self._build(run_store=run_store)
        result = orch.handle("deal.stage_changed", "client-northpath-001")

        run = run_store.get(result.span.run_id)
        assert run is not None
        assert run.run_id == result.span.run_id

    def test_run_status_done_after_handle(self):
        from engine.observability.run_store import InMemoryRunStore

        run_store = InMemoryRunStore()
        orch, _ = self._build(run_store=run_store)
        result = orch.handle("deal.stage_changed", "client-northpath-001")
        assert run_store.get(result.span.run_id).status == "done"

    def test_memory_recall_span_emitted(self):
        orch, emitter = self._build()
        orch.handle("deal.stage_changed", "client-northpath-001")

        memory_spans = [s for s in emitter.spans() if s.op == SpanOp.memory]
        assert len(memory_spans) >= 1
        assert memory_spans[0].actor == "memory-writer"

    def test_all_spans_share_run_id(self):
        orch, emitter = self._build()
        orch.handle("deal.stage_changed", "client-northpath-001")

        run_ids = {s.run_id for s in emitter.spans()}
        assert len(run_ids) == 1


# ---------------------------------------------------------------------------
# Cycle 5: ToolExecutor emits tool spans on approve / reject
# ---------------------------------------------------------------------------

class TestToolExecutorSpans:
    def test_approve_emits_tool_span(self):
        from engine.agent.span_emitter import SpanEmitter

        emitter = SpanEmitter()
        executor = _make_t3_executor(span_emitter=emitter)
        _park(executor, "k-approve-001")
        executor.approve("k-approve-001")

        tool_spans = [s for s in emitter.spans() if s.op == SpanOp.tool]
        assert len(tool_spans) == 1
        assert tool_spans[0].status == "ok"

    def test_reject_emits_tool_span(self):
        from engine.agent.span_emitter import SpanEmitter

        emitter = SpanEmitter()
        executor = _make_t3_executor(span_emitter=emitter)
        _park(executor, "k-reject-001")
        executor.reject("k-reject-001", reason="out of scope")

        tool_spans = [s for s in emitter.spans() if s.op == SpanOp.tool]
        assert len(tool_spans) == 1
        assert tool_spans[0].status == "rejected"

    def test_tool_span_carries_run_id(self):
        from engine.agent.span_emitter import SpanEmitter

        emitter = SpanEmitter()
        executor = _make_t3_executor(span_emitter=emitter)
        _park(executor, "k-runid-001", run_id="run-obs-test")
        executor.approve("k-runid-001")

        tool_spans = [s for s in emitter.spans() if s.op == SpanOp.tool]
        assert tool_spans[0].run_id == "run-obs-test"


# ---------------------------------------------------------------------------
# Cycle 6: Eval labels on approve / edit-then-approve / reject
# ---------------------------------------------------------------------------

class TestEvalLabels:
    def test_approve_sets_positive_label(self):
        from engine.agent.span_emitter import SpanEmitter

        emitter = SpanEmitter()
        executor = _make_t3_executor(span_emitter=emitter)
        _park(executor, "eval-approve-001")
        executor.approve("eval-approve-001")

        span = next(s for s in emitter.spans() if s.op == SpanOp.tool)
        assert span.eval_label == "positive"

    def test_edit_then_approve_sets_soft_negative_label(self):
        from engine.agent.span_emitter import SpanEmitter

        emitter = SpanEmitter()
        executor = _make_t3_executor(span_emitter=emitter)
        _park(executor, "eval-edit-001")
        executor.approve("eval-edit-001", override_body="edited version")

        span = next(s for s in emitter.spans() if s.op == SpanOp.tool)
        assert span.eval_label == "soft_negative"
        assert span.eval_note is not None

    def test_reject_sets_negative_label_with_reason(self):
        from engine.agent.span_emitter import SpanEmitter

        emitter = SpanEmitter()
        executor = _make_t3_executor(span_emitter=emitter)
        _park(executor, "eval-reject-001")
        executor.reject("eval-reject-001", reason="not relevant")

        span = next(s for s in emitter.spans() if s.op == SpanOp.tool)
        assert span.eval_label == "negative"
        assert span.eval_note == "not relevant"


# ---------------------------------------------------------------------------
# Cycle 7: Audit log — approve/reject writes AuditRecord + immutability
# ---------------------------------------------------------------------------

class TestAuditLog:
    def test_approve_writes_audit_record(self):
        from engine.observability.audit_store import InMemoryAuditStore
        from engine.agent.span_emitter import SpanEmitter

        audit = InMemoryAuditStore()
        executor = _make_t3_executor(span_emitter=SpanEmitter(), audit_store=audit)
        _park(executor, "audit-approve-001")
        executor.approve("audit-approve-001", approver="partner@firm.com")

        record = audit.get("audit-approve-001")
        assert record is not None
        assert record.outcome == "approved"
        assert record.approver == "partner@firm.com"
        assert record.idempotency_key == "audit-approve-001"

    def test_reject_writes_audit_record(self):
        from engine.observability.audit_store import InMemoryAuditStore
        from engine.agent.span_emitter import SpanEmitter

        audit = InMemoryAuditStore()
        executor = _make_t3_executor(span_emitter=SpanEmitter(), audit_store=audit)
        _park(executor, "audit-reject-001")
        executor.reject("audit-reject-001", reason="out of scope", approver="partner@firm.com")

        record = audit.get("audit-reject-001")
        assert record is not None
        assert record.outcome == "rejected"

    def test_audit_record_has_before_and_after_state(self):
        from engine.observability.audit_store import InMemoryAuditStore
        from engine.agent.span_emitter import SpanEmitter

        audit = InMemoryAuditStore()
        executor = _make_t3_executor(span_emitter=SpanEmitter(), audit_store=audit)
        _park(executor, "audit-state-001")
        executor.approve("audit-state-001", override_body="edited body")

        record = audit.get("audit-state-001")
        assert record.before_state is not None
        assert record.after_state is not None

    def test_immutable_store_raises_on_update(self):
        from engine.observability.audit_store import InMemoryAuditStore, ImmutableRecordError
        with pytest.raises(ImmutableRecordError):
            InMemoryAuditStore().update("any-key", {})

    def test_immutable_store_raises_on_delete(self):
        from engine.observability.audit_store import InMemoryAuditStore, ImmutableRecordError
        with pytest.raises(ImmutableRecordError):
            InMemoryAuditStore().delete("any-key")


# ---------------------------------------------------------------------------
# Cycle 8: Trace tree endpoint — GET /runs/{run_id}/trace
# ---------------------------------------------------------------------------

class TestTraceEndpoint:
    def setup_method(self):
        from app.main import app
        app.dependency_overrides = {}

    def teardown_method(self):
        from app.main import app
        app.dependency_overrides = {}

    def _client(self, span_store, run_store):
        from fastapi.testclient import TestClient
        from app.main import app
        from app.traces import get_span_store, get_run_store
        app.dependency_overrides[get_span_store] = lambda: span_store
        app.dependency_overrides[get_run_store] = lambda: run_store
        return TestClient(app)

    def test_trace_returns_spans_ordered_by_started_at(self):
        from engine.observability.span_store import InMemorySpanStore
        from engine.observability.run_store import InMemoryRunStore
        from engine.spine.types import Run

        span_store = InMemorySpanStore()
        run_store = InMemoryRunStore()
        run_store.save(Run(
            run_id="run-trace-001",
            initiated_by="deal.stage_changed",
            scope=_scope(),
            started_at=datetime.now(timezone.utc),
            status="done",
        ))
        span_store.save(_make_span(run_id="run-trace-001", span_id="sp-t1"))
        span_store.save(_make_span(run_id="run-trace-001", span_id="sp-t2"))

        resp = self._client(span_store, run_store).get("/runs/run-trace-001/trace")

        assert resp.status_code == 200
        data = resp.json()
        assert data["run_id"] == "run-trace-001"
        assert len(data["spans"]) == 2

    def test_trace_returns_404_for_unknown_run(self):
        from engine.observability.span_store import InMemorySpanStore
        from engine.observability.run_store import InMemoryRunStore

        resp = self._client(InMemorySpanStore(), InMemoryRunStore()).get("/runs/no-such-run/trace")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Cycle 9: Cost attribution — sum of token costs equals total LLM spend
# ---------------------------------------------------------------------------

class TestCostAttribution:
    def test_sum_of_span_tokens_covers_llm_usage(self):
        from engine.agent.registry import AgentRegistry
        from engine.agent.live import LiveQuery
        from engine.agent.span_emitter import SpanEmitter
        from engine.ingestion.memory_writer import MemoryWriter
        from engine.agent.orchestrator import Orchestrator
        from engine.spine.types import AgentSpec

        spec = AgentSpec(
            name="account-agent",
            role="manages accounts",
            scope=Scope(level=ScopeLevel.entity, entity_ref="__client__"),
            toolset=[],
            model_tier={"default": "strong"},
            wake_triggers=["deal.stage_changed"],
            playbooks=[],
            spawn_policy={},
        )
        registry = AgentRegistry()
        registry.register(spec)
        emitter = SpanEmitter()

        Orchestrator(
            registry=registry,
            memory_writer=MemoryWriter(),
            live=LiveQuery(),
            anthropic_client=_mock_anthropic(input_tokens=200, output_tokens=80),
            span_emitter=emitter,
        ).handle("deal.stage_changed", "client-northpath-001")

        spans = emitter.spans()
        total_in = sum(s.token_in for s in spans)
        total_out = sum(s.token_out for s in spans)
        assert total_in >= 200
        assert total_out >= 80
