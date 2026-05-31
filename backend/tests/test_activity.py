"""
Slice 14: Activity Feed — recent runs list + trace drilldown.
"""
from datetime import datetime, timezone, timedelta

import pytest

from engine.spine.types import Run, Scope, ScopeLevel, Span, SpanOp


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _scope(entity_ref: str = "client-northpath-001") -> Scope:
    return Scope(level=ScopeLevel.entity, entity_ref=entity_ref)


def _run(run_id: str, initiated_by: str = "deal.stage_changed",
         entity_ref: str = "client-northpath-001",
         started_at: datetime | None = None,
         status: str = "done") -> Run:
    if started_at is None:
        started_at = datetime.now(timezone.utc)
    return Run(
        run_id=run_id,
        initiated_by=initiated_by,
        scope=_scope(entity_ref),
        started_at=started_at,
        status=status,
    )


def _span(run_id: str, span_id: str, actor: str = "account-agent",
          op: SpanOp = SpanOp.reason) -> Span:
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
        model_tier="strong",
        token_in=100,
        token_out=50,
        scope=_scope(),
        status="ok",
    )


# ---------------------------------------------------------------------------
# Cycle 1: RunStore.list() — reverse chronological order
# ---------------------------------------------------------------------------

class TestRunStoreList:
    def test_list_returns_all_runs(self):
        from engine.observability.run_store import InMemoryRunStore
        store = InMemoryRunStore()
        store.save(_run("r1"))
        store.save(_run("r2"))
        result = store.list()
        assert {r.run_id for r in result} == {"r1", "r2"}

    def test_list_returns_empty_when_no_runs(self):
        from engine.observability.run_store import InMemoryRunStore
        assert InMemoryRunStore().list() == []

    def test_list_reverse_chronological_order(self):
        from engine.observability.run_store import InMemoryRunStore
        now = datetime.now(timezone.utc)
        store = InMemoryRunStore()
        store.save(_run("r-old", started_at=now - timedelta(hours=2)))
        store.save(_run("r-mid", started_at=now - timedelta(hours=1)))
        store.save(_run("r-new", started_at=now))
        ids = [r.run_id for r in store.list()]
        assert ids == ["r-new", "r-mid", "r-old"]


# ---------------------------------------------------------------------------
# Cycle 2: RunStore.list() — scope filtering
# ---------------------------------------------------------------------------

class TestRunStoreListScopeFilter:
    def test_list_filters_by_entity_ref(self):
        from engine.observability.run_store import InMemoryRunStore
        store = InMemoryRunStore()
        store.save(_run("r-a", entity_ref="client-a"))
        store.save(_run("r-b", entity_ref="client-b"))
        result = store.list(scope_entity_ref="client-a")
        assert len(result) == 1
        assert result[0].run_id == "r-a"

    def test_list_no_filter_returns_all(self):
        from engine.observability.run_store import InMemoryRunStore
        store = InMemoryRunStore()
        store.save(_run("r-a", entity_ref="client-a"))
        store.save(_run("r-b", entity_ref="client-b"))
        assert len(store.list()) == 2


# ---------------------------------------------------------------------------
# Cycle 3: GET /activity — run summary shape
# ---------------------------------------------------------------------------

class TestActivityEndpoint:
    def setup_method(self):
        from app.main import app
        app.dependency_overrides = {}

    def teardown_method(self):
        from app.main import app
        app.dependency_overrides = {}

    def _client(self, run_store, span_store=None):
        from fastapi.testclient import TestClient
        from app.main import app
        from app.deps import get_run_store, get_span_store
        from engine.observability.span_store import InMemorySpanStore

        app.dependency_overrides[get_run_store] = lambda: run_store
        app.dependency_overrides[get_span_store] = lambda: (span_store or InMemorySpanStore())
        return TestClient(app)

    def test_activity_returns_200(self):
        from engine.observability.run_store import InMemoryRunStore
        client = self._client(InMemoryRunStore())
        resp = client.get("/activity")
        assert resp.status_code == 200

    def test_activity_returns_list(self):
        from engine.observability.run_store import InMemoryRunStore
        store = InMemoryRunStore()
        store.save(_run("r1"))
        resp = self._client(store).get("/activity")
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) == 1

    def test_activity_run_has_required_fields(self):
        from engine.observability.run_store import InMemoryRunStore
        store = InMemoryRunStore()
        store.save(_run("r1", initiated_by="deal.stage_changed", status="done"))
        data = self._client(store).get("/activity").json()
        row = data[0]
        assert "run_id" in row
        assert "trigger" in row
        assert "trigger_type" in row
        assert "outcome" in row
        assert "started_at" in row
        assert "primary_agent" in row

    def test_activity_trigger_type_proactive_for_event_trigger(self):
        from engine.observability.run_store import InMemoryRunStore
        store = InMemoryRunStore()
        store.save(_run("r1", initiated_by="deal.stage_changed"))
        row = self._client(store).get("/activity").json()[0]
        assert row["trigger_type"] == "proactive"

    def test_activity_trigger_type_human_for_user_prefix(self):
        from engine.observability.run_store import InMemoryRunStore
        store = InMemoryRunStore()
        store.save(_run("r1", initiated_by="user:chat"))
        row = self._client(store).get("/activity").json()[0]
        assert row["trigger_type"] == "human-directed"

    def test_activity_outcome_maps_done_to_completed(self):
        from engine.observability.run_store import InMemoryRunStore
        store = InMemoryRunStore()
        store.save(_run("r1", status="done"))
        row = self._client(store).get("/activity").json()[0]
        assert row["outcome"] == "completed"

    def test_activity_outcome_parked_passthrough(self):
        from engine.observability.run_store import InMemoryRunStore
        store = InMemoryRunStore()
        store.save(_run("r1", status="parked"))
        row = self._client(store).get("/activity").json()[0]
        assert row["outcome"] == "parked"

    def test_activity_outcome_failed_passthrough(self):
        from engine.observability.run_store import InMemoryRunStore
        store = InMemoryRunStore()
        store.save(_run("r1", status="failed"))
        row = self._client(store).get("/activity").json()[0]
        assert row["outcome"] == "failed"

    def test_activity_ordered_reverse_chron(self):
        from engine.observability.run_store import InMemoryRunStore
        now = datetime.now(timezone.utc)
        store = InMemoryRunStore()
        store.save(_run("r-old", started_at=now - timedelta(hours=2)))
        store.save(_run("r-new", started_at=now))
        ids = [r["run_id"] for r in self._client(store).get("/activity").json()]
        assert ids == ["r-new", "r-old"]


# ---------------------------------------------------------------------------
# Cycle 4: GET /activity?scope= — scope filtering
# ---------------------------------------------------------------------------

class TestActivityScopeFilter:
    def setup_method(self):
        from app.main import app
        app.dependency_overrides = {}

    def teardown_method(self):
        from app.main import app
        app.dependency_overrides = {}

    def _client(self, run_store):
        from fastapi.testclient import TestClient
        from app.main import app
        from app.deps import get_run_store, get_span_store
        from engine.observability.span_store import InMemorySpanStore
        app.dependency_overrides[get_run_store] = lambda: run_store
        app.dependency_overrides[get_span_store] = lambda: InMemorySpanStore()
        return TestClient(app)

    def test_scope_filter_returns_only_matching_entity(self):
        from engine.observability.run_store import InMemoryRunStore
        store = InMemoryRunStore()
        store.save(_run("r-a", entity_ref="client-a"))
        store.save(_run("r-b", entity_ref="client-b"))
        data = self._client(store).get("/activity?scope=client-a").json()
        assert len(data) == 1
        assert data[0]["run_id"] == "r-a"

    def test_no_scope_filter_returns_all(self):
        from engine.observability.run_store import InMemoryRunStore
        store = InMemoryRunStore()
        store.save(_run("r-a", entity_ref="client-a"))
        store.save(_run("r-b", entity_ref="client-b"))
        data = self._client(store).get("/activity").json()
        assert len(data) == 2


# ---------------------------------------------------------------------------
# Cycle 5: primary_agent derived from spans
# ---------------------------------------------------------------------------

class TestActivityPrimaryAgent:
    def setup_method(self):
        from app.main import app
        app.dependency_overrides = {}

    def teardown_method(self):
        from app.main import app
        app.dependency_overrides = {}

    def _client(self, run_store, span_store):
        from fastapi.testclient import TestClient
        from app.main import app
        from app.deps import get_run_store, get_span_store
        app.dependency_overrides[get_run_store] = lambda: run_store
        app.dependency_overrides[get_span_store] = lambda: span_store
        return TestClient(app)

    def test_primary_agent_from_first_reason_span(self):
        from engine.observability.run_store import InMemoryRunStore
        from engine.observability.span_store import InMemorySpanStore
        run_store = InMemoryRunStore()
        span_store = InMemorySpanStore()
        run_store.save(_run("r1"))
        span_store.save(_span("r1", "sp1", actor="account-agent", op=SpanOp.reason))
        row = self._client(run_store, span_store).get("/activity").json()[0]
        assert row["primary_agent"] == "account-agent"

    def test_primary_agent_null_when_no_spans(self):
        from engine.observability.run_store import InMemoryRunStore
        from engine.observability.span_store import InMemorySpanStore
        run_store = InMemoryRunStore()
        run_store.save(_run("r1"))
        row = self._client(run_store, InMemorySpanStore()).get("/activity").json()[0]
        assert row["primary_agent"] is None

    def test_primary_agent_prefers_reason_span_over_tool_span(self):
        from engine.observability.run_store import InMemoryRunStore
        from engine.observability.span_store import InMemorySpanStore
        run_store = InMemoryRunStore()
        span_store = InMemorySpanStore()
        run_store.save(_run("r1"))
        span_store.save(_span("r1", "sp-tool", actor="tool-executor", op=SpanOp.tool))
        span_store.save(_span("r1", "sp-reason", actor="comms-agent", op=SpanOp.reason))
        row = self._client(run_store, span_store).get("/activity").json()[0]
        assert row["primary_agent"] == "comms-agent"
