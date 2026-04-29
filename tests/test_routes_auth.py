"""Smoke tests: every protected route returns 401 without a bearer token."""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_notes_generate_requires_auth():
    r = client.post("/api/notes/generate", json={"subtopic": "film analysis"})
    assert r.status_code == 401


def test_assignments_generate_requires_auth():
    r = client.post("/api/assignments/generate", json={"subtopic": "film analysis"})
    assert r.status_code == 401


def test_assignments_revise_requires_auth():
    r = client.post(
        "/api/assignments/revise",
        json={"subtopic": "film analysis", "content": "x", "changes": "y"},
    )
    assert r.status_code == 401


def test_quizzes_generate_requires_auth():
    r = client.post("/api/quizzes/generate", json={"subtopic": "film analysis"})
    assert r.status_code == 401


def test_mentor_chat_requires_auth():
    r = client.post("/api/mentor/chat", json={"chatInput": "what is mise-en-scene?"})
    assert r.status_code == 401


def test_assignments_evaluate_requires_auth():
    r = client.post(
        "/api/assignments/evaluate",
        json={
            "criteria": "rubric blob",
            "subtopic": "film analysis",
            "file_url": "https://example.com/x.pdf",
        },
    )
    assert r.status_code == 401


def test_scripts_analyze_requires_auth():
    r = client.post(
        "/api/scripts/analyze",
        json={"Type": "assignment", "file_url": "https://example.com/x.pdf"},
    )
    assert r.status_code == 401


def test_scripts_status_requires_auth():
    r = client.get("/api/scripts/analyze/status/some-job-id")
    assert r.status_code == 401
