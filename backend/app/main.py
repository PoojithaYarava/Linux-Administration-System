from __future__ import annotations

import hashlib
import hmac
import json
import logging
import math
import os
import platform
import re
import secrets
import shutil
import sqlite3
import subprocess
import threading
import time
from contextlib import contextmanager, suppress
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import psutil
from fastapi import Depends, FastAPI, HTTPException, Query, Request, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app.intelligence import detect_anomalies
from app.forecasting import forecast_resources
from app.root_cause import analyze_root_causes
from app.safety import action_fingerprint, assess_action, recommendations_from_state

BASE_DIR = Path(__file__).resolve().parents[2]


def load_environment(path: Path) -> None:
    """Load the project .env without overriding values set by the process."""
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        value = value.strip().strip("\"'")
        os.environ.setdefault(key.strip(), value)


load_environment(BASE_DIR / ".env")
configured_db_path = Path(os.getenv("DATABASE_PATH", BASE_DIR / "data" / "platform.db"))
DB_PATH = configured_db_path if configured_db_path.is_absolute() else BASE_DIR / configured_db_path
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="Linux Admin Intelligence Platform", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",") if origin.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
ALLOWED_SERVICES = set(filter(None, os.getenv("ALLOWED_SERVICES", "ssh,cron,systemd-journald").split(",")))
SESSION_TTL_HOURS = max(1, int(os.getenv("SESSION_TTL_HOURS", "12")))
COLLECTOR_INTERVAL_SECONDS = max(5, int(os.getenv("COLLECTOR_INTERVAL_SECONDS", "15")))
RETENTION_DAYS = max(1, int(os.getenv("RETENTION_DAYS", "30")))
COLLECTOR_ENABLED = os.getenv("COLLECTOR_ENABLED", "true").strip().lower() not in {"0", "false", "no", "off"}
logger = logging.getLogger("linux_admin_platform")
collector_stop = threading.Event()
collector_thread: threading.Thread | None = None
login_failures: dict[str, tuple[int, float]] = {}
LOGIN_FAILURE_LIMIT = max(3, int(os.getenv("LOGIN_FAILURE_LIMIT", "5")))
LOGIN_WINDOW_SECONDS = max(60, int(os.getenv("LOGIN_WINDOW_SECONDS", "900")))


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def db():
    connection = sqlite3.connect(DB_PATH, timeout=10)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys=ON")
    connection.execute("PRAGMA busy_timeout=10000")
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def init_db() -> None:
    with db() as connection:
        connection.executescript("""
        CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, username TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL, role TEXT NOT NULL, created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS system_metrics (id INTEGER PRIMARY KEY, timestamp TEXT NOT NULL, cpu_usage REAL NOT NULL, memory_usage REAL NOT NULL, disk_usage REAL NOT NULL, network_received INTEGER NOT NULL, network_sent INTEGER NOT NULL, load_average REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS processes (id INTEGER PRIMARY KEY, timestamp TEXT NOT NULL, pid INTEGER NOT NULL, process_name TEXT NOT NULL, cpu_usage REAL NOT NULL, memory_usage REAL NOT NULL, status TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS services (id INTEGER PRIMARY KEY, service_name TEXT NOT NULL, status TEXT NOT NULL, enabled INTEGER NOT NULL, checked_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS logs (id INTEGER PRIMARY KEY, timestamp TEXT NOT NULL, source TEXT NOT NULL, severity TEXT NOT NULL, message TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS alerts (id INTEGER PRIMARY KEY, timestamp TEXT NOT NULL, alert_type TEXT NOT NULL, severity TEXT NOT NULL, message TEXT NOT NULL, status TEXT NOT NULL, source TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS actions (id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL, action_type TEXT NOT NULL, target TEXT NOT NULL, requested_at TEXT NOT NULL, executed_at TEXT, status TEXT NOT NULL, result TEXT, FOREIGN KEY(user_id) REFERENCES users(id));
        CREATE TABLE IF NOT EXISTS audit_logs (id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL, action TEXT NOT NULL, target TEXT NOT NULL, timestamp TEXT NOT NULL, result TEXT NOT NULL, FOREIGN KEY(user_id) REFERENCES users(id));
        CREATE TABLE IF NOT EXISTS sessions (token_hash TEXT PRIMARY KEY, user_id INTEGER NOT NULL, created_at TEXT NOT NULL, expires_at TEXT NOT NULL, FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE);
        CREATE TABLE IF NOT EXISTS service_dependencies (id INTEGER PRIMARY KEY, source_service TEXT NOT NULL, target_service TEXT NOT NULL, relationship TEXT NOT NULL, source TEXT NOT NULL, observed_at TEXT NOT NULL, UNIQUE(source_service,target_service,relationship));
        CREATE TABLE IF NOT EXISTS service_snapshots (id INTEGER PRIMARY KEY, service_name TEXT NOT NULL, active TEXT NOT NULL, sub_state TEXT, load_state TEXT, enabled_state TEXT, description TEXT, observed_at TEXT NOT NULL, UNIQUE(service_name,observed_at));
        CREATE TABLE IF NOT EXISTS anomaly_findings (id INTEGER PRIMARY KEY, metric_id INTEGER NOT NULL, metric TEXT NOT NULL, component TEXT NOT NULL, observed_value REAL NOT NULL, baseline REAL, severity TEXT NOT NULL, detection_method TEXT NOT NULL, score REAL, explanation TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'open', created_at TEXT NOT NULL, resolved_at TEXT, UNIQUE(metric_id,detection_method), FOREIGN KEY(metric_id) REFERENCES system_metrics(id) ON DELETE CASCADE);
        CREATE TABLE IF NOT EXISTS incident_actions (incident_id INTEGER NOT NULL, action_id INTEGER NOT NULL, PRIMARY KEY(incident_id,action_id), FOREIGN KEY(incident_id) REFERENCES incidents(id), FOREIGN KEY(action_id) REFERENCES actions(id));
        CREATE TABLE IF NOT EXISTS predictions (id INTEGER PRIMARY KEY, metric TEXT NOT NULL, method TEXT NOT NULL, model_version TEXT NOT NULL, observed_at TEXT NOT NULL, forecast_at TEXT NOT NULL, horizon_hours REAL NOT NULL, observed_value REAL NOT NULL, predicted_value REAL NOT NULL, threshold REAL NOT NULL, estimated_hours_to_threshold REAL, walk_forward_mae REAL, baseline_mae REAL, evaluation_count INTEGER NOT NULL, sample_count INTEGER NOT NULL, confidence_score REAL, explanation TEXT NOT NULL, created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS model_versions (id INTEGER PRIMARY KEY, name TEXT NOT NULL, version TEXT NOT NULL, method TEXT NOT NULL, training_window_start TEXT, training_window_end TEXT, sample_count INTEGER NOT NULL, parameters_json TEXT NOT NULL, created_at TEXT NOT NULL, UNIQUE(name,version));
        CREATE TABLE IF NOT EXISTS evaluation_runs (id INTEGER PRIMARY KEY, model_name TEXT NOT NULL, model_version TEXT NOT NULL, evaluation_method TEXT NOT NULL, metrics_json TEXT NOT NULL, sample_count INTEGER NOT NULL, created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS root_cause_findings (id INTEGER PRIMARY KEY, incident_id INTEGER, component TEXT NOT NULL, hypothesis TEXT NOT NULL, confidence INTEGER NOT NULL, confidence_definition TEXT NOT NULL, evidence_json TEXT NOT NULL, alternatives_json TEXT NOT NULL, diagnostics_json TEXT NOT NULL, created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS impact_assessments (id INTEGER PRIMARY KEY, action_id INTEGER, incident_id INTEGER, actor_id INTEGER NOT NULL, operation TEXT NOT NULL, target TEXT NOT NULL, report_json TEXT NOT NULL, created_at TEXT NOT NULL, FOREIGN KEY(action_id) REFERENCES actions(id), FOREIGN KEY(incident_id) REFERENCES incidents(id), FOREIGN KEY(actor_id) REFERENCES users(id));
        CREATE TABLE IF NOT EXISTS risk_assessments (id INTEGER PRIMARY KEY, action_id INTEGER, incident_id INTEGER, actor_id INTEGER NOT NULL, score INTEGER NOT NULL CHECK(score BETWEEN 0 AND 100), band TEXT NOT NULL, factors_json TEXT NOT NULL, policy_json TEXT NOT NULL, created_at TEXT NOT NULL, FOREIGN KEY(action_id) REFERENCES actions(id), FOREIGN KEY(incident_id) REFERENCES incidents(id), FOREIGN KEY(actor_id) REFERENCES users(id));
        CREATE TABLE IF NOT EXISTS recommendations (id INTEGER PRIMARY KEY, recommendation_key TEXT NOT NULL UNIQUE, category TEXT NOT NULL, title TEXT NOT NULL, problem TEXT NOT NULL, evidence_json TEXT NOT NULL, proposed_action TEXT NOT NULL, expected_benefit TEXT NOT NULL, potential_impact TEXT NOT NULL, risk_score INTEGER, risk_factors_json TEXT NOT NULL DEFAULT '{}', requires_approval INTEGER NOT NULL, verification TEXT NOT NULL, do_not_follow_when TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'active', created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS approvals (id INTEGER PRIMARY KEY, action_id INTEGER NOT NULL, approver_id INTEGER NOT NULL, decision TEXT NOT NULL, reason TEXT NOT NULL, approved_at TEXT NOT NULL, expires_at TEXT NOT NULL, FOREIGN KEY(action_id) REFERENCES actions(id), FOREIGN KEY(approver_id) REFERENCES users(id));
        CREATE TABLE IF NOT EXISTS incidents (id INTEGER PRIMARY KEY, incident_key TEXT NOT NULL UNIQUE, title TEXT NOT NULL, description TEXT NOT NULL, severity TEXT NOT NULL, component TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'open', linked_alert_id INTEGER, assigned_to INTEGER, resolution_notes TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL, resolved_at TEXT, FOREIGN KEY(linked_alert_id) REFERENCES alerts(id), FOREIGN KEY(assigned_to) REFERENCES users(id));
        CREATE TABLE IF NOT EXISTS collector_state (id INTEGER PRIMARY KEY CHECK(id=1), status TEXT NOT NULL, last_attempt_at TEXT, last_success_at TEXT, last_error TEXT, observation_count INTEGER NOT NULL DEFAULT 0, updated_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS app_config (key TEXT PRIMARY KEY, value_json TEXT NOT NULL, updated_at TEXT NOT NULL, updated_by INTEGER, FOREIGN KEY(updated_by) REFERENCES users(id));
        """)
        migrations = {
            "system_metrics": {
                "memory_available": "INTEGER NOT NULL DEFAULT 0", "disk_total_bytes": "INTEGER NOT NULL DEFAULT 0",
                "disk_used_bytes": "INTEGER NOT NULL DEFAULT 0", "disk_read_bytes": "INTEGER NOT NULL DEFAULT 0",
                "disk_write_bytes": "INTEGER NOT NULL DEFAULT 0", "network_received_rate": "REAL NOT NULL DEFAULT 0",
                "network_sent_rate": "REAL NOT NULL DEFAULT 0", "interface_stats": "TEXT NOT NULL DEFAULT '{}'",
                "process_count": "INTEGER NOT NULL DEFAULT 0", "availability_json": "TEXT NOT NULL DEFAULT '{}'",
            },
            "processes": {"username": "TEXT", "start_time": "TEXT", "command": "TEXT", "memory_bytes": "INTEGER NOT NULL DEFAULT 0"},
            "services": {"active": "TEXT NOT NULL DEFAULT 'unknown'", "load": "TEXT", "description": "TEXT", "unit_file_state": "TEXT"},
            "logs": {"unit": "TEXT", "journal_cursor": "TEXT"},
            "actions": {"state": "TEXT NOT NULL DEFAULT 'PENDING_APPROVAL'", "impact_json": "TEXT", "risk_json": "TEXT", "requested_by": "INTEGER", "approved_by": "INTEGER", "expires_at": "TEXT", "before_state": "TEXT", "fingerprint": "TEXT", "incident_id": "INTEGER"},
            "recommendations": {"risk_factors_json": "TEXT NOT NULL DEFAULT '{}'"},
        }
        for table, columns in migrations.items():
            present = {row["name"] for row in connection.execute(f"PRAGMA table_info({table})")}
            for name, definition in columns.items():
                if name not in present:
                    connection.execute(f"ALTER TABLE {table} ADD COLUMN {name} {definition}")
        connection.executescript("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_logs_journal_cursor ON logs(journal_cursor) WHERE journal_cursor IS NOT NULL;
        CREATE INDEX IF NOT EXISTS idx_metrics_timestamp ON system_metrics(timestamp);
        CREATE INDEX IF NOT EXISTS idx_processes_timestamp ON processes(timestamp);
        CREATE INDEX IF NOT EXISTS idx_alerts_status_timestamp ON alerts(status,timestamp);
        CREATE INDEX IF NOT EXISTS idx_actions_state_requested ON actions(state,requested_at);
        CREATE INDEX IF NOT EXISTS idx_incidents_status_created ON incidents(status,created_at);
        CREATE INDEX IF NOT EXISTS idx_predictions_metric_created ON predictions(metric,created_at);
        CREATE INDEX IF NOT EXISTS idx_anomalies_status_created ON anomaly_findings(status,created_at);
        CREATE INDEX IF NOT EXISTS idx_service_snapshots_name_observed ON service_snapshots(service_name,observed_at);
        CREATE INDEX IF NOT EXISTS idx_impact_target_created ON impact_assessments(target,created_at);
        CREATE INDEX IF NOT EXISTS idx_risk_score_created ON risk_assessments(score,created_at);
        """)
        if connection.execute("SELECT 1 FROM users LIMIT 1").fetchone() is None:
            username = os.getenv("ADMIN_USERNAME", "admin")
            password = os.getenv("ADMIN_PASSWORD", "change-me-now")
            connection.execute("INSERT INTO users(username,password_hash,role,created_at) VALUES (?,?,?,?)", (username, hash_password(password), "administrator", now()))


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 210_000)
    return f"pbkdf2_sha256$210000${salt.hex()}${digest.hex()}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, rounds, salt, digest = encoded.split("$")
        candidate = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), int(rounds)).hex()
        return algorithm == "pbkdf2_sha256" and hmac.compare_digest(candidate, digest)
    except (ValueError, TypeError):
        return False


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=256)


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=256)
    new_password: str = Field(min_length=12, max_length=256)


class ActionRequest(BaseModel):
    action_type: str = Field(min_length=1, max_length=16)
    target: str = Field(min_length=1, max_length=128)
    reason: str = Field(min_length=8, max_length=1000)
    incident_id: int | None = Field(default=None, ge=1)


class UserCreateRequest(BaseModel):
    username: str = Field(min_length=3, max_length=64, pattern=r"^[A-Za-z0-9_.-]+$")
    password: str = Field(min_length=12, max_length=256)
    role: str = Field(default="operator", pattern=r"^(operator|administrator)$")


class ActionDecisionRequest(BaseModel):
    decision: str = Field(pattern=r"^(approve|reject)$")
    reason: str = Field(min_length=5, max_length=1000)


class IncidentUpdateRequest(BaseModel):
    status: str = Field(pattern=r"^(open|investigating|resolved|closed)$")
    resolution_notes: str | None = Field(default=None, max_length=4000)
    assigned_to: int | None = Field(default=None, ge=1)


class RecommendationUpdateRequest(BaseModel):
    status: str = Field(pattern=r"^(active|dismissed|resolved)$")


class ConfigUpdateRequest(BaseModel):
    cpu_alert_threshold: float = Field(ge=1, le=100)
    memory_alert_threshold: float = Field(ge=1, le=100)
    disk_alert_threshold: float = Field(ge=1, le=100)


def current_user(request: Request) -> dict[str, Any]:
    authorization = request.headers.get("Authorization", "")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    token_hash = hash_token(token.strip())
    with db() as connection:
        row = connection.execute(
            "SELECT users.id, users.username, users.role, sessions.expires_at "
            "FROM sessions JOIN users ON users.id=sessions.user_id WHERE sessions.token_hash=?",
            (token_hash,),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
        if datetime.fromisoformat(row["expires_at"]) <= datetime.now(timezone.utc):
            connection.execute("DELETE FROM sessions WHERE token_hash=?", (token_hash,))
            connection.commit()
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session expired")
    return {"id": row["id"], "username": row["username"], "role": row["role"]}


def administrator(user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    if user["role"] != "administrator":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Administrator role required")
    return user


def record_alert(alert_type: str, severity: str, message: str, source: str) -> None:
    with db() as connection:
        if connection.execute(
            "SELECT 1 FROM alerts WHERE alert_type=? AND source=? AND status IN ('open','acknowledged') LIMIT 1",
            (alert_type, source),
        ).fetchone():
            return
        timestamp = now()
        cursor = connection.execute(
            "INSERT INTO alerts(timestamp,alert_type,severity,message,status,source) VALUES (?,?,?,?,?,?)",
            (timestamp, alert_type, severity, message, "open", source),
        )
        connection.execute(
            "INSERT OR IGNORE INTO incidents(incident_key,title,description,severity,component,linked_alert_id,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?)",
            (f"alert:{cursor.lastrowid}", f"{alert_type.replace('_', ' ').title()} detected", message, severity, source, cursor.lastrowid, timestamp, timestamp),
        )


def track_service_failures(inventory: list[dict[str, Any]]) -> None:
    observed = {item["name"]: item["active"] for item in inventory}
    for name, active in observed.items():
        if active == "failed":
            record_alert("service_failure", "high", f"systemd reports {name}.service in a failed state.", name)
    with db() as connection:
        for name, active in observed.items():
            if active != "failed":
                timestamp = now()
                connection.execute("UPDATE alerts SET status='resolved' WHERE alert_type='service_failure' AND source=? AND status IN ('open','acknowledged')", (name,))
                connection.execute("UPDATE incidents SET status='resolved',resolved_at=?,updated_at=? WHERE component=? AND linked_alert_id IN (SELECT id FROM alerts WHERE alert_type='service_failure') AND status IN ('open','investigating')", (timestamp, timestamp, name))


def collect_metrics() -> dict[str, Any]:
    disk_path = Path("/") if os.name != "nt" else Path(Path.cwd().anchor)
    timestamp = now()
    memory = psutil.virtual_memory()
    disk = psutil.disk_usage(str(disk_path))
    network = psutil.net_io_counters()
    io = psutil.disk_io_counters()
    cpu = float(psutil.cpu_percent(interval=0.1))
    load_available = hasattr(os, "getloadavg")
    load = round(os.getloadavg()[0], 2) if load_available else 0.0
    received = int(network.bytes_recv) if network else 0
    sent = int(network.bytes_sent) if network else 0
    interfaces = {}
    interface_counters = psutil.net_io_counters(pernic=True) or {}
    interface_stats = psutil.net_if_stats() or {}
    for name, counters in interface_counters.items():
        interface = interface_stats.get(name)
        interfaces[name] = {
            "bytes_received": int(counters.bytes_recv), "bytes_sent": int(counters.bytes_sent),
            "is_up": bool(interface.isup) if interface else None,
            "speed_mbps": int(interface.speed) if interface and interface.speed else None,
        }
    with db() as connection:
        previous = connection.execute("SELECT timestamp,network_received,network_sent FROM system_metrics ORDER BY id DESC LIMIT 1").fetchone()
    receive_rate = send_rate = 0.0
    if previous and network:
        with suppress(ValueError, TypeError):
            elapsed = max(0.001, (datetime.fromisoformat(timestamp) - datetime.fromisoformat(previous["timestamp"])).total_seconds())
            receive_rate = max(0.0, (received - previous["network_received"]) / elapsed)
            send_rate = max(0.0, (sent - previous["network_sent"]) / elapsed)
    process_count = len(psutil.pids())
    metric = {
        "timestamp": timestamp, "cpu_usage": cpu, "memory_usage": float(memory.percent),
        "memory_available": int(memory.available), "disk_usage": float(disk.percent),
        "disk_total_bytes": int(disk.total), "disk_used_bytes": int(disk.used),
        "disk_read_bytes": int(io.read_bytes) if io else 0, "disk_write_bytes": int(io.write_bytes) if io else 0,
        "network_received": received, "network_sent": sent,
        "network_received_rate": receive_rate, "network_sent_rate": send_rate,
        "load_average": load, "process_count": process_count,
            "available_metrics": {"network": network is not None, "disk_io": io is not None, "load_average": load_available},
        "interface_stats": interfaces,
    }
    if not all(math.isfinite(float(metric[key])) for key in ("cpu_usage", "memory_usage", "disk_usage")):
        raise ValueError("Collected utilization metrics must be finite numbers")
    if any(not 0 <= metric[key] <= 100 for key in ("cpu_usage", "memory_usage", "disk_usage")):
        raise ValueError("Collected utilization metrics must be between 0 and 100")
    with db() as connection:
        cursor = connection.execute(
            "INSERT INTO system_metrics(timestamp,cpu_usage,memory_usage,disk_usage,network_received,network_sent,load_average,memory_available,disk_total_bytes,disk_used_bytes,disk_read_bytes,disk_write_bytes,network_received_rate,network_sent_rate,interface_stats,process_count,availability_json) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (timestamp, cpu, memory.percent, disk.percent, received, sent, load, memory.available, disk.total, disk.used, metric["disk_read_bytes"], metric["disk_write_bytes"], receive_rate, send_rate, json.dumps(interfaces), process_count, json.dumps(metric["available_metrics"])),
        )
        metric["id"] = cursor.lastrowid
    collect_process_snapshots()
    thresholds = effective_thresholds()
    if metric["cpu_usage"] > thresholds["cpu_alert_threshold"]:
        record_alert("cpu_threshold", "high", f"CPU utilization reached {metric['cpu_usage']:.1f}%, above the configured threshold.", "system")
    if metric["memory_usage"] > thresholds["memory_alert_threshold"]:
        record_alert("memory_threshold", "high", f"Memory utilization reached {metric['memory_usage']:.1f}%, above the configured threshold.", "system")
    if metric["disk_usage"] > thresholds["disk_alert_threshold"]:
        record_alert("disk_threshold", "medium", f"Disk utilization reached {metric['disk_usage']:.1f}%, above the configured threshold.", "filesystem")
    metric_rows = fetch_metric_history(200)
    findings = detect_anomalies(metric_rows)
    latest_finding = next((item for item in reversed(findings) if item.get("id") == metric["id"] and item.get("is_anomaly")), None)
    if latest_finding:
        persist_anomaly(latest_finding)
    if len(metric_rows) >= 12:
        persist_forecasts(forecast_resources(metric_rows))
    with db() as connection:
        connection.execute("UPDATE collector_state SET status='running',last_success_at=?,last_error=NULL,observation_count=observation_count+1,updated_at=? WHERE id=1", (timestamp, timestamp))
    return metric


def fetch_metric_history(limit: int = 500) -> list[dict[str, Any]]:
    with db() as connection:
        rows = connection.execute("SELECT * FROM system_metrics ORDER BY id DESC LIMIT ?", (min(max(limit, 1), 5000),)).fetchall()
    history = [dict(row) for row in reversed(rows)]
    for row in history:
        with suppress(ValueError, TypeError, json.JSONDecodeError):
            row["interface_stats"] = json.loads(row.get("interface_stats") or "{}")
            row["available_metrics"] = json.loads(row.get("availability_json") or "{}")
    return history


def effective_thresholds() -> dict[str, float]:
    values = {"cpu_alert_threshold": float(os.getenv("CPU_ALERT_THRESHOLD", "85")), "memory_alert_threshold": float(os.getenv("MEMORY_ALERT_THRESHOLD", "85")), "disk_alert_threshold": float(os.getenv("DISK_ALERT_THRESHOLD", "90"))}
    with db() as connection:
        rows = connection.execute("SELECT key,value_json FROM app_config WHERE key IN ('cpu_alert_threshold','memory_alert_threshold','disk_alert_threshold')").fetchall()
    for row in rows:
        with suppress(ValueError, TypeError, json.JSONDecodeError):
            values[row["key"]] = float(json.loads(row["value_json"]))
    return values


def persist_anomaly(finding: dict[str, Any]) -> None:
    metric_id = finding.get("id")
    metric_name = str(finding.get("dominant_metric") or "cpu_usage")
    value = float(finding.get(metric_name) or 0)
    explanation = finding.get("explanation", "The observation differs from its historical baseline.")
    with db() as connection:
        connection.execute(
            "INSERT OR IGNORE INTO anomaly_findings(metric_id,metric,component,observed_value,baseline,severity,detection_method,score,explanation,created_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (metric_id, metric_name, "host", value, finding.get("baseline_value"), "medium", finding.get("detection_method", "statistical"), finding.get("anomaly_score"), explanation, finding.get("timestamp", now())),
        )
    record_alert("statistical_anomaly", "medium", explanation, "system")


def persist_forecasts(forecasts: list[dict[str, Any]]) -> None:
    timestamp = now()
    with db() as connection:
        for item in forecasts:
            if item.get("status") != "forecasted":
                continue
            connection.execute("INSERT INTO evaluation_runs(model_name,model_version,evaluation_method,metrics_json,sample_count,created_at) VALUES (?,?,?,?,?,?)", (item["metric"], item["model_version"], "chronological_walk_forward_vs_last_value", json.dumps({"selected_method": item["method"], "walk_forward_mae": item["walk_forward_mae"], "last_value_baseline_mae": item["baseline_mae"], "evaluation_count": item["evaluation_count"]}), item["evaluation_count"], timestamp))
            connection.execute(
                "INSERT INTO predictions(metric,method,model_version,observed_at,forecast_at,horizon_hours,observed_value,predicted_value,threshold,estimated_hours_to_threshold,walk_forward_mae,baseline_mae,evaluation_count,sample_count,confidence_score,explanation,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (item["metric"], item["method"], item["model_version"], item["observed_at"], item["forecast_at"], item["horizon_hours"], item["observed_value"], item["predicted_value"], item["threshold"], item["estimated_hours_to_threshold"], item["walk_forward_mae"], item["baseline_mae"], item["evaluation_count"], item["sample_count"], item["confidence_score"], item["explanation"], timestamp),
            )
        connection.execute("INSERT OR IGNORE INTO model_versions(name,version,method,sample_count,parameters_json,created_at) VALUES (?,?,?,?,?,?)", ("resource_forecast", "resource-trend-v1", "chronological linear trend compared with last-value baseline", max((item.get("sample_count", 0) for item in forecasts), default=0), json.dumps({"horizon_hours": 1, "minimum_samples": 12}), timestamp))


def collect_process_snapshots() -> list[dict[str, Any]]:
    processes = list(psutil.process_iter())
    for process in processes:
        with suppress(psutil.Error):
            process.cpu_percent(None)
    time.sleep(0.1)
    rows = [row for process in processes if (row := process_row(process))]
    rows.sort(key=lambda row: row["cpu_usage"], reverse=True)
    snapshot_time = now()
    with db() as connection:
        connection.executemany(
            "INSERT INTO processes(timestamp,pid,process_name,cpu_usage,memory_usage,status,username,start_time,command,memory_bytes) VALUES (?,?,?,?,?,?,?,?,?,?)",
            [(snapshot_time, row["pid"], row["name"], row["cpu_usage"], row["memory_usage"], row["status"], row.get("user"), row.get("start_time"), row.get("command"), row.get("memory_bytes", 0)) for row in rows[:100]],
        )
    return rows


def process_row(process: psutil.Process) -> dict[str, Any] | None:
    try:
        with process.oneshot():
            command = process.cmdline()
            safe_command = []
            redact_next = False
            for arg in command:
                if redact_next:
                    safe_command.append("[REDACTED]")
                    redact_next = False
                    continue
                if re.search(r"(?i)(password|passwd|token|secret|api[-_]?key|credential)", arg):
                    if "=" in arg:
                        safe_command.append(arg.split("=", 1)[0] + "=[REDACTED]")
                    else:
                        safe_command.append(arg)
                        redact_next = True
                else:
                    safe_command.append(arg)
            memory_info = process.memory_info()
            return {"pid": process.pid, "name": process.name(), "cpu_usage": process.cpu_percent(None), "memory_usage": process.memory_percent(), "memory_bytes": int(memory_info.rss), "status": process.status(), "user": process.username(), "start_time": datetime.fromtimestamp(process.create_time(), timezone.utc).isoformat(), "command": " ".join(safe_command)[:500]}
    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
        return None


def linux_command(args: list[str], timeout: int = 5) -> str:
    if os.name != "posix":
        return ""
    try:
        return subprocess.run(args, check=False, capture_output=True, text=True, timeout=timeout).stdout
    except (OSError, subprocess.TimeoutExpired):
        return ""


def run_service_operation(name: str, operation: str) -> tuple[int, str]:
    if os.name != "posix":
        return 1, "systemd is unavailable on this host"
    try:
        completed = subprocess.run(["systemctl", operation, f"{name}.service"], check=False, capture_output=True, text=True, timeout=15)
        return completed.returncode, (completed.stdout + completed.stderr).strip()
    except (OSError, subprocess.TimeoutExpired) as error:
        return 1, str(error)


def refresh_service_inventory() -> list[dict[str, Any]]:
    if os.name != "posix" or not shutil.which("systemctl"):
        return []
    units = linux_command(["systemctl", "list-units", "--type=service", "--all", "--no-legend", "--no-pager"])
    files = linux_command(["systemctl", "list-unit-files", "--type=service", "--no-legend", "--no-pager"])
    enabled = {}
    for line in files.splitlines():
        parts = line.split()
        if len(parts) >= 2:
            enabled[parts[0].removesuffix(".service")] = parts[1]
    observed_at = now()
    result = []
    for line in units.splitlines():
        parts = line.split(None, 4)
        if len(parts) < 4:
            continue
        name = parts[0].removesuffix(".service")
        result.append({
            "name": name, "load": parts[1], "active": parts[2], "status": parts[3],
            "description": parts[4] if len(parts) == 5 else "",
            "unit_file_state": enabled.get(name, "unknown"), "checked_at": observed_at, "allowed": name in ALLOWED_SERVICES,
        })
    with db() as connection:
        for service in result:
            existing = connection.execute("SELECT id FROM services WHERE service_name=? ORDER BY id DESC LIMIT 1", (service["name"],)).fetchone()
            values = (service["status"], int(enabled.get(service["name"]) in {"enabled", "enabled-runtime"}), observed_at, service["active"], service["load"], service["description"], service["unit_file_state"])
            if existing:
                connection.execute("UPDATE services SET status=?,enabled=?,checked_at=?,active=?,load=?,description=?,unit_file_state=? WHERE id=?", (*values, existing["id"]))
            else:
                connection.execute("INSERT INTO services(service_name,status,enabled,checked_at,active,load,description,unit_file_state) VALUES (?,?,?,?,?,?,?,?)", (service["name"], *values))
            connection.execute(
                "INSERT OR IGNORE INTO service_snapshots(service_name,active,sub_state,load_state,enabled_state,description,observed_at) VALUES (?,?,?,?,?,?,?)",
                (service["name"], service["active"], service["status"], service["load"], service["unit_file_state"], service["description"], observed_at),
            )
    return result


def refresh_dependencies(services: list[str] | None = None) -> list[dict[str, Any]]:
    if os.name != "posix" or not shutil.which("systemctl"):
        return []
    targets = services or sorted(ALLOWED_SERVICES)
    relationships = ("Requires", "Wants", "BindsTo", "PartOf", "Before", "After", "RequiredBy", "WantedBy", "BoundBy", "ConsistsOf")
    observed_at = now()
    edges = []
    for service in targets[:100]:
        if not re.fullmatch(r"[A-Za-z0-9_.@:-]+", service):
            continue
        properties = ",".join(relationships)
        output = linux_command(["systemctl", "show", f"{service}.service", "--no-pager", f"--property={properties}"])
        values = dict(line.split("=", 1) for line in output.splitlines() if "=" in line)
        for relationship in relationships:
            for item in filter(None, values.get(relationship, "").split()):
                name = item.removesuffix(".service")
                if name == service:
                    continue
                incoming = relationship in {"RequiredBy", "WantedBy", "BoundBy"}
                edges.append({"source_service": name if incoming else service, "target_service": service if incoming else name, "relationship": relationship, "source": "systemctl show", "observed_at": observed_at})
    with db() as connection:
        for edge in edges:
            connection.execute(
                "INSERT INTO service_dependencies(source_service,target_service,relationship,source,observed_at) VALUES (?,?,?,?,?) ON CONFLICT(source_service,target_service,relationship) DO UPDATE SET source=excluded.source,observed_at=excluded.observed_at",
                (edge["source_service"], edge["target_service"], edge["relationship"], edge["source"], edge["observed_at"]),
            )
    return edges


def cleanup_retention() -> None:
    cutoff = (datetime.now(timezone.utc) - timedelta(days=RETENTION_DAYS)).isoformat()
    with db() as connection:
        for table, timestamp_column in (("system_metrics", "timestamp"), ("processes", "timestamp"), ("services", "checked_at"), ("logs", "timestamp"), ("predictions", "created_at")):
            connection.execute(f"DELETE FROM {table} WHERE {timestamp_column} < ?", (cutoff,))


def collector_loop() -> None:
    with db() as connection:
        connection.execute("UPDATE collector_state SET status='running',last_error=NULL,updated_at=? WHERE id=1", (now(),))
    while not collector_stop.is_set():
        attempt = now()
        with db() as connection:
            connection.execute("UPDATE collector_state SET last_attempt_at=?,updated_at=? WHERE id=1", (attempt, attempt))
        try:
            inventory = refresh_service_inventory()
            track_service_failures(inventory)
            refresh_dependencies(sorted(ALLOWED_SERVICES))
            collect_metrics()
            cleanup_retention()
            if not inventory and os.name != "posix":
                logger.info("systemd integration unavailable on %s; host metrics are still collected", os.name)
        except Exception as error:
            logger.exception("Metric collection failed")
            with db() as connection:
                connection.execute("UPDATE collector_state SET status='degraded',last_error=?,updated_at=? WHERE id=1", (str(error)[:500], now()))
        collector_stop.wait(COLLECTOR_INTERVAL_SECONDS)


@app.on_event("startup")
def startup() -> None:
    init_db()
    with db() as connection:
        connection.execute("DELETE FROM sessions WHERE expires_at <= ?", (now(),))
        connection.execute("INSERT OR IGNORE INTO collector_state(id,status,updated_at) VALUES (1,?,?)", ("starting" if COLLECTOR_ENABLED else "disabled", now()))
    if COLLECTOR_ENABLED:
        global collector_thread
        collector_stop.clear()
        collector_thread = threading.Thread(target=collector_loop, name="linux-admin-collector", daemon=True)
        collector_thread.start()


@app.on_event("shutdown")
def shutdown() -> None:
    collector_stop.set()
    if collector_thread and collector_thread.is_alive():
        collector_thread.join(timeout=COLLECTOR_INTERVAL_SECONDS + 2)
    with db() as connection:
        connection.execute("UPDATE collector_state SET status='stopped',updated_at=? WHERE id=1", (now(),))


@app.get("/api/health")
def health() -> dict[str, Any]:
    with db() as connection:
        state = connection.execute("SELECT * FROM collector_state WHERE id=1").fetchone()
    collector = dict(state) if state else {"status": "not_initialized", "last_success_at": None, "last_error": None, "observation_count": 0}
    return {"status": "degraded" if collector.get("status") == "degraded" else "ok", "platform": platform.platform(), "linux_integration": os.name == "posix" and shutil.which("systemctl") is not None, "collector": collector, "collection_interval_seconds": COLLECTOR_INTERVAL_SECONDS, "retention_days": RETENTION_DAYS}


@app.post("/api/auth/login")
def login(payload: LoginRequest, request: Request) -> dict[str, Any]:
    client = request.client.host if request.client else "unknown"
    count, first_failure = login_failures.get(client, (0, time.monotonic()))
    if count >= LOGIN_FAILURE_LIMIT and time.monotonic() - first_failure < LOGIN_WINDOW_SECONDS:
        raise HTTPException(status_code=429, detail="Too many login attempts. Try again later.", headers={"Retry-After": str(max(1, int(LOGIN_WINDOW_SECONDS - (time.monotonic() - first_failure))))})
    with db() as connection:
        row = connection.execute("SELECT id,username,password_hash,role FROM users WHERE username=?", (payload.username,)).fetchone()
    if not row or not verify_password(payload.password, row["password_hash"]):
        if time.monotonic() - first_failure >= LOGIN_WINDOW_SECONDS:
            login_failures[client] = (1, time.monotonic())
        else:
            login_failures[client] = (count + 1, first_failure)
        raise HTTPException(status_code=401, detail="Invalid username or password")
    login_failures.pop(client, None)
    token = secrets.token_urlsafe(32)
    user = {"id": row["id"], "username": row["username"], "role": row["role"]}
    created_at = datetime.now(timezone.utc)
    expires_at = created_at + timedelta(hours=SESSION_TTL_HOURS)
    with db() as connection:
        connection.execute(
            "INSERT INTO sessions(token_hash,user_id,created_at,expires_at) VALUES (?,?,?,?)",
            (hash_token(token), user["id"], created_at.isoformat(), expires_at.isoformat()),
        )
        connection.execute("INSERT INTO audit_logs(user_id,action,target,timestamp,result) VALUES (?,?,?,?,?)", (user["id"], "login", user["username"], now(), "success"))
    return {"token": token, "user": user}


@app.get("/api/users")
def users(user: dict[str, Any] = Depends(administrator)) -> list[dict[str, Any]]:
    with db() as connection:
        return [dict(row) for row in connection.execute("SELECT id,username,role,created_at FROM users ORDER BY username")]


@app.post("/api/users", status_code=201)
def create_user(payload: UserCreateRequest, user: dict[str, Any] = Depends(administrator)) -> dict[str, Any]:
    with db() as connection:
        try:
            cursor = connection.execute("INSERT INTO users(username,password_hash,role,created_at) VALUES (?,?,?,?)", (payload.username, hash_password(payload.password), payload.role, now()))
        except sqlite3.IntegrityError as error:
            raise HTTPException(status_code=409, detail="Username already exists") from error
        connection.execute("INSERT INTO audit_logs(user_id,action,target,timestamp,result) VALUES (?,?,?,?,?)", (user["id"], "create_user", payload.username, now(), f"role={payload.role}"))
        row = connection.execute("SELECT id,username,role,created_at FROM users WHERE id=?", (cursor.lastrowid,)).fetchone()
    return dict(row)


@app.post("/api/auth/change-password")
def change_password(payload: ChangePasswordRequest, user: dict[str, Any] = Depends(administrator)) -> dict[str, str]:
    with db() as connection:
        row = connection.execute("SELECT password_hash FROM users WHERE id=?", (user["id"],)).fetchone()
        if not row or not verify_password(payload.current_password, row["password_hash"]):
            raise HTTPException(status_code=400, detail="Current password is incorrect")
        if hmac.compare_digest(payload.current_password, payload.new_password):
            raise HTTPException(status_code=400, detail="New password must be different")
        connection.execute("UPDATE users SET password_hash=? WHERE id=?", (hash_password(payload.new_password), user["id"]))
        connection.execute(
            "INSERT INTO audit_logs(user_id,action,target,timestamp,result) VALUES (?,?,?,?,?)",
            (user["id"], "change_password", user["username"], now(), "success"),
        )
        connection.execute("DELETE FROM sessions WHERE user_id=?", (user["id"],))
    return {"status": "password_changed"}


@app.post("/api/auth/logout")
def logout(request: Request, user: dict[str, Any] = Depends(current_user)) -> dict[str, str]:
    token = request.headers.get("Authorization", "").partition(" ")[2].strip()
    with db() as connection:
        connection.execute("DELETE FROM sessions WHERE token_hash=?", (hash_token(token),))
    return {"status": "logged_out"}


@app.get("/api/system/info")
def system_info(user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    return {"hostname": platform.node(), "os": platform.platform(), "kernel": platform.release(), "architecture": platform.machine(), "uptime_seconds": int(time.time() - psutil.boot_time()), "cpu_count": psutil.cpu_count(), "python": platform.python_version()}


@app.get("/api/system/metrics")
def metrics(limit: int = Query(60, ge=1, le=500), user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    history = fetch_metric_history(limit)
    if not history:
        history = [collect_metrics()]
    latest = history[-1]
    age = max(0.0, (datetime.now(timezone.utc) - datetime.fromisoformat(latest["timestamp"])).total_seconds())
    return {"latest": latest, "history": history, "age_seconds": round(age, 1), "stale": age > COLLECTOR_INTERVAL_SECONDS * 3}


@app.get("/api/system/metrics/history")
def metric_history(start: str | None = None, end: str | None = None, limit: int = Query(500, ge=1, le=5000), user: dict[str, Any] = Depends(current_user)) -> list[dict[str, Any]]:
    clauses, values = [], []
    for column, value in (("timestamp >=", start), ("timestamp <=", end)):
        if value:
            try:
                datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError as error:
                raise HTTPException(status_code=422, detail="Time filters must be ISO-8601 timestamps") from error
            clauses.append(column + " ?")
            values.append(value)
    where = " WHERE " + " AND ".join(clauses) if clauses else ""
    with db() as connection:
        rows = connection.execute(f"SELECT * FROM system_metrics{where} ORDER BY timestamp DESC LIMIT ?", (*values, limit)).fetchall()
    return list(reversed([dict(row) for row in rows]))


@app.get("/api/system/disk")
def disk_info(user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    partitions = []
    for partition in psutil.disk_partitions(all=False):
        try:
            usage = psutil.disk_usage(partition.mountpoint)
        except (PermissionError, OSError):
            continue
        partitions.append({"device": partition.device, "mountpoint": partition.mountpoint, "filesystem": partition.fstype, "total_bytes": usage.total, "used_bytes": usage.used, "free_bytes": usage.free, "percent": usage.percent})
    io = psutil.disk_io_counters(perdisk=True) or {}
    io_summary = {name: {"read_bytes": value.read_bytes, "write_bytes": value.write_bytes, "read_count": value.read_count, "write_count": value.write_count} for name, value in io.items()}
    return {"partitions": partitions, "io": io_summary, "observed_at": now()}


@app.get("/api/system/health")
def system_health(user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    history = fetch_metric_history(1)
    metric = history[-1] if history else None
    if not metric:
        return {"status": "unknown", "metric": None, "reason": "No metric observations have been collected."}
    stale = (datetime.now(timezone.utc) - datetime.fromisoformat(metric["timestamp"])).total_seconds() > COLLECTOR_INTERVAL_SECONDS * 3
    with db() as connection:
        failed_services = connection.execute("SELECT COUNT(*) AS count FROM services WHERE active='failed' AND checked_at=(SELECT MAX(checked_at) FROM services)").fetchone()["count"]
        open_alerts = connection.execute("SELECT COUNT(*) AS count FROM alerts WHERE status='open'").fetchone()["count"]
    degraded = metric["cpu_usage"] > 85 or metric["memory_usage"] > 85 or metric["disk_usage"] > 90 or failed_services > 0 or open_alerts > 0
    status_value = "stale" if stale else "degraded" if degraded else "healthy"
    return {"status": status_value, "metric": metric, "failed_service_count": failed_services, "open_alert_count": open_alerts}


@app.get("/api/processes")
def processes(limit: int = Query(200, ge=1, le=500), user: dict[str, Any] = Depends(current_user)) -> list[dict[str, Any]]:
    collect_process_snapshots()
    with db() as connection:
        snapshot = connection.execute("SELECT MAX(timestamp) AS timestamp FROM processes").fetchone()["timestamp"]
        rows = connection.execute("SELECT * FROM processes WHERE timestamp=? ORDER BY cpu_usage DESC LIMIT ?", (snapshot, limit)).fetchall() if snapshot else []
    return [{"pid": row["pid"], "name": row["process_name"], "cpu_usage": row["cpu_usage"], "memory_usage": row["memory_usage"], "memory_bytes": row["memory_bytes"], "status": row["status"], "user": row["username"], "start_time": row["start_time"], "command": row["command"], "timestamp": row["timestamp"]} for row in rows]


@app.get("/api/processes/{pid}")
def process_detail(pid: int, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    try:
        process = psutil.Process(pid)
        process.cpu_percent(None)
        time.sleep(0.1)
        row = process_row(process)
    except psutil.NoSuchProcess:
        row = None
    if not row:
        raise HTTPException(status_code=404, detail="Process not found or inaccessible")
    return row


@app.get("/api/services")
def services(user: dict[str, Any] = Depends(current_user)) -> list[dict[str, Any]]:
    result = refresh_service_inventory()
    with db() as connection:
        rows = connection.execute("SELECT * FROM services WHERE checked_at=(SELECT MAX(checked_at) FROM services) ORDER BY service_name").fetchall()
    if rows:
        result = [{"name": row["service_name"], "load": row["load"], "active": row["active"], "status": row["status"], "description": row["description"], "enabled": bool(row["enabled"]), "unit_file_state": row["unit_file_state"], "checked_at": row["checked_at"], "allowed": row["service_name"] in ALLOWED_SERVICES} for row in rows]
    return result


@app.get("/api/services/{name}")
def service_detail(name: str, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    if name not in ALLOWED_SERVICES:
        raise HTTPException(status_code=403, detail="Service is not in the controlled allowlist")
    if not re.fullmatch(r"[A-Za-z0-9_.@:-]+", name):
        raise HTTPException(status_code=400, detail="Invalid service name")
    output = linux_command(["systemctl", "show", f"{name}.service", "--no-pager", "--property=Id,Description,ActiveState,SubState,UnitFileState"])
    if not output:
        raise HTTPException(status_code=503, detail="systemd is unavailable on this host")
    return dict(line.split("=", 1) for line in output.splitlines() if "=" in line)


@app.get("/api/dependencies")
def dependency_graph(service: str | None = None, depth: int = Query(2, ge=1, le=5), user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    if service and not re.fullmatch(r"[A-Za-z0-9_.@:-]+", service):
        raise HTTPException(status_code=422, detail="Invalid service name")
    with db() as connection:
        count = connection.execute("SELECT COUNT(*) AS count FROM service_dependencies").fetchone()["count"]
    if count == 0 and os.name == "posix":
        refresh_dependencies()
    with db() as connection:
        rows = connection.execute("SELECT * FROM service_dependencies ORDER BY source_service,target_service LIMIT 2000").fetchall()
    edges = [dict(row) for row in rows]
    if service:
        selected, frontier = set(), {service.removesuffix(".service")}
        for _ in range(depth):
            next_frontier = set()
            for edge in edges:
                if edge["source_service"] in frontier or edge["target_service"] in frontier:
                    selected.add((edge["source_service"], edge["target_service"], edge["relationship"]))
                    next_frontier.update({edge["source_service"], edge["target_service"]} - frontier)
            frontier = next_frontier
        edges = [edge for edge in edges if (edge["source_service"], edge["target_service"], edge["relationship"]) in selected]
    nodes = sorted({edge["source_service"] for edge in edges} | {edge["target_service"] for edge in edges})
    return {"nodes": nodes, "edges": edges, "source": "systemctl show", "coverage": "available" if edges else "unknown_or_unavailable", "note": "Requires/Wants and ordering relationships are preserved as separate edge types; an ordering edge does not prove functional dependency."}


@app.get("/api/logs")
def logs(limit: int = Query(100, ge=1, le=500), severity: str | None = None, service: str | None = None, search: str | None = None, user: dict[str, Any] = Depends(current_user)) -> list[dict[str, Any]]:
    args = ["journalctl", "-n", str(limit), "--no-pager", "-o", "json"]
    if service:
        if not re.fullmatch(r"[A-Za-z0-9_.@:-]+", service):
            raise HTTPException(status_code=422, detail="Invalid service filter")
        args.extend(["-u", service])
    raw = linux_command(args)
    result = []
    for line in raw.splitlines():
        try:
            item = json.loads(line)
            message = str(item.get("MESSAGE", ""))
            priority = {"0": "emergency", "1": "alert", "2": "critical", "3": "error", "4": "warning", "5": "notice", "6": "info", "7": "debug"}.get(str(item.get("PRIORITY", "6")), "info")
            raw_timestamp = item.get("__REALTIME_TIMESTAMP")
            try:
                timestamp = datetime.fromtimestamp(int(raw_timestamp) / 1_000_000, timezone.utc).isoformat()
            except (TypeError, ValueError, OSError, OverflowError):
                timestamp = now()
            row = {"timestamp": timestamp, "source": item.get("SYSLOG_IDENTIFIER", item.get("_SYSTEMD_UNIT", "system")), "unit": item.get("_SYSTEMD_UNIT"), "severity": priority, "message": str(message)[:4000], "journal_cursor": item.get("__CURSOR")}
            if (not severity or priority == severity) and (not search or search.lower() in message.lower()):
                result.append(row)
        except json.JSONDecodeError:
            continue
    with db() as connection:
        for item in result:
            connection.execute("INSERT OR IGNORE INTO logs(timestamp,source,severity,message,unit,journal_cursor) VALUES (?,?,?,?,?,?)", (item["timestamp"], item["source"], item["severity"], item["message"], item["unit"], item["journal_cursor"]))
    return result


@app.get("/api/alerts")
def alerts(user: dict[str, Any] = Depends(current_user)) -> list[dict[str, Any]]:
    with db() as connection:
        return [dict(row) for row in connection.execute("SELECT * FROM alerts ORDER BY id DESC LIMIT 200")]


@app.patch("/api/alerts/{alert_id}/acknowledge")
def acknowledge_alert(alert_id: int, user: dict[str, Any] = Depends(administrator)) -> dict[str, Any]:
    with db() as connection:
        result = connection.execute("UPDATE alerts SET status='acknowledged' WHERE id=? AND status='open'", (alert_id,))
        if result.rowcount == 0:
            exists = connection.execute("SELECT status FROM alerts WHERE id=?", (alert_id,)).fetchone()
            if not exists:
                raise HTTPException(status_code=404, detail="Alert not found")
        else:
            connection.execute(
                "INSERT INTO audit_logs(user_id,action,target,timestamp,result) VALUES (?,?,?,?,?)",
                (user["id"], "acknowledge_alert", str(alert_id), now(), "success"),
            )
        row = connection.execute("SELECT * FROM alerts WHERE id=?", (alert_id,)).fetchone()
    return dict(row)


@app.patch("/api/alerts/{alert_id}/resolve")
def resolve_alert(alert_id: int, user: dict[str, Any] = Depends(administrator)) -> dict[str, Any]:
    with db() as connection:
        row = connection.execute("SELECT * FROM alerts WHERE id=?", (alert_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Alert not found")
        connection.execute("UPDATE alerts SET status='resolved' WHERE id=?", (alert_id,))
        connection.execute("UPDATE incidents SET status='resolved',resolved_at=?,updated_at=? WHERE linked_alert_id=? AND status IN ('open','investigating')", (now(), now(), alert_id))
        connection.execute("INSERT INTO audit_logs(user_id,action,target,timestamp,result) VALUES (?,?,?,?,?)", (user["id"], "resolve_alert", str(alert_id), now(), "success"))
        updated = connection.execute("SELECT * FROM alerts WHERE id=?", (alert_id,)).fetchone()
    return dict(updated)


@app.get("/api/anomalies")
def anomalies(status_filter: str | None = None, limit: int = Query(100, ge=1, le=500), offset: int = Query(0, ge=0), user: dict[str, Any] = Depends(current_user)) -> list[dict[str, Any]]:
    if status_filter and status_filter not in {"open", "acknowledged", "resolved"}:
        raise HTTPException(status_code=422, detail="Invalid anomaly status filter")
    with db() as connection:
        if status_filter:
            rows = connection.execute("SELECT * FROM anomaly_findings WHERE status=? ORDER BY created_at DESC LIMIT ? OFFSET ?", (status_filter, limit, offset)).fetchall()
        else:
            rows = connection.execute("SELECT * FROM anomaly_findings ORDER BY created_at DESC LIMIT ? OFFSET ?", (limit, offset)).fetchall()
    return [dict(row) for row in rows]


@app.patch("/api/anomalies/{anomaly_id}")
def update_anomaly(anomaly_id: int, state: str = Query(..., pattern="^(acknowledged|resolved)$"), user: dict[str, Any] = Depends(administrator)) -> dict[str, Any]:
    with db() as connection:
        result = connection.execute("UPDATE anomaly_findings SET status=?,resolved_at=? WHERE id=? AND status!='resolved'", (state, now() if state == "resolved" else None, anomaly_id))
        row = connection.execute("SELECT * FROM anomaly_findings WHERE id=?", (anomaly_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Anomaly not found")
        if result.rowcount:
            connection.execute("INSERT INTO audit_logs(user_id,action,target,timestamp,result) VALUES (?,?,?,?,?)", (user["id"], f"{state}_anomaly", str(anomaly_id), now(), "success"))
    return dict(row)


@app.get("/api/predictions")
def predictions(metric: str | None = None, limit: int = Query(100, ge=1, le=500), offset: int = Query(0, ge=0), user: dict[str, Any] = Depends(current_user)) -> list[dict[str, Any]]:
    if metric and metric not in {"cpu_usage", "memory_usage", "disk_usage"}:
        raise HTTPException(status_code=422, detail="Unsupported forecast metric")
    with db() as connection:
        if metric:
            rows = connection.execute("SELECT * FROM predictions WHERE metric=? ORDER BY created_at DESC LIMIT ? OFFSET ?", (metric, limit, offset)).fetchall()
        else:
            rows = connection.execute("SELECT * FROM predictions ORDER BY created_at DESC LIMIT ? OFFSET ?", (limit, offset)).fetchall()
    return [dict(row) for row in rows]


@app.get("/api/models/status")
def model_status(user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    with db() as connection:
        models = [dict(row) for row in connection.execute("SELECT * FROM model_versions ORDER BY created_at DESC")]
        evaluations = [dict(row) for row in connection.execute("SELECT * FROM evaluation_runs ORDER BY created_at DESC LIMIT 50")]
        sample_count = connection.execute("SELECT COUNT(*) AS count FROM system_metrics").fetchone()["count"]
    return {"models": models, "evaluations": evaluations, "observation_count": sample_count, "anomaly_detector": "Isolation Forest when scikit-learn is installed; robust multivariate MAD fallback otherwise", "forecast_model": "resource-trend-v1 with chronological walk-forward evaluation; this estimates resource threshold crossing, not labeled system failure"}


@app.get("/api/root-causes")
def root_causes(limit: int = Query(50, ge=1, le=200), user: dict[str, Any] = Depends(current_user)) -> list[dict[str, Any]]:
    metric = fetch_metric_history(500)
    latest_metric = metric[-1] if metric else None
    with db() as connection:
        snapshot = connection.execute("SELECT MAX(timestamp) AS timestamp FROM processes").fetchone()["timestamp"]
        process_rows = connection.execute("SELECT pid,process_name,cpu_usage,memory_usage,username,status,timestamp FROM processes WHERE timestamp=? ORDER BY cpu_usage DESC LIMIT 100", (snapshot,)).fetchall() if snapshot else []
        service_time = connection.execute("SELECT MAX(checked_at) AS timestamp FROM services").fetchone()["timestamp"]
        service_rows = connection.execute("SELECT service_name AS name,active,status,checked_at,(SELECT previous.active FROM service_snapshots previous WHERE previous.service_name=services.service_name AND previous.observed_at < services.checked_at ORDER BY previous.observed_at DESC LIMIT 1) AS previous_active FROM services WHERE checked_at=?", (service_time,)).fetchall() if service_time else []
        log_rows = connection.execute("SELECT timestamp,source,unit,severity,message FROM logs ORDER BY id DESC LIMIT 200").fetchall()
        dependency_rows = connection.execute("SELECT source_service,target_service,relationship,source,observed_at FROM service_dependencies").fetchall()
        incident_rows = connection.execute("SELECT id,component,status,severity FROM incidents ORDER BY created_at DESC LIMIT 200").fetchall()
        action_rows = connection.execute("SELECT action_type,target,state,requested_by,requested_at,executed_at FROM actions ORDER BY requested_at DESC LIMIT 200").fetchall()
        anomaly_rows = connection.execute("SELECT metric,component,observed_value,baseline,explanation,created_at FROM anomaly_findings ORDER BY created_at DESC LIMIT 200").fetchall()
        prediction_rows = connection.execute("SELECT metric,predicted_value,estimated_hours_to_threshold,created_at FROM predictions ORDER BY created_at DESC LIMIT 50").fetchall()
    process_items = [{**dict(row), "name": row["process_name"], "user": row["username"]} for row in process_rows]
    findings = analyze_root_causes(latest_metric, process_items, [dict(row) for row in service_rows], [dict(row) for row in log_rows], [dict(row) for row in dependency_rows], [dict(row) for row in incident_rows], [dict(row) for row in action_rows], [dict(row) for row in anomaly_rows], [dict(row) for row in prediction_rows], metric)
    created = now()
    with db() as connection:
        for item in findings:
            evidence_json = json.dumps(item["evidence"])
            incident_ids = item.get("related_incidents") or [None]
            for incident_id in incident_ids:
                exists = connection.execute("SELECT 1 FROM root_cause_findings WHERE incident_id IS ? AND component=? AND hypothesis=? AND evidence_json=? LIMIT 1", (incident_id, item["component"], item["hypothesis"], evidence_json)).fetchone()
                if not exists:
                    connection.execute("INSERT INTO root_cause_findings(incident_id,component,hypothesis,confidence,confidence_definition,evidence_json,alternatives_json,diagnostics_json,created_at) VALUES (?,?,?,?,?,?,?,?,?)", (incident_id, item["component"], item["hypothesis"], item["confidence"], item["confidence_definition"], evidence_json, json.dumps(item["alternatives"]), json.dumps(item["diagnostics"]), created))
    return findings[:limit]


def _action_context(target: str, operation: str) -> tuple[str | None, list[dict[str, Any]], list[dict[str, Any]], dict[str, Any] | None]:
    service_state = None
    if os.name == "posix" and shutil.which("systemctl"):
        service_state = linux_command(["systemctl", "is-active", f"{target}.service"]).strip() or "unknown"
    with db() as connection:
        dependencies = [dict(row) for row in connection.execute("SELECT source_service,target_service,relationship,source FROM service_dependencies WHERE source_service=? OR target_service=?", (target, target))]
        active_alerts = [dict(row) for row in connection.execute("SELECT id,severity,status,source,alert_type FROM alerts WHERE status='open' UNION ALL SELECT id,severity,status,component AS source,'incident' AS alert_type FROM incidents WHERE status IN ('open','investigating') LIMIT 200")]
    latest = fetch_metric_history(1)
    return service_state, dependencies, active_alerts, latest[-1] if latest else None


def build_impact_report(operation: str, target: str, risk: dict[str, Any], coverage: str) -> dict[str, Any]:
    affected = risk.get("affected_services", [])
    return {
        "operation": operation, "target": target, "service_criticality": risk["factors"]["service_criticality"]["basis"],
        "potentially_affected_services": affected, "affected_count": len(affected),
        "classification": {"LOW": "low", "MEDIUM": "moderate", "HIGH": "high", "CRITICAL": "critical"}.get(risk["band"], "unknown"),
        "current_state": risk["factors"]["current_service_health"]["basis"],
        "coverage": coverage, "unknowns": risk["unknowns"],
        "verification_steps": [f"Confirm {target}.service reaches the expected state after {operation}.", "Check dependent service health and new alerts.", "Review the service journal for operation errors."],
        "recovery_readiness": risk["factors"]["recovery_readiness"],
    }


@app.get("/api/impact/{service}")
def impact_assessment(service: str, operation: str = Query("restart", pattern="^(start|stop|restart)$"), user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    if service not in ALLOWED_SERVICES:
        raise HTTPException(status_code=403, detail="Service is not in the controlled allowlist")
    state, dependencies, active_alerts, metric = _action_context(service, operation)
    risk = assess_action(operation, service, state, dependencies, active_alerts, metric)
    coverage = "systemd evidence available" if state else "systemd state unavailable"
    impact = build_impact_report(operation, service, risk, coverage)
    assessed_at = now()
    with db() as connection:
        connection.execute("INSERT INTO impact_assessments(actor_id,operation,target,report_json,created_at) VALUES (?,?,?,?,?)", (user["id"], operation, service, json.dumps(impact), assessed_at))
        connection.execute("INSERT INTO risk_assessments(actor_id,score,band,factors_json,policy_json,created_at) VALUES (?,?,?,?,?,?)", (user["id"], risk["score"], risk["band"], json.dumps(risk["factors"]), json.dumps(risk["policy"]), assessed_at))
    return {"assessed_at": assessed_at, "impact": impact, "risk": risk}


@app.get("/api/risk/{service}")
def risk_assessment(service: str, operation: str = Query("restart", pattern="^(start|stop|restart)$"), user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    if service not in ALLOWED_SERVICES:
        raise HTTPException(status_code=403, detail="Service is not in the controlled allowlist")
    state, dependencies, alerts_data, metric = _action_context(service, operation)
    result = assess_action(operation, service, state, dependencies, alerts_data, metric)
    created_at = now()
    with db() as connection:
        connection.execute("INSERT INTO risk_assessments(actor_id,score,band,factors_json,policy_json,created_at) VALUES (?,?,?,?,?,?)", (user["id"], result["score"], result["band"], json.dumps(result["factors"]), json.dumps(result["policy"]), created_at))
    return {"assessed_at": created_at, **result}


def refresh_recommendations() -> list[dict[str, Any]]:
    history = fetch_metric_history(1)
    metric = history[-1] if history else None
    forecasts_data = forecast_resources(fetch_metric_history(500)) if history else []
    with db() as connection:
        anomalies_data = [dict(row) for row in connection.execute("SELECT * FROM anomaly_findings WHERE status='open' ORDER BY created_at DESC LIMIT 100")]
        service_time = connection.execute("SELECT MAX(checked_at) AS timestamp FROM services").fetchone()["timestamp"]
        service_data = [dict(row) for row in connection.execute("SELECT service_name AS name,active,status FROM services WHERE checked_at=?", (service_time,))] if service_time else []
        process_time = connection.execute("SELECT MAX(timestamp) AS timestamp FROM processes").fetchone()["timestamp"]
        process_data = [dict(row) for row in connection.execute("SELECT pid,process_name AS name,cpu_usage,memory_usage FROM processes WHERE timestamp=? ORDER BY cpu_usage DESC LIMIT 100", (process_time,))] if process_time else []
        dependency_data = [dict(row) for row in connection.execute("SELECT source_service,target_service,relationship,source FROM service_dependencies")]
        alert_data = [dict(row) for row in connection.execute("SELECT id,severity,status,source,alert_type FROM alerts WHERE status='open' UNION ALL SELECT id,severity,status,component AS source,'incident' AS alert_type FROM incidents WHERE status IN ('open','investigating')")]
    recommendations_data = recommendations_from_state(metric, forecasts_data, anomalies_data, service_data, process_data)
    for item in recommendations_data:
        if item["category"] == "service_health":
            service_name = item["key"].split(":", 2)[1]
            service_state = next((service.get("active") for service in service_data if service.get("name") == service_name), None)
            risk = assess_action("restart", service_name, service_state, dependency_data, alert_data, metric)
            item["risk_score"] = risk["score"]
            item["risk_factors"] = {"band": risk["band"], "contributions": risk["contributions"], "factors": risk["factors"], "unknowns": risk["unknowns"]}
    updated = now()
    with db() as connection:
        for item in recommendations_data:
            connection.execute("INSERT INTO recommendations(recommendation_key,category,title,problem,evidence_json,proposed_action,expected_benefit,potential_impact,risk_score,risk_factors_json,requires_approval,verification,do_not_follow_when,status,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(recommendation_key) DO UPDATE SET category=excluded.category,title=excluded.title,problem=excluded.problem,evidence_json=excluded.evidence_json,proposed_action=excluded.proposed_action,expected_benefit=excluded.expected_benefit,potential_impact=excluded.potential_impact,risk_score=excluded.risk_score,risk_factors_json=excluded.risk_factors_json,updated_at=excluded.updated_at", (item["key"], item["category"], item["title"], item["problem"], json.dumps(item["evidence"]), item["proposed_action"], item["expected_benefit"], item["potential_impact"], item.get("risk_score", 0), json.dumps(item.get("risk_factors", {})), int(item["requires_approval"]), item["verification"], item["do_not_follow_when"], "active", updated, updated))
    return recommendations_data


@app.get("/api/recommendations")
def recommendations(status_filter: str | None = None, limit: int = Query(100, ge=1, le=500), offset: int = Query(0, ge=0), user: dict[str, Any] = Depends(current_user)) -> list[dict[str, Any]]:
    refresh_recommendations()
    with db() as connection:
        if status_filter:
            rows = connection.execute("SELECT * FROM recommendations WHERE status=? ORDER BY updated_at DESC LIMIT ? OFFSET ?", (status_filter, limit, offset)).fetchall()
        else:
            rows = connection.execute("SELECT * FROM recommendations ORDER BY updated_at DESC LIMIT ? OFFSET ?", (limit, offset)).fetchall()
    output = []
    for row in rows:
        item = dict(row)
        item["evidence"] = json.loads(item.pop("evidence_json"))
        item["risk_factors"] = json.loads(item.pop("risk_factors_json") or "{}")
        item["requires_approval"] = bool(item["requires_approval"])
        output.append(item)
    return output


@app.patch("/api/recommendations/{recommendation_id}")
def update_recommendation(recommendation_id: int, payload: RecommendationUpdateRequest, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    with db() as connection:
        result = connection.execute("UPDATE recommendations SET status=?,updated_at=? WHERE id=?", (payload.status, now(), recommendation_id))
        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="Recommendation not found")
        connection.execute("INSERT INTO audit_logs(user_id,action,target,timestamp,result) VALUES (?,?,?,?,?)", (user["id"], f"{payload.status}_recommendation", str(recommendation_id), now(), "success"))
        row = connection.execute("SELECT * FROM recommendations WHERE id=?", (recommendation_id,)).fetchone()
    return dict(row)


@app.post("/api/actions")
def create_action(payload: ActionRequest, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    if payload.action_type not in {"start", "stop", "restart"} or payload.target not in ALLOWED_SERVICES:
        raise HTTPException(status_code=400, detail="Only allowlisted start, stop, and restart requests are supported")
    if not re.fullmatch(r"[A-Za-z0-9_.@:-]+", payload.target):
        raise HTTPException(status_code=422, detail="Invalid service target")
    if payload.incident_id:
        with db() as connection:
            incident = connection.execute("SELECT id FROM incidents WHERE id=?", (payload.incident_id,)).fetchone()
        if not incident:
            raise HTTPException(status_code=404, detail="Linked incident not found")
    service_state, dependencies, active_alerts, metric = _action_context(payload.target, payload.action_type)
    risk = assess_action(payload.action_type, payload.target, service_state, dependencies, active_alerts, metric)
    impact = build_impact_report(payload.action_type, payload.target, risk, "systemd evidence available" if service_state else "systemd state unavailable")
    state = "REJECTED" if risk["policy"]["decision"] == "prohibited" else "PENDING_APPROVAL"
    timestamp = now()
    expires_at = (datetime.now(timezone.utc) + timedelta(minutes=30)).isoformat()
    fingerprint = action_fingerprint(payload.action_type, payload.target)
    with db() as connection:
        cursor = connection.execute(
            "INSERT INTO actions(user_id,action_type,target,requested_at,executed_at,status,result,state,impact_json,risk_json,requested_by,expires_at,before_state,fingerprint,incident_id) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (user["id"], payload.action_type, payload.target, timestamp, None, state.lower(), payload.reason, state, json.dumps(impact), json.dumps(risk), user["id"], expires_at, service_state, fingerprint, payload.incident_id),
        )
        action_id = cursor.lastrowid
        connection.execute("INSERT INTO impact_assessments(action_id,incident_id,actor_id,operation,target,report_json,created_at) VALUES (?,?,?,?,?,?,?)", (action_id, payload.incident_id, user["id"], payload.action_type, payload.target, json.dumps(impact), timestamp))
        connection.execute("INSERT INTO risk_assessments(action_id,incident_id,actor_id,score,band,factors_json,policy_json,created_at) VALUES (?,?,?,?,?,?,?,?)", (action_id, payload.incident_id, user["id"], risk["score"], risk["band"], json.dumps(risk["factors"]), json.dumps(risk["policy"]), timestamp))
        if payload.incident_id:
            connection.execute("INSERT OR IGNORE INTO incident_actions(incident_id,action_id) VALUES (?,?)", (payload.incident_id, action_id))
        connection.execute("INSERT INTO audit_logs(user_id,action,target,timestamp,result) VALUES (?,?,?,?,?)", (user["id"], "request_service_action", payload.target, timestamp, f"action_id={action_id}; operation={payload.action_type}; state={state}"))
        row = connection.execute("SELECT * FROM actions WHERE id=?", (action_id,)).fetchone()
    return _serialize_action(row)


@app.get("/api/actions")
def actions(limit: int = Query(100, ge=1, le=500), offset: int = Query(0, ge=0), state: str | None = None, user: dict[str, Any] = Depends(current_user)) -> list[dict[str, Any]]:
    with db() as connection:
        if user["role"] == "administrator":
            if state:
                rows = connection.execute("SELECT * FROM actions WHERE state=? ORDER BY id DESC LIMIT ? OFFSET ?", (state, limit, offset)).fetchall()
            else:
                rows = connection.execute("SELECT * FROM actions ORDER BY id DESC LIMIT ? OFFSET ?", (limit, offset)).fetchall()
        elif state:
            rows = connection.execute("SELECT * FROM actions WHERE requested_by=? AND state=? ORDER BY id DESC LIMIT ? OFFSET ?", (user["id"], state, limit, offset)).fetchall()
        else:
            rows = connection.execute("SELECT * FROM actions WHERE requested_by=? ORDER BY id DESC LIMIT ? OFFSET ?", (user["id"], limit, offset)).fetchall()
    return [_serialize_action(row) for row in rows]


def _serialize_action(row: sqlite3.Row) -> dict[str, Any]:
    result = dict(row)
    for raw, target in (("impact_json", "impact"), ("risk_json", "risk")):
        result[target] = json.loads(result.pop(raw) or "{}")
    result["approvals"] = []
    with db() as connection:
        result["approvals"] = [dict(approval) for approval in connection.execute("SELECT approvals.id,users.username AS approver,approvals.decision,approvals.reason,approvals.approved_at,approvals.expires_at FROM approvals JOIN users ON users.id=approvals.approver_id WHERE action_id=? ORDER BY approvals.id", (result["id"],))]
    return result


@app.get("/api/actions/{action_id}")
def action_detail(action_id: int, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    with db() as connection:
        row = connection.execute("SELECT * FROM actions WHERE id=?", (action_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Action request not found")
    if user["role"] != "administrator" and row["requested_by"] != user["id"]:
        raise HTTPException(status_code=403, detail="You can only inspect your own action requests")
    return _serialize_action(row)


@app.post("/api/actions/{action_id}/decision")
def decide_action(action_id: int, payload: ActionDecisionRequest, user: dict[str, Any] = Depends(administrator)) -> dict[str, Any]:
    with db() as connection:
        row = connection.execute("SELECT * FROM actions WHERE id=?", (action_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Action request not found")
        if row["state"] != "PENDING_APPROVAL":
            raise HTTPException(status_code=409, detail=f"Action is {row['state'].lower()} and cannot be decided")
        if datetime.fromisoformat(row["expires_at"]) <= datetime.now(timezone.utc):
            connection.execute("UPDATE actions SET state='EXPIRED',status='expired',result='Approval window expired' WHERE id=?", (action_id,))
            connection.execute("INSERT INTO audit_logs(user_id,action,target,timestamp,result) VALUES (?,?,?,?,?)", (user["id"], "expire_action", str(action_id), now(), "expired before approval"))
            connection.commit()
            raise HTTPException(status_code=409, detail="Action request has expired")
        risk = json.loads(row["risk_json"] or "{}")
        if payload.decision == "approve" and risk.get("requires_second_approver") and user["id"] == row["requested_by"]:
            raise HTTPException(status_code=409, detail="A different administrator must approve this high-risk request")
        if payload.decision == "approve" and risk.get("policy", {}).get("decision") == "prohibited":
            raise HTTPException(status_code=403, detail="Policy prohibits this operation regardless of approval")
        state = "APPROVED" if payload.decision == "approve" else "REJECTED"
        connection.execute("INSERT INTO approvals(action_id,approver_id,decision,reason,approved_at,expires_at) VALUES (?,?,?,?,?,?)", (action_id, user["id"], payload.decision, payload.reason, now(), row["expires_at"]))
        connection.execute("UPDATE actions SET state=?,status=?,approved_by=?,result=? WHERE id=?", (state, state.lower(), user["id"], payload.reason, action_id))
        connection.execute("INSERT INTO audit_logs(user_id,action,target,timestamp,result) VALUES (?,?,?,?,?)", (user["id"], payload.decision + "_action", str(action_id), now(), payload.reason))
        updated = connection.execute("SELECT * FROM actions WHERE id=?", (action_id,)).fetchone()
    return _serialize_action(updated)


@app.post("/api/actions/{action_id}/execute")
def execute_action(action_id: int, user: dict[str, Any] = Depends(administrator)) -> dict[str, Any]:
    with db() as connection:
        row = connection.execute("SELECT * FROM actions WHERE id=?", (action_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Action request not found")
    if row["state"] != "APPROVED":
        raise HTTPException(status_code=409, detail="Only approved requests can be executed")
    if datetime.fromisoformat(row["expires_at"]) <= datetime.now(timezone.utc):
        with db() as connection:
            connection.execute("UPDATE actions SET state='EXPIRED',status='expired',result='Approval window expired' WHERE id=?", (action_id,))
            connection.execute("INSERT INTO audit_logs(user_id,action,target,timestamp,result) VALUES (?,?,?,?,?)", (user["id"], "expire_approved_action", str(action_id), now(), "expired before execution"))
        raise HTTPException(status_code=409, detail="Approved operation has expired")
    operation, target = row["action_type"], row["target"]
    if target not in ALLOWED_SERVICES or operation not in {"start", "stop", "restart"} or row["fingerprint"] != action_fingerprint(operation, target):
        with db() as connection:
            connection.execute("UPDATE actions SET state='REJECTED',status='rejected',result='Operation fingerprint or allowlist validation failed' WHERE id=?", (action_id,))
            connection.execute("INSERT INTO audit_logs(user_id,action,target,timestamp,result) VALUES (?,?,?,?,?)", (user["id"], "reject_action_revalidation", str(action_id), now(), "fingerprint or allowlist validation failed"))
        raise HTTPException(status_code=409, detail="Approved operation no longer passes policy validation")
    if os.name != "posix" or not shutil.which("systemctl"):
        with db() as connection:
            connection.execute("UPDATE actions SET state='FAILED',status='failed',executed_at=?,result='systemd unavailable on this host' WHERE id=?", (now(), action_id))
            connection.execute("INSERT INTO audit_logs(user_id,action,target,timestamp,result) VALUES (?,?,?,?,?)", (user["id"], "execute_action", target, now(), "failed: systemd unavailable"))
        with db() as connection:
            failed = connection.execute("SELECT * FROM actions WHERE id=?", (action_id,)).fetchone()
        return _serialize_action(failed)
    current_state, dependencies, active_alerts, metric = _action_context(target, operation)
    risk = assess_action(operation, target, current_state, dependencies, active_alerts, metric)
    impact = build_impact_report(operation, target, risk, "systemd evidence available" if current_state else "systemd state unavailable")
    with db() as connection:
        connection.execute("INSERT INTO impact_assessments(action_id,incident_id,actor_id,operation,target,report_json,created_at) VALUES (?,?,?,?,?,?,?)", (action_id, row["incident_id"], user["id"], operation, target, json.dumps(impact), now()))
        connection.execute("INSERT INTO risk_assessments(action_id,incident_id,actor_id,score,band,factors_json,policy_json,created_at) VALUES (?,?,?,?,?,?,?,?)", (action_id, row["incident_id"], user["id"], risk["score"], risk["band"], json.dumps(risk["factors"]), json.dumps(risk["policy"]), now()))
    if current_state != row["before_state"] or risk["policy"]["decision"] == "prohibited":
        reason = "System state changed after approval; request a new assessment." if current_state != row["before_state"] else "Current policy prohibits this action."
        with db() as connection:
            connection.execute("UPDATE actions SET state='REJECTED',status='rejected',result=? WHERE id=?", (reason, action_id))
            connection.execute("INSERT INTO audit_logs(user_id,action,target,timestamp,result) VALUES (?,?,?,?,?)", (user["id"], "revalidation_reject", str(action_id), now(), reason))
        with db() as connection:
            rejected = connection.execute("SELECT * FROM actions WHERE id=?", (action_id,)).fetchone()
        return _serialize_action(rejected)
    if risk["requires_second_approver"] and row["approved_by"] == row["requested_by"]:
        with db() as connection:
            connection.execute("UPDATE actions SET state='PENDING_APPROVAL',status='pending_approval',approved_by=NULL,risk_json=?,result='Risk increased; independent approval required' WHERE id=?", (json.dumps(risk), action_id))
            connection.execute("INSERT INTO audit_logs(user_id,action,target,timestamp,result) VALUES (?,?,?,?,?)", (user["id"], "require_independent_reapproval", str(action_id), now(), "risk increased before execution"))
        raise HTTPException(status_code=409, detail="Risk increased; a different administrator must approve this request")
    with db() as connection:
        connection.execute("UPDATE actions SET state='EXECUTING',status='executing',risk_json=? WHERE id=?", (json.dumps(risk), action_id))
    return_code, _ = run_service_operation(target, operation)
    verified = linux_command(["systemctl", "is-active", f"{target}.service"]).strip() or "unknown"
    expected = "inactive" if operation == "stop" else "active"
    succeeded = return_code == 0 and verified == expected
    state = "VERIFIED" if succeeded else "FAILED"
    result = f"return_code={return_code}; verified_state={verified}; expected_state={expected}"
    with db() as connection:
        connection.execute("UPDATE actions SET state=?,status=?,executed_at=?,result=?,risk_json=? WHERE id=?", (state, state.lower(), now(), result, json.dumps(risk), action_id))
        connection.execute("INSERT INTO audit_logs(user_id,action,target,timestamp,result) VALUES (?,?,?,?,?)", (user["id"], "execute_action", target, now(), result))
        if row["incident_id"] and succeeded:
            connection.execute("UPDATE incidents SET status='investigating',updated_at=? WHERE id=? AND status='open'", (now(), row["incident_id"]))
        finished = connection.execute("SELECT * FROM actions WHERE id=?", (action_id,)).fetchone()
    return _serialize_action(finished)


@app.post("/api/actions/{action_id}/cancel")
def cancel_action(action_id: int, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    with db() as connection:
        row = connection.execute("SELECT * FROM actions WHERE id=?", (action_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Action request not found")
        if user["role"] != "administrator" and row["requested_by"] != user["id"]:
            raise HTTPException(status_code=403, detail="You can only cancel your own action requests")
        if row["state"] not in {"PENDING_APPROVAL", "APPROVED"}:
            raise HTTPException(status_code=409, detail=f"Action is {row['state'].lower()} and cannot be cancelled")
        connection.execute("UPDATE actions SET state='CANCELLED',status='cancelled',result='Cancelled by user' WHERE id=?", (action_id,))
        connection.execute("INSERT INTO audit_logs(user_id,action,target,timestamp,result) VALUES (?,?,?,?,?)", (user["id"], "cancel_action", str(action_id), now(), "success"))
        cancelled = connection.execute("SELECT * FROM actions WHERE id=?", (action_id,)).fetchone()
    return _serialize_action(cancelled)


@app.get("/api/audit")
def audit(user: dict[str, Any] = Depends(administrator)) -> list[dict[str, Any]]:
    with db() as connection:
        return [dict(row) for row in connection.execute("SELECT audit_logs.*, users.username FROM audit_logs JOIN users ON users.id=audit_logs.user_id ORDER BY audit_logs.id DESC LIMIT 200")]


@app.get("/api/incidents")
def incidents(status_filter: str | None = None, limit: int = Query(200, ge=1, le=500), offset: int = Query(0, ge=0), user: dict[str, Any] = Depends(current_user)) -> list[dict[str, Any]]:
    with db() as connection:
        if status_filter:
            rows = connection.execute("SELECT incidents.*, users.username AS assignee FROM incidents LEFT JOIN users ON users.id=incidents.assigned_to WHERE incidents.status=? ORDER BY incidents.updated_at DESC LIMIT ? OFFSET ?", (status_filter, limit, offset)).fetchall()
        else:
            rows = connection.execute("SELECT incidents.*, users.username AS assignee FROM incidents LEFT JOIN users ON users.id=incidents.assigned_to ORDER BY incidents.updated_at DESC LIMIT ? OFFSET ?", (limit, offset)).fetchall()
    return [dict(row) for row in rows]


@app.get("/api/incidents/{incident_id}")
def incident_detail(incident_id: int, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    with db() as connection:
        incident = connection.execute("SELECT incidents.*,users.username AS assignee FROM incidents LEFT JOIN users ON users.id=incidents.assigned_to WHERE incidents.id=?", (incident_id,)).fetchone()
        if not incident:
            raise HTTPException(status_code=404, detail="Incident not found")
        alert = connection.execute("SELECT * FROM alerts WHERE id=?", (incident["linked_alert_id"],)).fetchone() if incident["linked_alert_id"] else None
        actions = [dict(row) for row in connection.execute("SELECT actions.* FROM actions JOIN incident_actions ON incident_actions.action_id=actions.id WHERE incident_actions.incident_id=? ORDER BY actions.id DESC", (incident_id,))]
        root_causes = [dict(row) for row in connection.execute("SELECT * FROM root_cause_findings WHERE incident_id=? OR component=? ORDER BY created_at DESC LIMIT 50", (incident_id, incident["component"]))]
        anomaly_rows = [dict(row) for row in connection.execute("SELECT * FROM anomaly_findings WHERE component=? ORDER BY created_at DESC LIMIT 50", (incident["component"],))]
        predictions = [dict(row) for row in connection.execute("SELECT * FROM predictions ORDER BY created_at DESC LIMIT 50")]
        audits = [dict(row) for row in connection.execute("SELECT audit_logs.*,users.username FROM audit_logs JOIN users ON users.id=audit_logs.user_id WHERE audit_logs.target=? OR audit_logs.target=? ORDER BY audit_logs.id DESC LIMIT 100", (incident["component"], str(incident_id))).fetchall()]
        risk = [dict(row) for row in connection.execute("SELECT * FROM risk_assessments WHERE incident_id=? ORDER BY created_at DESC", (incident_id,))]
        impact = [dict(row) for row in connection.execute("SELECT * FROM impact_assessments WHERE incident_id=? ORDER BY created_at DESC", (incident_id,))]
    serialized_actions = []
    for row in actions:
        row["impact"] = json.loads(row.pop("impact_json") or "{}")
        row["risk"] = json.loads(row.pop("risk_json") or "{}")
        serialized_actions.append(row)
    incident_alert = dict(alert) if alert else None
    related_metrics = {"cpu_threshold": "cpu_usage", "memory_threshold": "memory_usage", "disk_threshold": "disk_usage"}
    metric_key = related_metrics.get(incident_alert["alert_type"]) if incident_alert else None
    related_prediction = [row for row in predictions if row["metric"] == metric_key] if metric_key else []
    if incident_alert and incident_alert["alert_type"] == "statistical_anomaly":
        related_prediction = [row for row in predictions if row["metric"] in {item["metric"] for item in anomaly_rows}]
    for finding in root_causes:
        for raw, key in (("evidence_json", "evidence"), ("alternatives_json", "alternatives"), ("diagnostics_json", "diagnostics")):
            finding[key] = json.loads(finding.pop(raw) or "[]")
    return {"incident": dict(incident), "alert": incident_alert, "actions": serialized_actions, "root_cause_findings": root_causes, "anomalies": anomaly_rows, "predictions": related_prediction, "risk_assessments": risk, "impact_assessments": impact, "audit_events": audits}


@app.patch("/api/incidents/{incident_id}")
def update_incident(incident_id: int, payload: IncidentUpdateRequest, user: dict[str, Any] = Depends(administrator)) -> dict[str, Any]:
    if payload.assigned_to:
        with db() as connection:
            if not connection.execute("SELECT 1 FROM users WHERE id=?", (payload.assigned_to,)).fetchone():
                raise HTTPException(status_code=404, detail="Assignee not found")
    updated_at = now()
    resolved_at = updated_at if payload.status in {"resolved", "closed"} else None
    with db() as connection:
        result = connection.execute("UPDATE incidents SET status=?,resolution_notes=COALESCE(?,resolution_notes),assigned_to=COALESCE(?,assigned_to),resolved_at=?,updated_at=? WHERE id=?", (payload.status, payload.resolution_notes, payload.assigned_to, resolved_at, updated_at, incident_id))
        if not result.rowcount:
            raise HTTPException(status_code=404, detail="Incident not found")
        connection.execute("INSERT INTO audit_logs(user_id,action,target,timestamp,result) VALUES (?,?,?,?,?)", (user["id"], f"{payload.status}_incident", str(incident_id), updated_at, payload.resolution_notes or "status updated"))
        row = connection.execute("SELECT incidents.*,users.username AS assignee FROM incidents LEFT JOIN users ON users.id=incidents.assigned_to WHERE incidents.id=?", (incident_id,)).fetchone()
    return dict(row)


@app.get("/api/config")
def get_config(user: dict[str, Any] = Depends(administrator)) -> dict[str, Any]:
    return {**effective_thresholds(), "collector_interval_seconds": COLLECTOR_INTERVAL_SECONDS, "retention_days": RETENTION_DAYS}


@app.put("/api/config")
def update_config(payload: ConfigUpdateRequest, user: dict[str, Any] = Depends(administrator)) -> dict[str, Any]:
    updated_at = now()
    values = payload.model_dump()
    with db() as connection:
        for key, value in values.items():
            connection.execute("INSERT INTO app_config(key,value_json,updated_at,updated_by) VALUES (?,?,?,?) ON CONFLICT(key) DO UPDATE SET value_json=excluded.value_json,updated_at=excluded.updated_at,updated_by=excluded.updated_by", (key, json.dumps(value), updated_at, user["id"]))
        connection.execute("INSERT INTO audit_logs(user_id,action,target,timestamp,result) VALUES (?,?,?,?,?)", (user["id"], "update_alert_thresholds", "app_config", updated_at, json.dumps(values)))
    return get_config(user)


@app.get("/api/forecasts")
def live_forecasts(horizon_hours: float = Query(1, gt=0, le=24), user: dict[str, Any] = Depends(current_user)) -> list[dict[str, Any]]:
    return forecast_resources(fetch_metric_history(500), horizon_hours)
