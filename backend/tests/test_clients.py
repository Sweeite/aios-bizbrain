"""
Slice 15: Cockpit — Client Profiles.
Tests exercise the HTTP interface through a real TestClient.
"""
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


# ---------------------------------------------------------------------------
# Cycle 1: GET /clients returns 200 with a list
# ---------------------------------------------------------------------------

class TestClientListShape:
    def test_returns_200(self):
        resp = client.get("/clients")
        assert resp.status_code == 200

    def test_returns_a_list(self):
        resp = client.get("/clients")
        assert isinstance(resp.json(), list)

    def test_returns_all_three_known_clients(self):
        data = client.get("/clients").json()
        ids = {c["id"] for c in data}
        assert ids == {
            "client-northpath-001",
            "client-meridian-001",
            "client-vertex-002",
        }

    def test_each_item_has_id_name_deal_stage(self):
        data = client.get("/clients").json()
        for c in data:
            assert "id" in c
            assert "name" in c
            assert "deal_stage" in c

    def test_northpath_has_deal_stage_from_hubspot(self):
        data = client.get("/clients").json()
        northpath = next(c for c in data if c["id"] == "client-northpath-001")
        assert northpath["deal_stage"] == "Proposal"

    def test_clients_without_hubspot_deal_have_null_stage(self):
        data = client.get("/clients").json()
        vertex = next(c for c in data if c["id"] == "client-vertex-002")
        assert vertex["deal_stage"] is None


# ---------------------------------------------------------------------------
# Cycle 3: GET /clients/{id} returns a full profile
# ---------------------------------------------------------------------------

class TestClientProfileShape:
    def test_returns_200_for_known_client(self):
        resp = client.get("/clients/client-northpath-001")
        assert resp.status_code == 200

    def test_returns_404_for_unknown_client(self):
        resp = client.get("/clients/client-does-not-exist")
        assert resp.status_code == 404

    def test_profile_has_id_and_name(self):
        data = client.get("/clients/client-northpath-001").json()
        assert data["id"] == "client-northpath-001"
        assert data["name"] == "Northpath"

    def test_profile_has_brain_understanding_section(self):
        data = client.get("/clients/client-northpath-001").json()
        brain = data["brain_understanding"]
        assert "entity_facts" in brain
        assert "episodic_history" in brain
        assert isinstance(brain["entity_facts"], list)
        assert isinstance(brain["episodic_history"], list)

    def test_brain_understanding_episodic_history_is_non_empty_for_northpath(self):
        data = client.get("/clients/client-northpath-001").json()
        history = data["brain_understanding"]["episodic_history"]
        assert len(history) > 0

    def test_episodic_record_has_required_fields(self):
        data = client.get("/clients/client-northpath-001").json()
        history = data["brain_understanding"]["episodic_history"]
        for record in history:
            assert "store" in record
            assert "payload" in record
            assert "confidence" in record
            assert "as_of" in record
            assert "source" in record


# ---------------------------------------------------------------------------
# Cycle 4: live_status section fuses source-system facts
# ---------------------------------------------------------------------------

class TestClientLiveStatus:
    def test_profile_has_live_status_section(self):
        data = client.get("/clients/client-northpath-001").json()
        live = data["live_status"]
        assert "deal" in live
        assert "budget" in live
        assert "open_tasks" in live
        assert "invoices" in live

    def test_northpath_live_deal_from_hubspot(self):
        live = client.get("/clients/client-northpath-001").json()["live_status"]
        assert live["deal"]["stage"] == "Proposal"
        assert live["deal"]["deal_name"] == "Northpath Q3 Audit"
        assert live["deal"]["days_in_stage"] == 21

    def test_meridian_live_budget_from_harvest(self):
        live = client.get("/clients/client-meridian-001").json()["live_status"]
        assert live["budget"]["budget_usd"] == 50000.0
        assert live["budget"]["spent_usd"] == 40200.0

    def test_meridian_has_open_invoice_from_quickbooks(self):
        live = client.get("/clients/client-meridian-001").json()["live_status"]
        invoice_numbers = [i["invoice_number"] for i in live["invoices"]]
        assert "INV-007" in invoice_numbers

    def test_vertex_has_asana_task(self):
        live = client.get("/clients/client-vertex-002").json()["live_status"]
        task_names = [t["task_name"] for t in live["open_tasks"]]
        assert any("Vertex" in name for name in task_names)

    def test_client_without_deal_has_null_deal(self):
        live = client.get("/clients/client-vertex-002").json()["live_status"]
        assert live["deal"] is None


# ---------------------------------------------------------------------------
# Cycle 5: scope enforcement
# ---------------------------------------------------------------------------

class TestScopeEnforcement:
    def test_list_with_entity_scope_returns_only_that_client(self):
        data = client.get("/clients?scope=client-northpath-001").json()
        assert len(data) == 1
        assert data[0]["id"] == "client-northpath-001"

    def test_list_without_scope_returns_all_clients(self):
        data = client.get("/clients").json()
        assert len(data) == 3

    def test_detail_with_matching_scope_returns_200(self):
        resp = client.get(
            "/clients/client-northpath-001?scope=client-northpath-001"
        )
        assert resp.status_code == 200

    def test_detail_with_mismatched_scope_returns_403(self):
        resp = client.get(
            "/clients/client-northpath-001?scope=client-meridian-001"
        )
        assert resp.status_code == 403

    def test_detail_without_scope_returns_200(self):
        resp = client.get("/clients/client-meridian-001")
        assert resp.status_code == 200
