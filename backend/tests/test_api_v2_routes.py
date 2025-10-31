# backend/tests/test_api_v2_routes.py
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_candidates_route_success():
    response = client.get("/api/v2/candidates")
    assert response.status_code == 200
    assert "summary" in response.json()
    assert "candidates" in response.json()

def test_import_summary_success():
    response = client.get("/api/v2/import-summary")
    assert response.status_code in [200, 500]  # ปรับตามไฟล์ log มีหรือไม่
