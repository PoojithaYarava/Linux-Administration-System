# Ubuntu deployment

The API must run natively on the Ubuntu host it monitors. Docker Compose runs PostgreSQL locally; keeping the API outside a container lets it use host psutil, systemd and journal interfaces without mounting privileged host sockets into a container. The commands below are documented for Ubuntu and have not been executed in this Windows workspace.

## Prerequisites and configuration

Install Python 3.11+, Node.js supported by the pinned Vite version, Docker Engine with the Compose plugin, PostgreSQL client utilities and a reverse proxy with TLS. Install the repository under `/opt/linux-admin-platform` and protect its environment file:

```bash
sudo useradd --system --home /opt/linux-admin-platform --shell /usr/sbin/nologin lap
sudo install -d -o lap -g lap /opt/linux-admin-platform /var/lib/linux-admin-platform
cd /opt/linux-admin-platform
cp .env.example .env
sudo chown lap:lap .env
sudo chmod 600 .env
```

Set unique private `POSTGRES_PASSWORD` and `ADMIN_PASSWORD` values. Set `DATABASE_URL` to `postgresql+psycopg://lap:<URL-encoded-password>@127.0.0.1:5432/linux_admin_platform`; URL-encode reserved characters. Set the exact browser `CORS_ORIGINS`, service allowlist, thresholds, and `PROTECTED_SERVICES`. Keep `.env` out of Git.

Start the database and install the Python application:

```bash
docker compose up -d postgres
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r backend/requirements.txt
cd backend
python -m alembic upgrade head
python -m alembic current
```

The API applies pending migrations during startup as an additional safeguard. Start it natively with `python -m app` for a demonstration. For a production service, use the unit example below.

## PostgreSQL Compose service

`docker-compose.yml` runs PostgreSQL 16 with a persistent named volume, health check, and a loopback-only port binding. The API remains native to the host and connects through `DATABASE_URL`.

```bash
docker compose ps
docker compose logs postgres
```

## Native systemd service example

Create `/etc/systemd/system/linux-admin-platform.service` and adapt paths. Grant only named, allowlisted service operations needed by the deployment; do not give the web process an unrestricted root shell.

```ini
[Unit]
Description=Linux Admin Intelligence Platform API
After=network-online.target docker.service
Wants=network-online.target

[Service]
Type=simple
User=lap
Group=lap
WorkingDirectory=/opt/linux-admin-platform/backend
EnvironmentFile=/opt/linux-admin-platform/.env
Environment=PYTHONPATH=/opt/linux-admin-platform/backend
ExecStart=/opt/linux-admin-platform/.venv/bin/python -m app
Restart=on-failure
RestartSec=5
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/var/lib/linux-admin-platform

[Install]
WantedBy=multi-user.target
```

Apply and inspect it with `sudo systemctl daemon-reload`, `sudo systemctl enable --now linux-admin-platform`, `systemctl status linux-admin-platform`, and `journalctl -u linux-admin-platform`. Ensure PostgreSQL is ready before starting the API.

## Frontend and reverse proxy

Build with `cd frontend && npm ci && npm run build`. Serve `frontend/dist` with the trusted reverse proxy and route `/api/` to the native FastAPI process at `127.0.0.1:8000`. Terminate TLS at the proxy, restrict inbound access, and set `CORS_ORIGINS` to the exact frontend origin. Do not expose Vite's development server publicly.

## Backups and operations

Use a protected PostgreSQL credential and create consistent backups. For the Compose database, `docker compose exec -T postgres pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --format=custom > platform.dump`. Restore into a separate test database with `pg_restore` and verify application health and important records before relying on backups. Monitor database disk use, host free space, collector freshness and service health. `RETENTION_DAYS` prunes collected metric/process/service/log/prediction history. Service operations remain human-reviewed and are revalidated before execution.

## Verification checklist

- `GET /api/health` reports collector status `running` and `linux_integration: true`.
- Alembic reports the expected current revision and PostgreSQL accepts an authenticated API login.
- Metric timestamps advance and contain actual host measurements.
- Service inventory, dependency graph and journal views show the access granted to the native service account.
- A non-disruptive allowlisted operation follows request, independent approval when policy requires it, execution, state verification and audit recording.
- Protected service stop requests are rejected.
- A database backup restores into a separate PostgreSQL database and required history is present.

These host checks and their evidence require Ubuntu, Docker/PostgreSQL, systemd access and a disposable test service; they are not represented as completed in this Windows workspace.
