"""
Slice 16: Cockpit — Integrations / Health.
Tests use TestClient through the full FastAPI stack.
"""
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.deps import get_connector_health_service
from engine.connectors.health_service import ConnectorHealthService

KNOWN_SYSTEMS = {
    "hubspot", "gmail", "calendar", "asana",
    "slack", "quickbooks", "harvest", "zoom",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fresh_svc() -> ConnectorHealthService:
    return ConnectorHealthService()


def _client_with_svc(svc: ConnectorHealthService) -> TestClient:
    app.dependency_overrides[get_connector_health_service] = lambda: svc
    client = TestClient(app)
    return client


# ---------------------------------------------------------------------------
# Cycle 1 — health endpoint returns all 8 connectors
# ---------------------------------------------------------------------------

class TestHealthEndpointReturnsAllConnectors:
    def test_returns_list_of_eight(self):
        svc = _fresh_svc()
        client = _client_with_svc(svc)

        res = client.get("/integrations/health")

        assert res.status_code == 200
        data = res.json()
        assert len(data) == 8

    def test_source_systems_are_all_known(self):
        svc = _fresh_svc()
        client = _client_with_svc(svc)

        res = client.get("/integrations/health")
        data = res.json()
        systems = {r["source_system"] for r in data}

        assert systems == KNOWN_SYSTEMS

    def test_initial_status_is_healthy(self):
        svc = _fresh_svc()
        client = _client_with_svc(svc)

        res = client.get("/integrations/health")
        data = res.json()

        assert all(r["status"] == "healthy" for r in data)

    def test_initial_last_sync_at_is_null(self):
        svc = _fresh_svc()
        client = _client_with_svc(svc)

        res = client.get("/integrations/health")
        data = res.json()

        assert all(r["last_sync_at"] is None for r in data)


# ---------------------------------------------------------------------------
# Cycle 2 — broken connector surfaces correctly
# ---------------------------------------------------------------------------

class TestBrokenConnectorSurfaces:
    def test_broken_status_after_failed_sync(self):
        svc = _fresh_svc()
        svc.record_sync("gmail", success=False, error_message="auth_expired")
        client = _client_with_svc(svc)

        res = client.get("/integrations/health")
        data = res.json()
        gmail = next(r for r in data if r["source_system"] == "gmail")

        assert gmail["status"] == "broken"

    def test_error_message_present_on_broken_connector(self):
        svc = _fresh_svc()
        svc.record_sync("gmail", success=False, error_message="auth_expired")
        client = _client_with_svc(svc)

        res = client.get("/integrations/health")
        data = res.json()
        gmail = next(r for r in data if r["source_system"] == "gmail")

        assert gmail["error_message"] == "auth_expired"

    def test_other_connectors_unaffected(self):
        svc = _fresh_svc()
        svc.record_sync("gmail", success=False, error_message="auth_expired")
        client = _client_with_svc(svc)

        res = client.get("/integrations/health")
        data = res.json()
        others = [r for r in data if r["source_system"] != "gmail"]

        assert all(r["status"] == "healthy" for r in others)

    def test_successful_sync_sets_healthy_and_last_sync_at(self):
        svc = _fresh_svc()
        svc.record_sync("hubspot", success=True)
        client = _client_with_svc(svc)

        res = client.get("/integrations/health")
        data = res.json()
        hubspot = next(r for r in data if r["source_system"] == "hubspot")

        assert hubspot["status"] == "healthy"
        assert hubspot["last_sync_at"] is not None
        assert hubspot["error_message"] is None


# ---------------------------------------------------------------------------
# Cycle 3 — reconnect resets a broken connector
# ---------------------------------------------------------------------------

class TestReconnect:
    def test_reconnect_resets_broken_to_healthy(self):
        svc = _fresh_svc()
        svc.record_sync("slack", success=False, error_message="token_revoked")
        client = _client_with_svc(svc)

        res = client.post("/integrations/slack/reconnect")

        assert res.status_code == 200
        data = res.json()
        assert data["source_system"] == "slack"
        assert data["status"] == "healthy"
        assert data["error_message"] is None

    def test_reconnect_unknown_connector_returns_404(self):
        svc = _fresh_svc()
        client = _client_with_svc(svc)

        res = client.post("/integrations/not_a_system/reconnect")

        assert res.status_code == 404

    def test_health_reflects_reconnect(self):
        svc = _fresh_svc()
        svc.record_sync("asana", success=False, error_message="rate_limited")
        client = _client_with_svc(svc)

        client.post("/integrations/asana/reconnect")
        res = client.get("/integrations/health")
        data = res.json()
        asana = next(r for r in data if r["source_system"] == "asana")

        assert asana["status"] == "healthy"


# ---------------------------------------------------------------------------
# Cycle 4 — status values are always in the valid set
# ---------------------------------------------------------------------------

class TestStatusValues:
    def test_status_is_always_valid(self):
        valid = {"healthy", "degraded", "broken"}
        svc = _fresh_svc()
        svc.record_sync("zoom", success=False, error_message="err")
        svc.record_sync("harvest", success=True)
        client = _client_with_svc(svc)

        res = client.get("/integrations/health")
        data = res.json()

        assert all(r["status"] in valid for r in data)
