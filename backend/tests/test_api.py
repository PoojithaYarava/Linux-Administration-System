import os
import tempfile
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

_test_db_dir = tempfile.TemporaryDirectory(prefix="lap-test-db-")
os.environ["DATABASE_PATH"] = str(Path(_test_db_dir.name) / "test.db")
os.environ["ADMIN_PASSWORD"] = "test-private-password-42"
from fastapi.testclient import TestClient
from app.main import app, init_db

init_db()
client = TestClient(app)


def token():
    response = client.post("/api/auth/login", json={"username": "admin", "password": "test-private-password-42"})
    assert response.status_code == 200
    return response.json()["token"]


def test_login_and_system_metrics():
    auth = {"Authorization": f"Bearer {token()}"}
    response = client.get("/api/system/metrics", headers=auth)
    assert response.status_code == 200
    assert {"cpu_usage", "memory_usage", "disk_usage"}.issubset(response.json()["latest"])


def test_fresh_database_rejects_missing_or_weak_admin_password(tmp_path, monkeypatch):
    import pytest
    from app import main as main_module

    original_path = main_module.DB_PATH
    try:
        for password in (None, "short"):
            main_module.DB_PATH = tmp_path / ("fresh-" + (password or "missing") + ".db")
            if password is None:
                monkeypatch.delenv("ADMIN_PASSWORD", raising=False)
            else:
                monkeypatch.setenv("ADMIN_PASSWORD", password)
            with pytest.raises(RuntimeError, match="at least 12 characters"):
                main_module.init_db()
    finally:
        main_module.DB_PATH = original_path
        monkeypatch.setenv("ADMIN_PASSWORD", "test-private-password-42")


def test_filtered_metric_history_downsamples_across_the_requested_range():
    from app.main import db

    start = datetime.now(timezone.utc) - timedelta(days=60)
    observations = [
        ((start + timedelta(seconds=index)).isoformat(), 20.0, 30.0, 40.0, 100, 200, 0.5)
        for index in range(5105)
    ]
    with db() as connection:
        connection.executemany(
            "INSERT INTO system_metrics(timestamp,cpu_usage,memory_usage,disk_usage,network_received,network_sent,load_average) VALUES(?,?,?,?,?,?,?)",
            observations,
        )

    auth = {"Authorization": f"Bearer {token()}"}
    response = client.get(
        "/api/system/metrics/history",
        headers=auth,
        params={"start": observations[0][0], "end": observations[-1][0], "limit": 5000},
    )
    history = response.json()
    assert response.status_code == 200
    assert 1 < len(history) <= 5000
    assert history[0]["timestamp"] == observations[0][0]
    assert history[-1]["timestamp"] == observations[-1][0]
    assert history[0]["timestamp"] < history[len(history) // 2]["timestamp"] < history[-1]["timestamp"]
    newest = client.get("/api/system/metrics/history", headers=auth, params={"start": observations[0][0], "end": observations[-1][0], "limit": 1}).json()
    assert len(newest) == 1 and newest[0]["timestamp"] == observations[-1][0]

    with db() as connection:
        connection.execute("DELETE FROM system_metrics WHERE timestamp>=? AND timestamp<=?", (observations[0][0], observations[-1][0]))


def test_unauthorized_and_allowlist():
    assert client.get("/api/processes").status_code == 401
    response = client.post("/api/services/not-allowed/restart", headers={"Authorization": f"Bearer {token()}"})
    assert response.status_code in {404, 403}


def test_service_operations_require_a_persisted_approval_request():
    auth = {"Authorization": f"Bearer {token()}"}
    response = client.post("/api/actions", headers=auth, json={"action_type": "restart", "target": "ssh", "reason": "Investigate the monitored SSH service after an alert."})
    assert response.status_code == 200
    action = response.json()
    assert action["state"] in {"PENDING_APPROVAL", "REJECTED"}
    assert client.post("/api/services/ssh/restart", headers=auth).status_code == 404


def test_admin_threshold_config_is_validated_and_audited():
    auth = {"Authorization": f"Bearer {token()}"}
    before = client.get("/api/config", headers=auth)
    assert before.status_code == 200
    saved = client.put("/api/config", headers=auth, json={"cpu_alert_threshold": 76, "memory_alert_threshold": 82, "disk_alert_threshold": 91})
    assert saved.status_code == 200
    assert saved.json()["cpu_alert_threshold"] == 76
    assert client.put("/api/config", headers=auth, json={"cpu_alert_threshold": 0, "memory_alert_threshold": 82, "disk_alert_threshold": 91}).status_code == 422
    client.put("/api/config", headers=auth, json=before.json() | {"cpu_alert_threshold": 85, "memory_alert_threshold": 85, "disk_alert_threshold": 90})


def test_impact_is_persisted_and_protected_service_stop_is_prohibited():
    auth = {"Authorization": f"Bearer {token()}"}
    result = client.get("/api/impact/ssh?operation=stop", headers=auth)
    assert result.status_code == 200
    assert result.json()["risk"]["policy"]["decision"] == "prohibited"
    assert result.json()["impact"]["classification"] in {"low", "moderate", "high", "critical"}
    assert client.get("/api/risk/ssh?operation=stop", headers=auth).json()["policy"]["decision"] == "prohibited"


def test_root_cause_endpoint_defines_uncertainty_and_diagnostics():
    auth = {"Authorization": f"Bearer {token()}"}
    response = client.get("/api/root-causes", headers=auth)
    assert response.status_code == 200
    assert response.json()
    finding = response.json()[0]
    assert finding["confidence_definition"]
    assert isinstance(finding["evidence"], list)
    assert isinstance(finding["diagnostics"], list)


def test_expired_approval_is_rejected_and_persisted():
    from app.main import db

    auth = {"Authorization": f"Bearer {token()}"}
    action = client.post("/api/actions", headers=auth, json={"action_type": "restart", "target": "ssh", "reason": "Review a test approval expiration path."}).json()
    with db() as connection:
        connection.execute("UPDATE actions SET expires_at='2000-01-01T00:00:00+00:00' WHERE id=?", (action["id"],))
    decision = client.post(f"/api/actions/{action['id']}/decision", headers=auth, json={"decision": "approve", "reason": "Attempt expired request test."})
    assert decision.status_code == 409
    assert client.get(f"/api/actions/{action['id']}", headers=auth).json()["state"] == "EXPIRED"


def test_approved_action_is_bound_to_exact_target_and_execution_failure_is_recorded():
    from app.main import db

    auth = {"Authorization": f"Bearer {token()}"}
    action = client.post("/api/actions", headers=auth, json={"action_type": "restart", "target": "ssh", "reason": "Exercise exact target operation binding."}).json()
    approved = client.post(f"/api/actions/{action['id']}/decision", headers=auth, json={"decision": "approve", "reason": "Approve a controlled test request."})
    assert approved.status_code == 200
    with db() as connection:
        connection.execute("UPDATE actions SET target='cron' WHERE id=?", (action["id"],))
    assert client.post(f"/api/actions/{action['id']}/execute", headers=auth).status_code == 409

    second = client.post("/api/actions", headers=auth, json={"action_type": "restart", "target": "ssh", "reason": "Exercise systemd unavailable handling."}).json()
    client.post(f"/api/actions/{second['id']}/decision", headers=auth, json={"decision": "approve", "reason": "Approve unavailable-host test."})
    executed = client.post(f"/api/actions/{second['id']}/execute", headers=auth)
    assert executed.status_code == 200
    assert executed.json()["state"] == "FAILED"
    assert "systemd unavailable" in executed.json()["result"]


def test_incident_lifecycle_and_detail_links_related_alert():
    from app.main import record_alert

    auth = {"Authorization": f"Bearer {token()}"}
    source = "test-service-" + str(time.time_ns())
    record_alert("service_failure", "high", "Test service reports failed state.", source)
    listed = client.get("/api/incidents?status_filter=open", headers=auth)
    incident = next(row for row in listed.json() if row["component"] == source)
    detail = client.get(f"/api/incidents/{incident['id']}", headers=auth)
    assert detail.status_code == 200
    assert detail.json()["alert"]["alert_type"] == "service_failure"
    changed = client.patch(f"/api/incidents/{incident['id']}", headers=auth, json={"status": "investigating", "assigned_to": 1})
    assert changed.json()["status"] == "investigating"
    resolved = client.patch(f"/api/incidents/{incident['id']}", headers=auth, json={"status": "resolved", "resolution_notes": "Confirmed recovery and reviewed logs."})
    assert resolved.json()["resolved_at"]


def test_admin_can_change_password_and_old_sessions_are_revoked():
    old_password = "test-private-password-42"
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
