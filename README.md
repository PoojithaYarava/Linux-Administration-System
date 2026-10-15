# Linux Admin Intelligence Platform

A local web console for Linux host telemetry and controlled administration. The React dashboard talks to a FastAPI service that collects host metrics, process data, systemd inventory, journal entries, alerts, actions, and audit history. SQLite stores application data and login sessions.

## Capabilities

- Live CPU, memory, disk, network, uptime, and host details, with a rolling telemetry chart.
- Process inventory with CPU, memory, user, command, and state details.
- systemd service inventory and dependency graph; allowlisted operations are submitted as expiring approval requests and revalidated before execution.
- journal search and severity filtering.
- background telemetry collection with history and retention, multivariate anomaly detection, resource threshold forecasts, and evidence-ranked root-cause hypotheses.
- explainable risk and impact reports, reviewed recommendations, incident tracking, human approvals, role-based accounts, and audit history.
- persistent, expiring bearer sessions; password changes revoke all sessions.
- alert acknowledgement and an audit trail for administrative actions.
- Responsive React interface and a FastAPI health endpoint.

See the [operator manual](docs/user_manual.md) for workflows and the [final demo script](docs/final_demo_script.md) for a guided presentation. The [project report](docs/final_project_report.md) records methods, verification and limitations.

## Quick start

Use Python 3.11 or newer and Node.js supported by the pinned Vite version. From the repository root, create a local environment file and set a private administrator password before the first launch:

```powershell
Copy-Item .env.example .env
```

Edit `.env` and replace `ADMIN_PASSWORD` with a long private password. Do not commit `.env`.

In one terminal, install and run the API:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r backend/requirements.txt
Set-Location backend
python -m app
```

In a second terminal, run the web client:

```powershell
Set-Location frontend
npm ci
npm run dev
```

Open [http://localhost:5173](http://localhost:5173). Sign in using `ADMIN_USERNAME` and `ADMIN_PASSWORD` from `.env`.

On Ubuntu, replace the Windows virtual-environment activation command with:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r backend/requirements.txt
cd backend && python -m app
```

Run the frontend in another terminal with `cd frontend && npm ci && npm run dev`.

## Configuration

| Variable | Default | Purpose |
| --- | --- | --- |
| `DATABASE_PATH` | `backend/data/platform.db` | SQLite database location |
| `ADMIN_USERNAME` | `admin` | Initial administrator account, created when the database is empty |
| `ADMIN_PASSWORD` | `change-me-now` if unset | Initial password; configure a long private value before first launch |
| `SESSION_TTL_HOURS` | `12` | Login session lifetime |
| `ALLOWED_SERVICES` | `ssh,cron,systemd-journald` | Services the admin API may operate |
| `CPU_ALERT_THRESHOLD` | `85` | CPU alert threshold percent |
| `MEMORY_ALERT_THRESHOLD` | `85` | Memory alert threshold percent |
| `DISK_ALERT_THRESHOLD` | `90` | Disk alert threshold percent |
| `COLLECTOR_INTERVAL_SECONDS` | `15` | Background sampling interval (minimum 5 seconds) |
| `RETENTION_DAYS` | `30` | History retention period |
| `COLLECTOR_ENABLED` | `true` | Enable background host collection |
| `PROTECTED_SERVICES` | `ssh,systemd-journald` | Services whose stop operation is prohibited |
| `SERVICE_CRITICALITY` | `ssh:critical,cron:medium,systemd-journald:high` | Comma-separated service risk classifications |
| `CORS_ORIGINS` | `http://localhost:5173` | Comma-separated allowed browser origins |

The API reads the root `.env` file on startup and respects environment variables already supplied by the process. The administrator account is created only on an empty database; changing the environment password later does not reset an existing account. Use Administration → Change admin password to rotate it.

## Linux host integration

Run the backend on the Ubuntu/Linux host you want to monitor. systemd inventory, unit dependencies, journal access, and service actions require `systemctl`/`journalctl` and the operating-system permissions granted to the backend process. Use a dedicated least-privilege account and grant only the narrowly scoped systemd commands required by the configured allowlist. On Windows or a container without systemd, host telemetry still works but Linux service, dependency and journal features report that the integration is unavailable.

The existing SQLite storage choice is preserved. PostgreSQL and Alembic are not included in this delivery. Set `DATABASE_PATH` to persistent storage and arrange regular, consistent database backups before collecting production history. See the [delivery checklist](docs/REQUIREMENTS_CHECKLIST.md) for implementation evidence and host-dependent limitations.

## Production build

Build the static frontend with:

```bash
cd frontend
npm ci
npm run build
```

The output is written to `frontend/dist`. For deployment, serve those files from a web server that proxies `/api` to the FastAPI process, set a strong initial admin password, restrict `CORS_ORIGINS`, and protect the API behind HTTPS and an appropriate network boundary. The Vite development server is for local use only.

## API and project notes

See the [API reference](docs/API.md), [architecture](docs/architecture.md), [system design and diagrams](docs/system_design.md), [database schema](docs/database_schema.md), [ML methodology](docs/ml_methodology.md), [security model](docs/security.md), and [testing/evaluation](docs/testing_and_evaluation.md). The [Ubuntu deployment guide](docs/deployment.md), [implementation phases](docs/IMPLEMENTATION_PLAN.md), and [master prompt checklist](docs/REQUIREMENTS_CHECKLIST.md) state the implemented scope and remaining host-dependent work. FastAPI exposes interactive OpenAPI documentation at `/docs` while the backend is running. The unauthenticated health probe is `GET /api/health`.

## Troubleshooting

- **The dashboard says it cannot reach the API:** start the backend on port 8000 and confirm `http://localhost:8000/api/health` returns `status: ok`.
- **The browser shows 502:** Vite is running but cannot connect to the API. Start or restart the backend; the web app clears an invalid saved session and returns to sign-in after the backend recovers.
- **Login fails after changing `.env`:** `.env` only initializes an empty database. Use the password already saved in the database or reset it through the supported account recovery procedure for your deployment.
- **Services or logs are unavailable:** run the backend on Linux with systemd and journal permissions. This is expected on Windows.
- **Port already in use:** stop the process using 5173 or 8000, or change the corresponding Vite/API configuration.
