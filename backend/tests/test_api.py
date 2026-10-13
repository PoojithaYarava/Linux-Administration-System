import os
from pathlib import Path

os.environ["DATABASE_PATH"] = str(Path(__file__).parent / "test.db")
from fastapi.testclient import TestClient
from app.main import app, init_db

init_db()
client = TestClient(app)


def token():
    response = client.post("/api/auth/login", json={"username": "admin", "password": "change-me-now"})
    assert response.status_code == 200
    return response.json()["token"]


def test_login_and_system_metrics():
    auth = {"Authorization": f"Bearer {token()}"}
    response = client.get("/api/system/metrics", headers=auth)
    assert response.status_code == 200
    assert {"cpu_usage", "memory_usage", "disk_usage"}.issubset(response.json()["latest"])


def test_unauthorized_and_allowlist():
    assert client.get("/api/processes").status_code == 401
    response = client.post("/api/services/not-allowed/restart", headers={"Authorization": f"Bearer {token()}"})
    assert response.status_code in {400, 403}


def test_admin_can_change_password_and_old_sessions_are_revoked():
    old_password = "change-me-now"
    new_password = "a-new-private-password-42"
    old_token = token()
    headers = {"Authorization": f"Bearer {old_token}"}

    changed = client.post(
        "/api/auth/change-password",
        headers=headers,
        json={"current_password": old_password, "new_password": new_password},
    )
    assert changed.status_code == 200
    assert client.get("/api/system/info", headers=headers).status_code == 401
    assert client.post("/api/auth/login", json={"username": "admin", "password": old_password}).status_code == 401

    new_login = client.post("/api/auth/login", json={"username": "admin", "password": new_password})
    assert new_login.status_code == 200
    new_headers = {"Authorization": f"Bearer {new_login.json()['token']}"}
    restored = client.post(
        "/api/auth/change-password",
        headers=new_headers,
        json={"current_password": new_password, "new_password": old_password},
    )
    assert restored.status_code == 200
