"""FastAPI app boots and health check responds."""
from datetime import datetime, timezone

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_health_check_returns_200():
    resp = client.get("/health")
    assert resp.status_code == 200


def test_health_check_reports_ok():
    resp = client.get("/health")
    data = resp.json()
    assert data["status"] == "ok"


def test_root_not_found():
    resp = client.get("/")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Cross-router seam: /activity and /runs/{id}/trace share the same stores
# ---------------------------------------------------------------------------

def test_activity_and_trace_share_run_store():
    """
    A run written to the shared store must appear in /activity AND be traceable
    via /runs/{run_id}/trace — with no DI overrides. Catches split-singleton
    wiring bugs where each router holds its own store instance.
    """
    from engine.observability.run_store import InMemoryRunStore
    from engine.observability.span_store import InMemorySpanStore
    from engine.spine.types import Run, Scope, ScopeLevel
    from app.deps import get_run_store, get_span_store

    run_store = InMemoryRunStore()
    span_store = InMemorySpanStore()

    app.dependency_overrides[get_run_store] = lambda: run_store
    app.dependency_overrides[get_span_store] = lambda: span_store

    try:
        run_store.save(Run(
            run_id="seam-test-run",
            initiated_by="deal.stage_changed",
            scope=Scope(level=ScopeLevel.entity, entity_ref="client-seam"),
            started_at=datetime.now(timezone.utc),
            status="done",
        ))

        http = TestClient(app)

        activity = http.get("/activity").json()
        assert any(r["run_id"] == "seam-test-run" for r in activity), \
            "/activity did not see the run"

        trace = http.get("/runs/seam-test-run/trace")
        assert trace.status_code == 200, \
            f"/runs/seam-test-run/trace returned {trace.status_code}"
    finally:
        app.dependency_overrides = {}
