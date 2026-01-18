from backend.app.main import app
from fastapi.testclient import TestClient

def test_health_ok():
    client = TestClient(app)
    r = client.get("/health")
    assert r.status_code == 200
    # Status can be "ok" or "degraded" depending on blockchain connection
    assert r.json()["status"] in ["ok", "degraded"]
