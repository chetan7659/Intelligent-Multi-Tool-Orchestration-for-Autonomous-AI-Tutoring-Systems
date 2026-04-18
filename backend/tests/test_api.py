from fastapi.testclient import TestClient
from app.main import app
from app.config import settings

client = TestClient(app)

def test_root():
    response = client.get("/api/v1/")
    assert response.status_code == 200
    assert response.json()["name"] == "EduOrchestrator API"

def test_health():
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"
    assert "tools_loaded" in response.json()
