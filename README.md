# Linux Admin Intelligence Platform

Linux Admin Intelligence Platform is a web console for administrators who need a clear view of host health and a traceable way to investigate operational issues. The React frontend uses a FastAPI backend. On a Linux host, the backend can collect system metrics, inspect processes and systemd units, read journal entries, and expose safety-checked administrative actions. PostgreSQL stores application data, sessions, and audit records.

## Live demo

- **Website:** [linux-administration-system.vercel.app](https://linux-administration-system.vercel.app)
- **API health:** [linux-admin-api.onrender.com/api/health](https://linux-admin-api.onrender.com/api/health)

Sign-in is required. Public registration is disabled because this is an administrator console. A reviewer account can be created by the project administrator; share its credentials privately and rotate them after the review. Never publish passwords or secret environment values in this repository.

The hosted demo reports on the host running its backend service. It does not monitor the visitor's computer. To demonstrate systemd services and journal data, run the backend on the Ubuntu/Linux machine being monitored. Windows supports general host telemetry, but Linux-only integrations are unavailable there.

## Screenshots

The gallery uses compact thumbnails in three columns. Select any image to open its full-size capture. The application screenshots show a Windows run; the Ubuntu/WSL group shows the Linux-specific integration. Screenshots show captured example states, and live data may differ.

### Application interface — Windows run

These screens show the application using Windows host telemetry. systemd services and journal features require a Linux backend and are unavailable in this run.

<table>
  <tr>
    <td align="center"><a href="artifacts/website-screenshots/00-login.png"><img src="artifacts/website-screenshots/00-login.png" width="280" alt="Sign-in screen"></a><br><sub>Sign-in</sub></td>
    <td align="center"><a href="artifacts/website-screenshots/01-dashboard.png"><img src="artifacts/website-screenshots/01-dashboard.png" width="280" alt="Dashboard overview"></a><br><sub>Dashboard</sub></td>
    <td align="center"><a href="artifacts/website-screenshots/02-dashboard-host-details.png"><img src="artifacts/website-screenshots/02-dashboard-host-details.png" width="280" alt="Dashboard host details"></a><br><sub>Host details</sub></td>
  </tr>
  <tr>
    <td align="center"><a href="artifacts/website-screenshots/03-processes.png"><img src="artifacts/website-screenshots/03-processes.png" width="280" alt="Process inventory"></a><br><sub>Processes</sub></td>
    <td align="center"><a href="artifacts/website-screenshots/03b-process-detail.png"><img src="artifacts/website-screenshots/03b-process-detail.png" width="280" alt="Process details"></a><br><sub>Process details</sub></td>
    <td align="center"><a href="artifacts/website-screenshots/04-services.png"><img src="artifacts/website-screenshots/04-services.png" width="280" alt="Services view"></a><br><sub>Services</sub></td>
  </tr>
  <tr>
    <td align="center"><a href="artifacts/website-screenshots/05-dependencies.png"><img src="artifacts/website-screenshots/05-dependencies.png" width="280" alt="Service dependency view"></a><br><sub>Dependencies</sub></td>
    <td align="center"><a href="artifacts/website-screenshots/06-forecasts-models.png"><img src="artifacts/website-screenshots/06-forecasts-models.png" width="280" alt="Forecasts and models"></a><br><sub>Forecasts and models</sub></td>
    <td align="center"><a href="artifacts/website-screenshots/07-root-cause.png"><img src="artifacts/website-screenshots/07-root-cause.png" width="280" alt="Root cause analysis"></a><br><sub>Root cause</sub></td>
  </tr>
  <tr>
    <td align="center"><a href="artifacts/website-screenshots/08-recommendations.png"><img src="artifacts/website-screenshots/08-recommendations.png" width="280" alt="Recommendations"></a><br><sub>Recommendations</sub></td>
    <td align="center"><a href="artifacts/website-screenshots/09-incidents.png"><img src="artifacts/website-screenshots/09-incidents.png" width="280" alt="Incident management"></a><br><sub>Incidents</sub></td>
    <td align="center"><a href="artifacts/website-screenshots/10-system-logs.png"><img src="artifacts/website-screenshots/10-system-logs.png" width="280" alt="System logs"></a><br><sub>System logs</sub></td>
  </tr>
  <tr>
    <td align="center"><a href="artifacts/website-screenshots/11-alerts-anomalies.png"><img src="artifacts/website-screenshots/11-alerts-anomalies.png" width="280" alt="Alerts and anomalies"></a><br><sub>Alerts and anomalies</sub></td>
    <td align="center"><a href="artifacts/website-screenshots/12-operations-admin.png"><img src="artifacts/website-screenshots/12-operations-admin.png" width="280" alt="Operations and administration"></a><br><sub>Operations and administration</sub></td>
    <td align="center"><a href="artifacts/website-screenshots/13-users.png"><img src="artifacts/website-screenshots/13-users.png" width="280" alt="User management"></a><br><sub>Users</sub></td>
  </tr>
  <tr>
    <td align="center"><a href="artifacts/website-screenshots/14-audit-history.png"><img src="artifacts/website-screenshots/14-audit-history.png" width="280" alt="Audit history"></a><br><sub>Audit history</sub></td>
    <td></td>
    <td></td>
  </tr>
</table>

### Ubuntu on WSL

These captures were taken with the backend running in Ubuntu on Windows Subsystem for Linux. They illustrate the Linux integration available in that environment; WSL may not expose every host service or journal feature in the same way as a dedicated Ubuntu server.

<table>
  <tr>
    <td align="center"><a href="artifacts/website-screenshots/linux-wsl/00-login.png"><img src="artifacts/website-screenshots/linux-wsl/00-login.png" width="280" alt="Sign-in screen during Ubuntu WSL run"></a><br><sub>Sign-in</sub></td>
    <td align="center"><a href="artifacts/website-screenshots/linux-wsl/dashboard.png"><img src="artifacts/website-screenshots/linux-wsl/dashboard.png" width="280" alt="Ubuntu WSL dashboard with redacted username"></a><br><sub>Linux host dashboard</sub></td>
    <td align="center"><a href="artifacts/website-screenshots/linux-wsl/02-services.png"><img src="artifacts/website-screenshots/linux-wsl/02-services.png" width="280" alt="Service inventory during Ubuntu WSL run"></a><br><sub>Services</sub></td>
  </tr>
  <tr>
    <td align="center"><a href="artifacts/website-screenshots/linux-wsl/03-dependencies.png"><img src="artifacts/website-screenshots/linux-wsl/03-dependencies.png" width="280" alt="Dependencies during Ubuntu WSL run"></a><br><sub>Dependencies</sub></td>
    <td align="center"><a href="artifacts/website-screenshots/linux-wsl/03-processes.png"><img src="artifacts/website-screenshots/linux-wsl/03-processes.png" width="280" alt="Processes during Ubuntu WSL run"></a><br><sub>Processes</sub></td>
    <td align="center"><a href="artifacts/website-screenshots/linux-wsl/04-system-logs.png"><img src="artifacts/website-screenshots/linux-wsl/04-system-logs.png" width="280" alt="System logs during Ubuntu WSL run"></a><br><sub>System logs</sub></td>
  </tr>
</table>

## What it provides

- CPU, memory, disk, network, uptime, and host details with historical resource charts.
- Process inventory, including process state, owner, CPU, memory, and command details where the host permits access.
- Linux systemd service inventory, dependency information, and journal search.
- Background telemetry collection, resource forecasts, anomaly signals, and evidence-ranked root-cause hypotheses.
- Recommendations, incident tracking, role-based user accounts, session expiry, and administrative audit history.
- Safety controls for service operations, including allowlists, protected services, expiring approvals, and action revalidation.

## Run locally

### Prerequisites

- Python 3.11 or newer
- Node.js and npm
- Docker Desktop or another Docker Compose installation for PostgreSQL
- Ubuntu/Linux if you need to demonstrate systemd and journal functionality

### 1. Configure the backend

From the project root, create a local environment file:

```powershell
Copy-Item .env.example .env
```

Edit `.env`. Set a private `POSTGRES_PASSWORD`, update the password in `DATABASE_URL` to match, and set a private `ADMIN_PASSWORD`. Do not commit `.env` or share the administrator password.

Start PostgreSQL:

```powershell
docker compose up -d postgres
```

Create and activate the Python environment, install backend packages, migrate the database, and start the API:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r backend/requirements.txt
Set-Location backend
python -m alembic upgrade head
python -m app
```

The API listens on `http://localhost:8000`. Open [http://localhost:8000/api/health](http://localhost:8000/api/health) to check it; interactive API docs are at [http://localhost:8000/docs](http://localhost:8000/docs).

### 2. Start the frontend

In a second terminal:

```powershell
Set-Location frontend
npm ci
npm run dev
```

Open [http://localhost:5173](http://localhost:5173) and sign in with the initial administrator credentials from `.env`. The initial administrator is created only when the database is empty; changing `.env` later does not replace a password already stored in the database.

### Ubuntu/Linux backend

Run the backend on the Ubuntu host whose services and journal you want to inspect. In the Ubuntu shell, from the project root:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r backend/requirements.txt
cd backend
python -m alembic upgrade head
python -m app
```

Run PostgreSQL and the frontend as described above. The backend process needs appropriate permission to read host metrics, systemd units, and journal entries. Follow the least-privilege guidance in [`deploy/README.md`](deploy/README.md) before enabling administrative actions.

## Deployment

The [`deploy/README.md`](deploy/README.md) guide covers the Ubuntu deployment files, Nginx, systemd, and the public Vercel + Render + Neon setup. Public cloud deployments monitor the backend container itself. To monitor a particular Linux host, deploy the backend on that host and configure HTTPS and network access carefully.

## Configuration

| Variable | Purpose |
| --- | --- |
| `DATABASE_URL` | PostgreSQL connection string; required for the standard setup |
| `DATABASE_PATH` | Optional legacy SQLite mode for an existing installation |
| `ADMIN_USERNAME` | Username for the initial administrator account |
| `ADMIN_PASSWORD` | Private password used only when initializing an empty database |
| `SESSION_TTL_HOURS` | Login session lifetime |
| `CORS_ORIGINS` | Comma-separated allowed browser origins |
| `COLLECTOR_ENABLED` | Enables or disables background telemetry collection |
| `COLLECTOR_INTERVAL_SECONDS` | Sampling interval for background collection |
| `RETENTION_DAYS` | Telemetry history retention period |
| `ALLOWED_SERVICES` | Allowlist of services eligible for administrative actions |
| `PROTECTED_SERVICES` | Services that cannot be stopped through the application |
| `CPU_ALERT_THRESHOLD` | CPU alert threshold percentage |
| `MEMORY_ALERT_THRESHOLD` | Memory alert threshold percentage |
| `DISK_ALERT_THRESHOLD` | Disk alert threshold percentage |

Additional settings and safe defaults are documented in [`.env.example`](.env.example). The backend reads that root configuration file at startup and respects environment variables supplied by the host.

## Project structure

```text
backend/       FastAPI application, database migrations, and API tests
frontend/      React application and Vite configuration
deploy/        Ubuntu, Nginx, and systemd deployment guidance/templates
ml/            Model evaluation notebook and notes
scripts/       Database migration and utility scripts
artifacts/     Screenshot gallery assets grouped by environment
```

## Security notes

- Keep `.env`, database credentials, API tokens, and account passwords out of Git.
- Do not publish the administrator password. Provide a limited reviewer account privately and rotate its password after review.
- Restrict the API to trusted clients, use HTTPS, set exact `CORS_ORIGINS`, and apply least-privilege host permissions.
- Review the allowlisted services and protected-service settings before enabling administrative actions.

## Troubleshooting

- **Frontend cannot reach the API:** check that the API is running on port `8000` and that `/api/health` responds.
- **A 502 appears in the frontend:** the frontend proxy cannot reach the backend. Start or restart the API and check its terminal output.
- **Sign-in fails after changing `.env`:** the configured password initializes an empty database only. Use the password stored for the existing account or follow the deployment's account recovery procedure.
- **Services or journal entries are unavailable:** run the backend on Linux with systemd/journal access. This is expected on Windows and on cloud containers that do not expose the host's systemd journal.
- **A port is already in use:** stop the process using port `5173` or `8000`, or update the corresponding local configuration.

## License

See [LICENSE](LICENSE).
