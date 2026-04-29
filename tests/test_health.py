from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_returns_ok():
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["service"] == "screen-scribe-agents"


def test_notes_requires_auth():
    r = client.post("/api/notes/generate", json={"subtopic": "film analysis"})
    assert r.status_code == 401
