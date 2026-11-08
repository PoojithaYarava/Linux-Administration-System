# Ubuntu deployment

This deployment serves the built React site through Nginx, runs FastAPI as a systemd service on the Ubuntu host, and runs PostgreSQL in Docker Compose. Keeping the API on the host allows it to inspect that host's systemd units and journal.

## 1. Prepare the host

Use an Ubuntu server with a public IP. Point your domain's DNS record at that address. Allow SSH, HTTP, and HTTPS through the cloud firewall and host firewall. Install Git, Nginx, Docker Compose, Python 3.11 or newer, and Node.js 22.12 or newer (required by the pinned Vite 8 dependency).

```bash
sudo apt update
sudo apt install -y git nginx docker.io docker-compose-v2 python3 python3-venv python3-pip
```

Install a compatible Node.js release using the official Node.js instructions or your approved host package source, then confirm `node --version` is at least `v22.12.0`.

## 2. Check out the project and configure secrets

Create a dedicated, unprivileged service account, then clone the repository under `/opt`:

```bash
sudo useradd --system --user-group --no-create-home --shell /usr/sbin/nologin linuxadmin
sudo install -d -o "$USER" -g "$USER" -m 0755 /opt/linux-admin-platform
git clone https://github.com/PoojithaYarava/Linux-Administration-System.git /opt/linux-admin-platform
cd /opt/linux-admin-platform
cp .env.example .env
nano .env
```

Set a private PostgreSQL password and a different administrator password of at least 12 characters. Make the password in `DATABASE_URL` match `POSTGRES_PASSWORD`; URL-encode reserved characters in the URL password. Set `CORS_ORIGINS` to the site's origin, for example `https://admin.example.com`. Use `ALLOWED_SERVICES=` to disable service changes until a separate, restricted privilege policy has been designed and reviewed. Do not run the API as root to enable service control.

Restrict the secret file so only the service account can read it:

```bash
sudo chown root:linuxadmin .env
sudo chmod 640 .env
```

## 3. Start PostgreSQL and install application dependencies

The Compose file publishes PostgreSQL only on `127.0.0.1:5432` and stores its data in a named volume.

```bash
sudo docker compose up -d postgres
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r backend/requirements.txt
cd frontend
printf 'VITE_API_URL=/api\n' > .env.production
npm ci
npm run build
cd ..
```

The API applies the configured Alembic migrations during startup. Ensure the source, virtual environment, and `frontend/dist` are readable by `linuxadmin` and Nginx. Keep the `.env` file restricted as above.

## 4. Install and start the API service

The supplied unit binds Uvicorn to localhost and runs without development reload. Add the Ubuntu journal group so the service can read permitted journal records:

```bash
sudo usermod -aG systemd-journal linuxadmin
sudo install -m 0644 deploy/systemd/linux-admin-api.service /etc/systemd/system/linux-admin-api.service
sudo systemctl daemon-reload
sudo systemctl enable --now linux-admin-api
sudo systemctl status linux-admin-api
```

View API logs with `sudo journalctl -u linux-admin-api -f`. The service user is intentionally unprivileged. Inventory and journal access depend on host permissions; systemctl start/stop/restart actions require a separately designed, narrow authorization mechanism and are not enabled by these deployment files.

## 5. Configure Nginx

Edit `deploy/nginx/linux-admin.conf` and replace `admin.example.com` with your domain. Install and enable it:

```bash
sudo install -m 0644 deploy/nginx/linux-admin.conf /etc/nginx/sites-available/linux-admin
sudo ln -s /etc/nginx/sites-available/linux-admin /etc/nginx/sites-enabled/linux-admin
sudo nginx -t
sudo systemctl reload nginx
```

If the default Nginx site claims the same hostname, disable that site's symlink before reloading. Nginx serves `frontend/dist`, sends `/api/` requests to Uvicorn, and leaves PostgreSQL and Uvicorn unavailable on public interfaces.

## 6. Configure HTTPS and verify

After DNS resolves to the server and HTTP works, install Certbot using its current Ubuntu instructions and request a certificate for the domain. Confirm automatic renewal is enabled. Open the site at `https://admin.example.com`, sign in with the configured admin account, and check `https://admin.example.com/api/health`.

Useful checks:

```bash
sudo docker compose ps
sudo systemctl status linux-admin-api nginx
curl -fsS http://127.0.0.1:8000/api/health
sudo journalctl -u linux-admin-api -n 100 --no-pager
```

Back up PostgreSQL regularly and test restoring a backup. Do not publish `.env`, expose port 5432 or 8000, or leave the site on HTTP for real credentials.

## Updating a deployment

From the checkout, pull the desired commit, rebuild the frontend, then restart the API:

```bash
cd /opt/linux-admin-platform
git pull --ff-only
cd frontend && npm ci && npm run build
sudo systemctl restart linux-admin-api
```

Review database migrations and back up PostgreSQL before applying application updates.
