from fastapi.testclient import TestClient
from backend.app.main import app

client = TestClient(app)

def test_health():
    r = client.get("/api/v1/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"

def test_score_hr_endpoint():
    payload = {
        "name": "Jane",
        "education": [],
        "skills": ["Python", "SQL"],
        "evidence": [{"type":"link"}, {"type":"pdf"}]
    }
    r = client.post("/api/v1/score-hr", json=payload)
    assert r.status_code == 200
    data = r.json()
    assert data["name"] == "Jane"
    assert "score" in data and "level" in data
    assert "summary" in data and "breakdown" in data