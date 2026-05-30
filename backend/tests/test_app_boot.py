"""FastAPI app boots and health check responds."""
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
