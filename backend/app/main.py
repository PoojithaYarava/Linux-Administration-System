from __future__ import annotations

import hashlib
import hmac
import json
import os
import platform
import secrets
import shutil
import sqlite3
import subprocess
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import psutil
from fastapi import Depends, FastAPI, HTTPException, Query, Request, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app.intelligence import detect_anomalies

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


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def db() -> sqlite3.Connection:
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


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
            "SELECT 1 FROM alerts WHERE alert_type=? AND source=? AND status='open' LIMIT 1",
            (alert_type, source),
        ).fetchone():
            return
        connection.execute("INSERT INTO alerts(timestamp,alert_type,severity,message,status,source) VALUES (?,?,?,?,?,?)", (now(), alert_type, severity, message, "open", source))


def collect_metrics() -> dict[str, Any]:
    disk_path = Path("/") if os.name != "nt" else Path.cwd().anchor
    network = psutil.net_io_counters()
    load = os.getloadavg()[0] if hasattr(os, "getloadavg") else psutil.cpu_percent(interval=None) / 100
    metric = {"timestamp": now(), "cpu_usage": psutil.cpu_percent(interval=0.15), "memory_usage": psutil.virtual_memory().percent, "disk_usage": psutil.disk_usage(disk_path).percent, "network_received": network.bytes_recv, "network_sent": network.bytes_sent, "load_average": round(load, 2)}
    with db() as connection:
        connection.execute("INSERT INTO system_metrics(timestamp,cpu_usage,memory_usage,disk_usage,network_received,network_sent,load_average) VALUES (?,?,?,?,?,?,?)", tuple(metric.values()))
    if metric["cpu_usage"] > float(os.getenv("CPU_ALERT_THRESHOLD", "85")):
        record_alert("cpu_threshold", "high", f"CPU utilization reached {metric['cpu_usage']:.1f}%, above the configured threshold.", "system")
    if metric["memory_usage"] > float(os.getenv("MEMORY_ALERT_THRESHOLD", "85")):
        record_alert("memory_threshold", "high", f"Memory utilization reached {metric['memory_usage']:.1f}%, above the configured threshold.", "system")
    if metric["disk_usage"] > float(os.getenv("DISK_ALERT_THRESHOLD", "90")):
        record_alert("disk_threshold", "medium", f"Disk utilization reached {metric['disk_usage']:.1f}%, above the configured threshold.", "filesystem")
    return metric


def process_row(process: psutil.Process) -> dict[str, Any] | None:
    try:
        with process.oneshot():
            return {"pid": process.pid, "name": process.name(), "cpu_usage": process.cpu_percent(None), "memory_usage": process.memory_percent(), "status": process.status(), "user": process.username(), "start_time": datetime.fromtimestamp(process.create_time(), timezone.utc).isoformat(), "command": " ".join(process.cmdline())[:500]}
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


@app.on_event("startup")
def startup() -> None:
    init_db()
    with db() as connection:
        connection.execute("DELETE FROM sessions WHERE expires_at <= ?", (now(),))


@app.get("/api/health")
def health() -> dict[str, Any]:
    return {"status": "ok", "platform": platform.platform(), "linux_integration": os.name == "posix" and shutil.which("systemctl") is not None}


@app.post("/api/auth/login")
def login(payload: LoginRequest) -> dict[str, Any]:
    with db() as connection:
        row = connection.execute("SELECT id,username,password_hash,role FROM users WHERE username=?", (payload.username,)).fetchone()
    if not row or not verify_password(payload.password, row["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid username or password")
    token = secrets.token_urlsafe(32)
    user = {"id": row["id"], "username": row["username"], "role": row["role"]}
    created_at = datetime.now(timezone.utc)
    expires_at = created_at + timedelta(hours=SESSION_TTL_HOURS)
    with db() as connection:
        connection.execute(
            "INSERT INTO sessions(token_hash,user_id,created_at,expires_at) VALUES (?,?,?,?)",
            (hash_token(token), user["id"], created_at.isoformat(), expires_at.isoformat()),
        )
    return {"token": token, "user": user}


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
    latest = collect_metrics()
    with db() as connection:
        rows = connection.execute("SELECT * FROM system_metrics ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    return {"latest": latest, "history": [dict(row) for row in reversed(rows)]}


@app.get("/api/system/health")
def system_health(user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    metric = collect_metrics()
    return {"status": "degraded" if metric["cpu_usage"] > 85 or metric["memory_usage"] > 85 else "healthy", "metric": metric}


@app.get("/api/processes")
def processes(user: dict[str, Any] = Depends(current_user)) -> list[dict[str, Any]]:
    rows = [row for process in psutil.process_iter() if (row := process_row(process))]
    with db() as connection:
        connection.executemany("INSERT INTO processes(timestamp,pid,process_name,cpu_usage,memory_usage,status) VALUES (?,?,?,?,?,?)", [(now(), row["pid"], row["name"], row["cpu_usage"], row["memory_usage"], row["status"]) for row in rows[:100]])
    return sorted(rows, key=lambda row: row["cpu_usage"], reverse=True)


@app.get("/api/processes/{pid}")
def process_detail(pid: int, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    try:
        row = process_row(psutil.Process(pid))
    except psutil.NoSuchProcess:
        row = None
    if not row:
        raise HTTPException(status_code=404, detail="Process not found or inaccessible")
    return row


@app.get("/api/services")
def services(user: dict[str, Any] = Depends(current_user)) -> list[dict[str, Any]]:
    output = linux_command(["systemctl", "list-units", "--type=service", "--all", "--no-legend", "--no-pager"])
    result = []
    for line in output.splitlines():
        parts = line.split(None, 4)
        if len(parts) >= 4:
            result.append({"name": parts[0].removesuffix(".service"), "load": parts[1], "active": parts[2], "status": parts[3], "description": parts[4] if len(parts) == 5 else "", "enabled": None})
    if not result and os.name != "posix":
        result.append({"name": "linux-only", "active": "unavailable", "status": "Windows host", "description": "Run this service on Ubuntu for systemd data", "enabled": False})
    with db() as connection:
        connection.executemany("INSERT INTO services(service_name,status,enabled,checked_at) VALUES (?,?,?,?)", [(item["name"], item["status"], int(bool(item.get("enabled"))), now()) for item in result[:100]])
    return result


@app.get("/api/services/{name}")
def service_detail(name: str, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    if name not in ALLOWED_SERVICES:
        raise HTTPException(status_code=403, detail="Service is not in the controlled allowlist")
    output = linux_command(["systemctl", "show", f"{name}.service", "--no-pager", "--property=Id,Description,ActiveState,SubState,UnitFileState"])
    if not output:
        raise HTTPException(status_code=503, detail="systemd is unavailable on this host")
    return dict(line.split("=", 1) for line in output.splitlines() if "=" in line)


@app.get("/api/logs")
def logs(limit: int = Query(100, ge=1, le=500), severity: str | None = None, service: str | None = None, search: str | None = None, user: dict[str, Any] = Depends(current_user)) -> list[dict[str, Any]]:
    args = ["journalctl", "-n", str(limit), "--no-pager", "-o", "json"]
    if service:
        args.extend(["-u", service])
    raw = linux_command(args)
    result = []
    for line in raw.splitlines():
        try:
            item = json.loads(line)
            message = item.get("MESSAGE", "")
            priority = {"0": "emergency", "1": "alert", "2": "critical", "3": "error", "4": "warning", "5": "notice", "6": "info", "7": "debug"}.get(str(item.get("PRIORITY", "6")), "info")
            row = {"timestamp": item.get("__REALTIME_TIMESTAMP", ""), "source": item.get("SYSLOG_IDENTIFIER", item.get("_SYSTEMD_UNIT", "system")), "severity": priority, "message": message}
            if (not severity or priority == severity) and (not search or search.lower() in message.lower()):
                result.append(row)
        except json.JSONDecodeError:
            continue
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


@app.get("/api/anomalies")
def anomalies(user: dict[str, Any] = Depends(current_user)) -> list[dict[str, Any]]:
    with db() as connection:
        rows = connection.execute("SELECT * FROM system_metrics ORDER BY id DESC LIMIT 100").fetchall()
    return detect_anomalies([dict(row) for row in reversed(rows)])


@app.post("/api/services/{name}/{operation}")
def service_action(name: str, operation: str, user: dict[str, Any] = Depends(administrator)) -> dict[str, Any]:
    if name not in ALLOWED_SERVICES or operation not in {"start", "stop", "restart"}:
        raise HTTPException(status_code=400, detail="Operation or service is not permitted")
    requested = now()
    return_code, result = run_service_operation(name, operation)
    verified = linux_command(["systemctl", "is-active", f"{name}.service"]).strip() or "unavailable"
    action_status = "success" if return_code == 0 and verified in {"active", "inactive", "failed"} else "failed"
    with db() as connection:
        cursor = connection.execute("INSERT INTO actions(user_id,action_type,target,requested_at,executed_at,status,result) VALUES (?,?,?,?,?,?,?)", (user["id"], operation, name, requested, now(), action_status, f"verified_state={verified}"))
        connection.execute("INSERT INTO audit_logs(user_id,action,target,timestamp,result) VALUES (?,?,?,?,?)", (user["id"], operation, name, now(), f"{action_status}; verified_state={verified}"))
    return {"action_id": cursor.lastrowid, "status": action_status, "service": name, "operation": operation, "verified_state": verified, "command_output": result[-500:]}


@app.post("/api/actions")
def create_action(payload: ActionRequest, user: dict[str, Any] = Depends(administrator)) -> dict[str, Any]:
    if payload.action_type not in {"start", "stop", "restart"} or payload.target not in ALLOWED_SERVICES:
        raise HTTPException(status_code=400, detail="Only allowlisted service actions are supported")
    return service_action(payload.target, payload.action_type, user)


@app.get("/api/actions")
def actions(user: dict[str, Any] = Depends(administrator)) -> list[dict[str, Any]]:
    with db() as connection:
        return [dict(row) for row in connection.execute("SELECT * FROM actions ORDER BY id DESC LIMIT 200")]


@app.get("/api/audit")
def audit(user: dict[str, Any] = Depends(administrator)) -> list[dict[str, Any]]:
    with db() as connection:
        return [dict(row) for row in connection.execute("SELECT audit_logs.*, users.username FROM audit_logs JOIN users ON users.id=audit_logs.user_id ORDER BY audit_logs.id DESC LIMIT 200")]
