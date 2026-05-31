"""
Slice 5: Tool registry, execution backbone, commitment gate, draft email T3 tool.
Tests describe observable behavior through public interfaces only.
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

def _make_spec(
    name: str = "test.tool",
    tier: AutonomyTier = AutonomyTier.T1,
    mode: ToolMode = ToolMode.read,
    scope_required: ScopeLevel = ScopeLevel.entity,
) -> ToolSpec:
    return ToolSpec(
        name=name,
        inputs={"data": "str"},
        system="test",
        mode=mode,
        tier=tier,
        scope_required=scope_required,
        reversible=True,
        side_effects=[],
    )


def _entity_scope(ref: str = "client-northpath-001") -> Scope:
    return Scope(level=ScopeLevel.entity, entity_ref=ref)


def _mock_anthropic_gate(tier_response: str = "T1"):
    client = MagicMock()
    resp = MagicMock()
    resp.content[0].text = f'{{"tier": "{tier_response}"}}'
    client.messages.create.return_value = resp
    return client


def _mock_anthropic_agent(draft_text: str = "Dear Team, following up."):
    client = MagicMock()
    resp = MagicMock()
    resp.content[0].text = draft_text
    resp.usage.input_tokens = 100
    resp.usage.output_tokens = 50
    client.messages.create.return_value = resp
    return client


# ---------------------------------------------------------------------------
# Cycle 1: ToolRegistry — get registered spec, raises ToolNotFound
# ---------------------------------------------------------------------------

class TestToolRegistry:
    def test_get_returns_registered_spec(self):
        from engine.tools.registry import ToolRegistry

        spec = _make_spec("test.read_data", tier=AutonomyTier.T0, mode=ToolMode.read)
        fn = lambda inputs, dry_run=False: "ok"

        registry = ToolRegistry()
        registry.register(spec, fn)

        got_spec, got_fn = registry.get("test.read_data")
        assert got_spec.name == "test.read_data"
        assert got_fn({}) == "ok"

    def test_raises_tool_not_found_for_unknown_name(self):
        from engine.tools.registry import ToolRegistry, ToolNotFound

        registry = ToolRegistry()
        with pytest.raises(ToolNotFound):
            registry.get("nonexistent.tool")

    def test_second_register_overwrites_first(self):
        from engine.tools.registry import ToolRegistry

        spec = _make_spec("dup.tool")
        fn_v1 = lambda inputs, dry_run=False: "v1"
        fn_v2 = lambda inputs, dry_run=False: "v2"

        registry = ToolRegistry()
        registry.register(spec, fn_v1)
        registry.register(spec, fn_v2)

        _, got_fn = registry.get("dup.tool")
        assert got_fn({}) == "v2"


# ---------------------------------------------------------------------------
# Cycle 2: Scope enforcement — InsufficientScope raised pre-execute
# ---------------------------------------------------------------------------

class TestScopeEnforcement:
    def test_user_private_scope_cannot_call_entity_tool(self):
        from engine.tools.registry import ToolRegistry
        from engine.tools.executor import ToolExecutor, InsufficientScope

        spec = _make_spec("test.entity_tool", tier=AutonomyTier.T1, scope_required=ScopeLevel.entity)
        called = []
        fn = lambda inputs, dry_run=False: called.append(True) or "result"

        registry = ToolRegistry()
        registry.register(spec, fn)
        executor = ToolExecutor(registry)

        with pytest.raises(InsufficientScope):
            executor.execute(
                "test.entity_tool",
                inputs={},
                scope=Scope(level=ScopeLevel.user_private, user_ref="user-1"),
                requesting_agent="account-agent",
                principal="user-1",
                rationale="test",
                idempotency_key="key-001",
            )

        assert called == []

    def test_entity_scope_can_call_entity_tool(self):
        from engine.tools.registry import ToolRegistry
        from engine.tools.executor import ToolExecutor

        spec = _make_spec("test.entity_tool2", tier=AutonomyTier.T1, scope_required=ScopeLevel.entity)
        fn = lambda inputs, dry_run=False: "result"

        registry = ToolRegistry()
        registry.register(spec, fn)
        executor = ToolExecutor(registry)

        result = executor.execute(
            "test.entity_tool2",
            inputs={},
            scope=_entity_scope(),
            requesting_agent="account-agent",
            principal="client-northpath-001",
            rationale="test",
            idempotency_key="key-002",
        )
        assert result == "result"

    def test_org_scope_can_call_entity_tool(self):
        from engine.tools.registry import ToolRegistry
        from engine.tools.executor import ToolExecutor

        spec = _make_spec("test.entity_tool3", tier=AutonomyTier.T1, scope_required=ScopeLevel.entity)
        fn = lambda inputs, dry_run=False: "ok"

        registry = ToolRegistry()
        registry.register(spec, fn)
        executor = ToolExecutor(registry)

        result = executor.execute(
            "test.entity_tool3",
            inputs={},
            scope=Scope(level=ScopeLevel.org),
            requesting_agent="admin-agent",
            principal="org",
            rationale="test",
            idempotency_key="key-003",
        )
        assert result == "ok"

    def test_entity_scope_cannot_call_org_tool(self):
        from engine.tools.registry import ToolRegistry
        from engine.tools.executor import ToolExecutor, InsufficientScope

        spec = _make_spec("test.org_tool", tier=AutonomyTier.T0, scope_required=ScopeLevel.org)
        fn = lambda inputs, dry_run=False: "result"

        registry = ToolRegistry()
        registry.register(spec, fn)
        executor = ToolExecutor(registry)

        with pytest.raises(InsufficientScope):
            executor.execute(
                "test.org_tool",
                inputs={},
                scope=_entity_scope(),
                requesting_agent="account-agent",
                principal="client-northpath-001",
                rationale="test",
                idempotency_key="key-004",
            )


# ---------------------------------------------------------------------------
# Cycle 3: T0 and T1 tool calls execute immediately
# ---------------------------------------------------------------------------

class TestImmediateExecution:
    def _executor_with(self, spec: ToolSpec, fn):
        from engine.tools.registry import ToolRegistry
        from engine.tools.executor import ToolExecutor

        registry = ToolRegistry()
        registry.register(spec, fn)
        return ToolExecutor(registry)

    def test_t0_tool_executes_and_returns_result(self):
        spec = _make_spec("test.t0", tier=AutonomyTier.T0, mode=ToolMode.read)
        fn = lambda inputs, dry_run=False: f"read:{inputs.get('id')}"

        executor = self._executor_with(spec, fn)
        result = executor.execute(
            "test.t0",
            inputs={"id": "deal-1"},
            scope=_entity_scope(),
            requesting_agent="account-agent",
            principal="client-northpath-001",
            rationale="read deal",
            idempotency_key="key-t0-001",
        )
        assert result == "read:deal-1"

    def test_t1_tool_executes_and_returns_result(self):
        spec = _make_spec("test.t1", tier=AutonomyTier.T1, mode=ToolMode.write)
        fn = lambda inputs, dry_run=False: "written"

        executor = self._executor_with(spec, fn)
        result = executor.execute(
            "test.t1",
            inputs={},
            scope=_entity_scope(),
            requesting_agent="account-agent",
            principal="client-northpath-001",
            rationale="safe write",
            idempotency_key="key-t1-001",
        )
        assert result == "written"

    def test_t0_and_t1_do_not_return_parked_request(self):
        spec = _make_spec("test.t1b", tier=AutonomyTier.T1)
        fn = lambda inputs, dry_run=False: "immediate"

        executor = self._executor_with(spec, fn)
        result = executor.execute(
            "test.t1b",
            inputs={},
            scope=_entity_scope(),
            requesting_agent="account-agent",
            principal="client-northpath-001",
            rationale="test",
            idempotency_key="key-t1b-001",
        )
        assert not isinstance(result, ParkedApprovalRequest)


# ---------------------------------------------------------------------------
# Cycle 4: T3 tool call emits ParkedApprovalRequest and suspends
# ---------------------------------------------------------------------------

class TestT3Parking:
    def _t3_executor(self, preview_body: str = "Email body preview"):
        from engine.tools.registry import ToolRegistry
        from engine.tools.executor import ToolExecutor

        spec = _make_spec("test.t3_write", tier=AutonomyTier.T3, mode=ToolMode.write)
        fn = lambda inputs, dry_run=False: preview_body

        registry = ToolRegistry()
        registry.register(spec, fn)
        return ToolExecutor(registry)

    def test_t3_returns_parked_approval_request(self):
        executor = self._t3_executor()
        result = executor.execute(
            "test.t3_write",
            inputs={"body": "send this"},
            scope=_entity_scope(),
            requesting_agent="account-agent",
            principal="client-northpath-001",
            rationale="escalated",
            idempotency_key="key-t3-001",
        )
        assert isinstance(result, ParkedApprovalRequest)

    def test_t3_does_not_call_fn_for_side_effects(self):
        """The fn is called only for the preview (dry_run=True), not to execute."""
        from engine.tools.registry import ToolRegistry
        from engine.tools.executor import ToolExecutor

        real_calls = []
        spec = _make_spec("test.t3_track", tier=AutonomyTier.T3, mode=ToolMode.write)

        def fn(inputs, dry_run=False):
            real_calls.append(dry_run)
            return "preview"

        registry = ToolRegistry()
        registry.register(spec, fn)
        executor = ToolExecutor(registry)

        executor.execute(
            "test.t3_track",
            inputs={},
            scope=_entity_scope(),
            requesting_agent="account-agent",
            principal="client-northpath-001",
            rationale="track",
            idempotency_key="key-t3-track-001",
        )

        # fn called exactly once with dry_run=True (preview), never with dry_run=False (execute)
        assert real_calls == [True]

    def test_t3_parked_request_has_correct_fields(self):
        executor = self._t3_executor(preview_body="Dear Client, confirming scope...")

        result = executor.execute(
            "test.t3_write",
            inputs={"body": "Dear Client, confirming scope..."},
            scope=_entity_scope(),
            requesting_agent="account-agent",
            principal="client-northpath-001",
            rationale="commitment email detected",
            idempotency_key="key-t3-fields-001",
        )

        assert isinstance(result, ParkedApprovalRequest)
        assert result.action == "test.t3_write"
        assert result.preview == "Dear Client, confirming scope..."
        assert result.requesting_agent == "account-agent"
        assert result.principal == "client-northpath-001"
        assert result.rationale == "commitment email detected"
        assert result.idempotency_key == "key-t3-fields-001"
        assert result.scope.level == ScopeLevel.entity


# ---------------------------------------------------------------------------
# Cycle 5: Idempotency — same key submitted twice → parked once
# ---------------------------------------------------------------------------

class TestIdempotency:
    def _t3_executor(self):
        from engine.tools.registry import ToolRegistry
        from engine.tools.executor import ToolExecutor

        call_count = []
        spec = _make_spec("test.idem", tier=AutonomyTier.T3, mode=ToolMode.write)

        def fn(inputs, dry_run=False):
            call_count.append(1)
            return "preview"

        registry = ToolRegistry()
        registry.register(spec, fn)
        return ToolExecutor(registry), call_count

    def test_same_key_returns_existing_parked_request(self):
        executor, _ = self._t3_executor()

        first = executor.execute(
            "test.idem",
            inputs={},
            scope=_entity_scope(),
            requesting_agent="account-agent",
            principal="client-northpath-001",
            rationale="first",
            idempotency_key="dupe-key-001",
        )
        second = executor.execute(
            "test.idem",
            inputs={},
            scope=_entity_scope(),
            requesting_agent="account-agent",
            principal="client-northpath-001",
            rationale="second",
            idempotency_key="dupe-key-001",
        )

        assert isinstance(first, ParkedApprovalRequest)
        assert isinstance(second, ParkedApprovalRequest)
        assert first.idempotency_key == second.idempotency_key

    def test_same_key_calls_fn_only_once(self):
        executor, call_count = self._t3_executor()

        executor.execute(
            "test.idem",
            inputs={},
            scope=_entity_scope(),
            requesting_agent="account-agent",
            principal="client-northpath-001",
            rationale="first",
            idempotency_key="dupe-key-002",
        )
        executor.execute(
            "test.idem",
            inputs={},
            scope=_entity_scope(),
            requesting_agent="account-agent",
            principal="client-northpath-001",
            rationale="second",
            idempotency_key="dupe-key-002",
        )

        assert len(call_count) == 1

    def test_different_keys_are_independent(self):
        executor, call_count = self._t3_executor()

        r1 = executor.execute(
            "test.idem",
            inputs={},
            scope=_entity_scope(),
            requesting_agent="account-agent",
            principal="client-northpath-001",
            rationale="first",
            idempotency_key="key-A",
        )
        r2 = executor.execute(
            "test.idem",
            inputs={},
            scope=_entity_scope(),
            requesting_agent="account-agent",
            principal="client-northpath-001",
            rationale="second",
            idempotency_key="key-B",
        )

        assert r1.idempotency_key == "key-A"
        assert r2.idempotency_key == "key-B"
        assert len(call_count) == 2


# ---------------------------------------------------------------------------
# Cycle 6: CommitmentGate — classifies commitment vs routine email
# ---------------------------------------------------------------------------

class TestCommitmentGate:
    def test_commitment_email_classified_as_t3(self):
        from engine.tools.commitment_gate import CommitmentGate

        gate = CommitmentGate(_mock_anthropic_gate(tier_response="T3"))
        tier = gate.classify(
            "Dear Northpath, we confirm the scope of the Q3 audit engagement is 200 hours "
            "at $250/hr, commencing June 1, with deliverables due August 31."
        )
        assert tier == AutonomyTier.T3

    def test_routine_email_classified_as_t1(self):
        from engine.tools.commitment_gate import CommitmentGate

        gate = CommitmentGate(_mock_anthropic_gate(tier_response="T1"))
        tier = gate.classify(
            "Hi team, just following up to see if you had a chance to review the proposal. "
            "Happy to jump on a call this week."
        )
        assert tier == AutonomyTier.T1

    def test_gate_uses_haiku_model(self):
        from engine.tools.commitment_gate import CommitmentGate, GATE_MODEL

        client = _mock_anthropic_gate("T3")
        CommitmentGate(client).classify("Any draft text here.")

        call_kwargs = client.messages.create.call_args
        assert call_kwargs.kwargs["model"] == GATE_MODEL

    def test_gate_defaults_to_t3_on_unparseable_response(self):
        """Safe default: when classification fails, escalate rather than pass through."""
        from engine.tools.commitment_gate import CommitmentGate

        client = MagicMock()
        resp = MagicMock()
        resp.content[0].text = "I cannot determine this."  # not valid JSON
        client.messages.create.return_value = resp

        gate = CommitmentGate(client)
        tier = gate.classify("Some email draft.")
        assert tier == AutonomyTier.T3


# ---------------------------------------------------------------------------
# Cycle 7: DraftEmailTool — preview/dry-run returns body, SPEC has correct tier
# ---------------------------------------------------------------------------

class TestDraftEmailTool:
    def test_dry_run_returns_email_body_without_side_effects(self):
        from engine.tools.implementations.draft_email import DraftEmailTool

        tool = DraftEmailTool()
        body = "Dear Northpath, following up on your proposal."
        result = tool.execute(
            {"to": "northpath@example.com", "subject": "Following up", "body": body},
            dry_run=True,
        )
        assert result == body

    def test_execute_returns_body(self):
        from engine.tools.implementations.draft_email import DraftEmailTool

        tool = DraftEmailTool()
        body = "Hi, just checking in on the Q3 audit timeline."
        result = tool.execute(
            {"to": "client@example.com", "subject": "Q3 Audit", "body": body},
        )
        assert result == body

    def test_spec_is_t3_write_entity_irreversible(self):
        from engine.tools.implementations.draft_email import SPEC

        assert SPEC.tier == AutonomyTier.T3
        assert SPEC.mode == ToolMode.write
        assert SPEC.scope_required == ScopeLevel.entity
        assert SPEC.reversible is False

    def test_spec_name_is_gmail_draft_email(self):
        from engine.tools.implementations.draft_email import SPEC

        assert SPEC.name == "gmail.draft_email"


# ---------------------------------------------------------------------------
# Cycle 8: End-to-end — AccountAgent → executor → T3 park → ParkedApprovalRequest
# ---------------------------------------------------------------------------

class TestEndToEndT3Park:
    def _build_executor(self):
        from engine.tools.registry import ToolRegistry
        from engine.tools.executor import ToolExecutor
        from engine.tools.implementations.draft_email import DraftEmailTool, SPEC

        tool = DraftEmailTool()
        registry = ToolRegistry()
        registry.register(SPEC, tool.execute)
        return ToolExecutor(registry)

    def test_account_agent_returns_parked_request_via_executor(self):
        from engine.agent.agents.account import AccountAgent

        executor = self._build_executor()
        agent_client = _mock_anthropic_agent(
            draft_text="Dear Northpath, confirming scope at 200 hours commencing June 1."
        )

        result = AccountAgent().run(
            entity_ref="client-northpath-001",
            memory_records=[],
            live_context={"current_stage": "Proposal", "days_in_stage": 21},
            scope=_entity_scope(),
            run_id="run-e2e-001",
            anthropic_client=agent_client,
            tool_executor=executor,
            idempotency_key="e2e-park-001",
        )

        assert result.parked is not None
        assert isinstance(result.parked, ParkedApprovalRequest)
        assert result.parked.action == "gmail.draft_email"
        assert result.parked.idempotency_key == "e2e-park-001"

    def test_parked_preview_contains_draft_body(self):
        from engine.agent.agents.account import AccountAgent

        draft = "Hi, we confirm deliverables due August 31."
        executor = self._build_executor()

        result = AccountAgent().run(
            entity_ref="client-northpath-001",
            memory_records=[],
            live_context={"current_stage": "Proposal", "days_in_stage": 21},
            scope=_entity_scope(),
            run_id="run-e2e-002",
            anthropic_client=_mock_anthropic_agent(draft_text=draft),
            tool_executor=executor,
            idempotency_key="e2e-park-002",
        )

        assert result.parked.preview == draft

    def test_draft_still_set_on_result_when_parked(self):
        """Span and draft are preserved on AgentStepResult even when parked."""
        from engine.agent.agents.account import AccountAgent

        executor = self._build_executor()
        draft = "Routine check-in."

        result = AccountAgent().run(
            entity_ref="client-northpath-001",
            memory_records=[],
            live_context={"current_stage": "Proposal", "days_in_stage": 21},
            scope=_entity_scope(),
            run_id="run-e2e-003",
            anthropic_client=_mock_anthropic_agent(draft_text=draft),
            tool_executor=executor,
            idempotency_key="e2e-park-003",
        )

        assert result.draft == draft
        assert result.span is not None

    def test_account_agent_without_executor_behaves_as_before(self):
        """Backward-compat: no executor → parked is None, draft returned as before."""
        from engine.agent.agents.account import AccountAgent

        result = AccountAgent().run(
            entity_ref="client-northpath-001",
            memory_records=[],
            live_context={"current_stage": "Proposal", "days_in_stage": 21},
            scope=_entity_scope(),
            run_id="run-e2e-004",
            anthropic_client=_mock_anthropic_agent(),
        )

        assert result.parked is None
        assert isinstance(result.draft, str)
        assert len(result.draft) > 0


# ---------------------------------------------------------------------------
# Cycle 9: on_park callback — fires once on T3 park, never on duplicates or T0/T1
# ---------------------------------------------------------------------------

class TestOnParkCallback:
    def _t3_executor(self, on_park=None):
        from engine.tools.registry import ToolRegistry
        from engine.tools.executor import ToolExecutor

        spec = _make_spec("test.cb_t3", tier=AutonomyTier.T3, mode=ToolMode.write)
        fn = lambda inputs, dry_run=False: "preview"

        registry = ToolRegistry()
        registry.register(spec, fn)
        return ToolExecutor(registry, on_park=on_park)

    def test_callback_fires_when_t3_parks(self):
        fired = []
        executor = self._t3_executor(on_park=lambda req: fired.append(req))

        executor.execute(
            "test.cb_t3",
            inputs={},
            scope=_entity_scope(),
            requesting_agent="account-agent",
            principal="client-northpath-001",
            rationale="test",
            idempotency_key="cb-key-001",
        )

        assert len(fired) == 1
        assert isinstance(fired[0], ParkedApprovalRequest)

    def test_callback_receives_correct_parked_request(self):
        received = []
        executor = self._t3_executor(on_park=lambda req: received.append(req))

        executor.execute(
            "test.cb_t3",
            inputs={},
            scope=_entity_scope(),
            requesting_agent="account-agent",
            principal="client-northpath-001",
            rationale="commitment detected",
            idempotency_key="cb-key-002",
        )

        req = received[0]
        assert req.action == "test.cb_t3"
        assert req.idempotency_key == "cb-key-002"
        assert req.rationale == "commitment detected"
        assert req.principal == "client-northpath-001"

    def test_callback_not_fired_on_idempotent_duplicate(self):
        fired = []
        executor = self._t3_executor(on_park=lambda req: fired.append(req))

        executor.execute(
            "test.cb_t3",
            inputs={},
            scope=_entity_scope(),
            requesting_agent="account-agent",
            principal="client-northpath-001",
            rationale="first",
            idempotency_key="cb-dupe-key",
        )
        executor.execute(
            "test.cb_t3",
            inputs={},
            scope=_entity_scope(),
            requesting_agent="account-agent",
            principal="client-northpath-001",
            rationale="second",
            idempotency_key="cb-dupe-key",
        )

        assert len(fired) == 1

    def test_callback_not_fired_for_t0_tool(self):
        from engine.tools.registry import ToolRegistry
        from engine.tools.executor import ToolExecutor

        fired = []
        spec = _make_spec("test.cb_t0", tier=AutonomyTier.T0, mode=ToolMode.read)
        fn = lambda inputs, dry_run=False: "read-result"

        registry = ToolRegistry()
        registry.register(spec, fn)
        executor = ToolExecutor(registry, on_park=lambda req: fired.append(req))

        executor.execute(
            "test.cb_t0",
            inputs={},
            scope=_entity_scope(),
            requesting_agent="account-agent",
            principal="client-northpath-001",
            rationale="read",
            idempotency_key="cb-t0-key",
        )

        assert fired == []

    def test_callback_not_fired_for_t1_tool(self):
        from engine.tools.registry import ToolRegistry
        from engine.tools.executor import ToolExecutor

        fired = []
        spec = _make_spec("test.cb_t1", tier=AutonomyTier.T1, mode=ToolMode.write)
        fn = lambda inputs, dry_run=False: "written"

        registry = ToolRegistry()
        registry.register(spec, fn)
        executor = ToolExecutor(registry, on_park=lambda req: fired.append(req))

        executor.execute(
            "test.cb_t1",
            inputs={},
            scope=_entity_scope(),
            requesting_agent="account-agent",
            principal="client-northpath-001",
            rationale="safe write",
            idempotency_key="cb-t1-key",
        )

        assert fired == []


# ---------------------------------------------------------------------------
# Cycle 10: list_pending() returns all currently parked requests
# ---------------------------------------------------------------------------

class TestListPending:
    def _t3_executor(self):
        from engine.tools.registry import ToolRegistry
        from engine.tools.executor import ToolExecutor

        spec = _make_spec("test.lp_t3", tier=AutonomyTier.T3, mode=ToolMode.write)
        fn = lambda inputs, dry_run=False: "preview"

        registry = ToolRegistry()
        registry.register(spec, fn)
        return ToolExecutor(registry)

    def test_list_pending_empty_before_any_park(self):
        executor = self._t3_executor()
        assert executor.list_pending() == []

    def test_list_pending_returns_parked_request(self):
        executor = self._t3_executor()

        executor.execute(
            "test.lp_t3",
            inputs={},
            scope=_entity_scope(),
            requesting_agent="account-agent",
            principal="client-northpath-001",
            rationale="test",
            idempotency_key="lp-key-001",
        )

        pending = executor.list_pending()
        assert len(pending) == 1
        assert pending[0].idempotency_key == "lp-key-001"

    def test_list_pending_returns_all_distinct_parked_requests(self):
        executor = self._t3_executor()

        for key in ("lp-multi-001", "lp-multi-002", "lp-multi-003"):
            executor.execute(
                "test.lp_t3",
                inputs={},
                scope=_entity_scope(),
                requesting_agent="account-agent",
                principal="client-northpath-001",
                rationale="test",
                idempotency_key=key,
            )

        keys = {r.idempotency_key for r in executor.list_pending()}
        assert keys == {"lp-multi-001", "lp-multi-002", "lp-multi-003"}


# ---------------------------------------------------------------------------
# Cycle 11: approve() calls fn with dry_run=False and removes request from pending
# ---------------------------------------------------------------------------

class TestApprove:
    def _t3_executor(self, fn=None):
        from engine.tools.registry import ToolRegistry
        from engine.tools.executor import ToolExecutor

        spec = _make_spec("test.ap_t3", tier=AutonomyTier.T3, mode=ToolMode.write)
        if fn is None:
            fn = lambda inputs, dry_run=False: f"executed:{inputs.get('body','')}"

        registry = ToolRegistry()
        registry.register(spec, fn)
        return ToolExecutor(registry)

    def _park(self, executor, key="ap-key-001", inputs=None):
        executor.execute(
            "test.ap_t3",
            inputs=inputs or {"body": "original body"},
            scope=_entity_scope(),
            requesting_agent="account-agent",
            principal="client-northpath-001",
            rationale="test",
            idempotency_key=key,
        )

    def test_approve_returns_execution_result(self):
        executor = self._t3_executor()
        self._park(executor)
        result = executor.approve("ap-key-001")
        assert result == "executed:original body"

    def test_approve_removes_request_from_pending(self):
        executor = self._t3_executor()
        self._park(executor)
        executor.approve("ap-key-001")
        assert executor.list_pending() == []

    def test_approve_calls_fn_with_dry_run_false(self):
        calls = []

        def fn(inputs, dry_run=False):
            calls.append(dry_run)
            return "result"

        executor = self._t3_executor(fn=fn)
        self._park(executor)
        calls.clear()  # discard the dry_run=True preview call made during park
        executor.approve("ap-key-001")

        assert calls == [False]

    def test_approve_raises_for_unknown_key(self):
        executor = self._t3_executor()
        with pytest.raises(KeyError):
            executor.approve("nonexistent-key")


# ---------------------------------------------------------------------------
# Cycle 12: approve() with override_body uses modified body, not original
# ---------------------------------------------------------------------------

class TestApproveOverride:
    def _executor_and_park(self, key="ov-key-001"):
        from engine.tools.registry import ToolRegistry
        from engine.tools.executor import ToolExecutor

        spec = _make_spec("test.ov_t3", tier=AutonomyTier.T3, mode=ToolMode.write)
        fn = lambda inputs, dry_run=False: inputs.get("body", "")

        registry = ToolRegistry()
        registry.register(spec, fn)
        executor = ToolExecutor(registry)
        executor.execute(
            "test.ov_t3",
            inputs={"body": "original draft"},
            scope=_entity_scope(),
            requesting_agent="account-agent",
            principal="client-northpath-001",
            rationale="test",
            idempotency_key=key,
        )
        return executor

    def test_override_body_replaces_original_in_execution(self):
        executor = self._executor_and_park()
        result = executor.approve("ov-key-001", override_body="edited draft")
        assert result == "edited draft"

    def test_no_override_uses_original_inputs(self):
        executor = self._executor_and_park("ov-key-002")
        result = executor.approve("ov-key-002")
        assert result == "original draft"


# ---------------------------------------------------------------------------
# Cycle 13: approve() is idempotent — fn called once, second returns same result
# ---------------------------------------------------------------------------

class TestApproveIdempotency:
    def _executor_and_park(self):
        from engine.tools.registry import ToolRegistry
        from engine.tools.executor import ToolExecutor

        calls = []
        spec = _make_spec("test.idem_ap", tier=AutonomyTier.T3, mode=ToolMode.write)

        def fn(inputs, dry_run=False):
            calls.append(dry_run)
            return "executed-result"

        registry = ToolRegistry()
        registry.register(spec, fn)
        executor = ToolExecutor(registry)
        executor.execute(
            "test.idem_ap",
            inputs={},
            scope=_entity_scope(),
            requesting_agent="account-agent",
            principal="client-northpath-001",
            rationale="test",
            idempotency_key="idem-ap-key",
        )
        calls.clear()
        return executor, calls

    def test_approve_twice_returns_same_result(self):
        executor, _ = self._executor_and_park()
        first = executor.approve("idem-ap-key")
        second = executor.approve("idem-ap-key")
        assert first == second == "executed-result"

    def test_approve_twice_calls_fn_only_once(self):
        executor, calls = self._executor_and_park()
        executor.approve("idem-ap-key")
        executor.approve("idem-ap-key")
        assert len(calls) == 1


# ---------------------------------------------------------------------------
# Cycle 14: reject() removes request from pending; idempotent; unknown key raises
# ---------------------------------------------------------------------------

class TestReject:
    def _executor_and_park(self, key="rj-key-001"):
        from engine.tools.registry import ToolRegistry
        from engine.tools.executor import ToolExecutor

        spec = _make_spec("test.rj_t3", tier=AutonomyTier.T3, mode=ToolMode.write)
        fn = lambda inputs, dry_run=False: "result"

        registry = ToolRegistry()
        registry.register(spec, fn)
        executor = ToolExecutor(registry)
        executor.execute(
            "test.rj_t3",
            inputs={},
            scope=_entity_scope(),
            requesting_agent="account-agent",
            principal="client-northpath-001",
            rationale="test",
            idempotency_key=key,
        )
        return executor

    def test_reject_removes_from_pending(self):
        executor = self._executor_and_park()
        executor.reject("rj-key-001", reason="not appropriate")
        assert executor.list_pending() == []

    def test_reject_idempotent_second_call_does_not_raise(self):
        executor = self._executor_and_park("rj-key-002")
        executor.reject("rj-key-002", reason="first")
        executor.reject("rj-key-002", reason="second")  # must not raise

    def test_reject_unknown_key_raises(self):
        executor = self._executor_and_park("rj-key-003")
        with pytest.raises(KeyError):
            executor.reject("nonexistent-key", reason="test")
