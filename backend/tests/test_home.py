"""
Slice 9: Home / Today — FastAPI /home/summary endpoint.
Tests exercise the HTTP interface through a real TestClient.
"""
import pytest
from fastapi.testclient import TestClient

from engine.spine.types import AutonomyTier, Scope, ScopeLevel, ToolMode, ToolSpec
from engine.tools.registry import ToolRegistry
from engine.tools.executor import ToolExecutor
from app.main import app
from app.deps import get_executor

client = TestClient(app)


def _make_t3_executor() -> ToolExecutor:
    spec = ToolSpec(
        name="test.home_t3",
        inputs={"body": "str"},
        system="test",
        mode=ToolMode.write,
        tier=AutonomyTier.T3,
        scope_required=ScopeLevel.entity,
        reversible=False,
        side_effects=[],
    )
    registry = ToolRegistry()
    registry.register(spec, lambda inputs, dry_run=False: inputs.get("body", ""))
    return ToolExecutor(registry)


def _client_with_executor(executor: ToolExecutor) -> TestClient:
    app.dependency_overrides[get_executor] = lambda: executor
    return TestClient(app)


def _park(executor: ToolExecutor, key: str) -> None:
    executor.execute(
        "test.home_t3",
        inputs={"body": "draft"},
        scope=Scope(level=ScopeLevel.entity, entity_ref="client-northpath-001"),
        requesting_agent="account-agent",
        principal="client-northpath-001",
        rationale="test",
        idempotency_key=key,
    )


# ---------------------------------------------------------------------------
# Cycle 1: GET /home/summary returns 200 with correct top-level shape
# ---------------------------------------------------------------------------

class TestHomeSummaryShape:
    def test_returns_200(self):
        resp = client.get("/home/summary")
        assert resp.status_code == 200

    def test_has_pending_count_meetings_flagged(self):
        resp = client.get("/home/summary")
        data = resp.json()
        assert "pending_count" in data
        assert "meetings" in data
        assert "flagged" in data


# ---------------------------------------------------------------------------
# Cycle 2: pending_count reflects queue depth
# ---------------------------------------------------------------------------

class TestPendingCount:
    def test_pending_count_is_zero_when_queue_empty(self):
        executor = _make_t3_executor()
        c = _client_with_executor(executor)
        data = c.get("/home/summary").json()
        assert data["pending_count"] == 0

    def test_pending_count_increments_when_item_parked(self):
        executor = _make_t3_executor()
        _park(executor, "home-pend-001")
        c = _client_with_executor(executor)
        data = c.get("/home/summary").json()
        assert data["pending_count"] == 1


# ---------------------------------------------------------------------------
# Cycle 3: meetings shape
# ---------------------------------------------------------------------------

class TestMeetings:
    def test_meetings_list_is_non_empty(self):
        data = client.get("/home/summary").json()
        assert len(data["meetings"]) > 0

    def test_each_meeting_has_required_fields(self):
        data = client.get("/home/summary").json()
        for m in data["meetings"]:
            assert "time" in m
            assert "title" in m
            assert "attendees" in m
            assert "brief" in m

    def test_attendees_is_a_list(self):
        data = client.get("/home/summary").json()
        for m in data["meetings"]:
            assert isinstance(m["attendees"], list)

    def test_scope_filter_returns_only_matching_meetings(self):
        data = client.get("/home/summary?scope=client-meridian-001").json()
        assert all(
            m["title"].startswith("Meridian") for m in data["meetings"]
        )


# ---------------------------------------------------------------------------
# Cycle 4: flagged items shape
# ---------------------------------------------------------------------------

class TestFlaggedItems:
    def test_flagged_list_is_non_empty(self):
        data = client.get("/home/summary").json()
        assert len(data["flagged"]) >= 1

    def test_each_flag_has_required_fields(self):
        data = client.get("/home/summary").json()
        for f in data["flagged"]:
            assert "type" in f
            assert "entity_ref" in f
            assert "label" in f
            assert "since" in f

    def test_scope_filter_returns_only_matching_flags(self):
        data = client.get("/home/summary?scope=client-meridian-001").json()
        assert all(f["entity_ref"] == "client-meridian-001" for f in data["flagged"])


# ---------------------------------------------------------------------------
# Seam test: shared executor singleton — no dependency_overrides
# Catches the class of bug where two routers hold separate executor instances
# ---------------------------------------------------------------------------

class TestSharedExecutorSeam:
    def test_pending_count_reflects_approval_seeded_via_approvals_router(self):
        import os
        os.environ["DEBUG"] = "1"
        real_client = TestClient(app)  # no overrides — exercises real singletons
        real_client.post("/approvals/seed")
        data = real_client.get("/home/summary").json()
        assert data["pending_count"] >= 1
