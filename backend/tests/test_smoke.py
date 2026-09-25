from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_docs_and_login():
    assert client.get("/openapi.json").status_code == 200
    response = client.post("/api/auth/login", data={"username": "admin@educrm.uz", "password": "Admin123!"})
    assert response.status_code == 200
    assert response.json()["token_type"] == "bearer"
