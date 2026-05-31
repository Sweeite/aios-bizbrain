"""
Slice 6: Approval Queue — FastAPI endpoints.
Tests exercise the HTTP interface only; a fresh ToolExecutor is injected per test.
"""
import pytest
from fastapi.testclient import TestClient

from engine.spine.types import AutonomyTier, Scope, ScopeLevel, ToolMode, ToolSpec
from engine.tools.registry import ToolRegistry
from engine.tools.executor import ToolExecutor


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_t3_spec(name: str = "test.aq_t3") -> ToolSpec:
    return ToolSpec(
        name=name,
        inputs={"body": "str"},
        system="test",
        mode=ToolMode.write,
        tier=AutonomyTier.T3,
        scope_required=ScopeLevel.entity,
        reversible=False,
        side_effects=[],
    )


def _entity_scope(ref: str = "client-northpath-001") -> Scope:
    return Scope(level=ScopeLevel.entity, entity_ref=ref)


def _make_executor(fn=None, spec_name: str = "test.aq_t3") -> ToolExecutor:
    if fn is None:
        fn = lambda inputs, dry_run=False: inputs.get("body", "sent")
    registry = ToolRegistry()
    registry.register(_make_t3_spec(spec_name), fn)
    return ToolExecutor(registry)


def _park(executor: ToolExecutor, key: str, inputs: dict | None = None, spec_name: str = "test.aq_t3"):
    executor.execute(
        spec_name,
        inputs=inputs or {"body": "draft body"},
        scope=_entity_scope(),
        requesting_agent="account-agent",
        principal="client-northpath-001",
        rationale="commitment detected",
        idempotency_key=key,
    )


def _client(executor: ToolExecutor) -> TestClient:
    from app.main import app
    from app.deps import get_executor
    app.dependency_overrides[get_executor] = lambda: executor
    return TestClient(app)


# ---------------------------------------------------------------------------
# Cycle A: GET /approvals returns 200 with empty list when nothing is parked
# ---------------------------------------------------------------------------

class TestListApprovals:
    def test_empty_queue_returns_200_and_empty_list(self):
        executor = _make_executor()
        client = _client(executor)
        resp = client.get("/approvals")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_parked_request_appears_in_list(self):
        executor = _make_executor()
        _park(executor, "list-key-001")
        client = _client(executor)

        resp = client.get("/approvals")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["idempotency_key"] == "list-key-001"

    def test_list_includes_all_fields(self):
        executor = _make_executor()
        _park(executor, "list-fields-001", inputs={"body": "Hello client"})
        client = _client(executor)

        data = client.get("/approvals").json()
        item = data[0]
        assert item["action"] == "test.aq_t3"
        assert item["preview"] == "Hello client"
        assert item["rationale"] == "commitment detected"
        assert item["requesting_agent"] == "account-agent"
        assert item["principal"] == "client-northpath-001"


# ---------------------------------------------------------------------------
# Cycle C: POST /approvals/{key}/approve → 200, removed from queue
# ---------------------------------------------------------------------------

class TestApproveEndpoint:
    def test_approve_returns_200_and_approved_status(self):
        executor = _make_executor()
        _park(executor, "ap-ep-001")
        client = _client(executor)

        resp = client.post("/approvals/ap-ep-001/approve")
        assert resp.status_code == 200
        assert resp.json()["status"] == "approved"

    def test_approve_removes_request_from_queue(self):
        executor = _make_executor()
        _park(executor, "ap-ep-002")
        client = _client(executor)

        client.post("/approvals/ap-ep-002/approve")
        assert client.get("/approvals").json() == []

    def test_approve_result_contains_execution_output(self):
        executor = _make_executor()
        _park(executor, "ap-ep-003", inputs={"body": "nudge email"})
        client = _client(executor)

        resp = client.post("/approvals/ap-ep-003/approve")
        assert resp.json()["result"] == "nudge email"


# ---------------------------------------------------------------------------
# Cycle D: Approve twice → 200 both times, fn called once
# ---------------------------------------------------------------------------

class TestApproveIdempotencyEndpoint:
    def test_approve_twice_both_return_200(self):
        executor = _make_executor()
        _park(executor, "idem-ep-001")
        client = _client(executor)

        r1 = client.post("/approvals/idem-ep-001/approve")
        r2 = client.post("/approvals/idem-ep-001/approve")
        assert r1.status_code == 200
        assert r2.status_code == 200

    def test_approve_twice_same_result(self):
        executor = _make_executor()
        _park(executor, "idem-ep-002", inputs={"body": "the body"})
        client = _client(executor)

        r1 = client.post("/approvals/idem-ep-002/approve")
        r2 = client.post("/approvals/idem-ep-002/approve")
        assert r1.json()["result"] == r2.json()["result"]

    def test_approve_twice_fn_called_once(self):
        calls = []

        def fn(inputs, dry_run=False):
            calls.append(dry_run)
            return "result"

        executor = _make_executor(fn=fn)
        _park(executor, "idem-ep-003")
        client = _client(executor)
        calls.clear()

        client.post("/approvals/idem-ep-003/approve")
        client.post("/approvals/idem-ep-003/approve")
        assert len(calls) == 1


# ---------------------------------------------------------------------------
# Cycle E: Edit-then-approve → override body is what executes
# ---------------------------------------------------------------------------

class TestEditApproveEndpoint:
    def test_override_body_used_in_execution(self):
        executor = _make_executor()
        _park(executor, "edit-ep-001", inputs={"body": "original"})
        client = _client(executor)

        resp = client.post("/approvals/edit-ep-001/approve", json={"body": "edited version"})
        assert resp.status_code == 200
        assert resp.json()["result"] == "edited version"

    def test_no_body_field_uses_original(self):
        executor = _make_executor()
        _park(executor, "edit-ep-002", inputs={"body": "original"})
        client = _client(executor)

        resp = client.post("/approvals/edit-ep-002/approve", json={})
        assert resp.json()["result"] == "original"


# ---------------------------------------------------------------------------
# Cycle F: POST /approvals/{key}/reject → 200, removed from queue
# ---------------------------------------------------------------------------

class TestRejectEndpoint:
    def test_reject_returns_200_and_rejected_status(self):
        executor = _make_executor()
        _park(executor, "rj-ep-001")
        client = _client(executor)

        resp = client.post("/approvals/rj-ep-001/reject", json={"reason": "not appropriate"})
        assert resp.status_code == 200
        assert resp.json()["status"] == "rejected"

    def test_reject_removes_from_queue(self):
        executor = _make_executor()
        _park(executor, "rj-ep-002")
        client = _client(executor)

        client.post("/approvals/rj-ep-002/reject", json={"reason": "out of scope"})
        assert client.get("/approvals").json() == []

    def test_reject_twice_both_200(self):
        executor = _make_executor()
        _park(executor, "rj-ep-003")
        client = _client(executor)

        r1 = client.post("/approvals/rj-ep-003/reject", json={"reason": "first"})
        r2 = client.post("/approvals/rj-ep-003/reject", json={"reason": "second"})
        assert r1.status_code == 200
        assert r2.status_code == 200


# ---------------------------------------------------------------------------
# Cycle G/H: Unknown key → 404
# ---------------------------------------------------------------------------

class TestUnknownKey:
    def test_approve_unknown_key_returns_404(self):
        executor = _make_executor()
        client = _client(executor)
        resp = client.post("/approvals/no-such-key/approve")
        assert resp.status_code == 404

    def test_reject_unknown_key_returns_404(self):
        executor = _make_executor()
        client = _client(executor)
        resp = client.post("/approvals/no-such-key/reject", json={"reason": "test"})
        assert resp.status_code == 404
