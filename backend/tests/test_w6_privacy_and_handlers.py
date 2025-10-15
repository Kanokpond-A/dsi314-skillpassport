from fastapi.testclient import TestClient
from backend.app.main import app

client = TestClient(app)

def test_redaction_in_ucb():
    payload = {
        "name": "Alice",
        "education": ["B.Sc"],
        "skills": ["Python", "SQL"],
        "evidence": ["alice@example.com", "call me +66 81-234-5678"],
        "email": "alice@example.com",
        "phone": "+66 81-234-5678"
    }
    r = client.post("/api/v1/ucb", json=payload)
    assert r.status_code == 200
    data = r.json()
    # ใน summary/breakdown ไม่ควรมีอีเมล/เบอร์ดิบ
    text = str(data)
    assert "[REDACTED]" in text
    assert "example.com" not in text
    assert "81-234" not in text

def test_validation_handler():
    # ส่ง payload ผิดชนิด เช่น skills เป็นสตริง
    bad = {"name":"Bob","education":[],"skills":"Python","evidence":[]}
    r = client.post("/api/v1/ucb", json=bad)
    assert r.status_code == 422
    body = r.json()
    assert body["error"] == "Invalid request payload"
    assert "request_id" in body

def test_request_id_header():
    payload = {"name":"Jane","education":[],"skills":["Python"],"evidence":[]}
    r = client.post("/api/v1/ucb", json=payload)
    assert r.status_code == 200
    assert "X-Request-ID" in r.headers
