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

## Free public demonstration (Vercel + Render + Neon)

The repository also includes a Render Blueprint at [`../render.yaml`](../render.yaml) for the FastAPI API. The frontend remains a static Vite site on Vercel, and Neon provides PostgreSQL. This layout uses provider-managed HTTPS and keeps database credentials out of the frontend.

### Before you start

- Push the project to the GitHub repository you will connect to both providers.
- Create a free Neon project in Singapore (or the Render service's region). Copy its PostgreSQL connection string with SSL enabled (`sslmode=require`). The application converts provider `postgresql://` URLs to the installed Psycopg 3 driver. Never put this URL in GitHub or the frontend settings.
- Render's Free web service sleeps after 15 minutes without inbound requests and can take about a minute to wake. Neon Free currently has usage and storage limits; check the provider dashboard before relying on it for long-term storage. These are demonstration tiers, not production availability guarantees.

### Deploy the API

1. In Render, choose **New → Blueprint** and connect the GitHub repository. Render reads `render.yaml` from the repository root and creates the Python API service.
2. When Render asks for secret values, enter the Neon connection string as `DATABASE_URL`, a unique password of at least 12 characters as `ADMIN_PASSWORD`, and a different password of at least 12 characters as `DEMO_PASSWORD`. The demo user name is `demo`; the app creates it with the restricted `operator` role. Keep both passwords private until deployment is complete.
3. For `CORS_ORIGINS`, enter a temporary value such as `https://placeholder.invalid`. After deploying Vercel, replace this with the exact Vercel origin.
4. Wait for the Render deploy to finish. Copy the service's public URL, such as `https://linux-admin-api.onrender.com`. Verify that `<API-URL>/api/health` returns JSON with `status: ok` before continuing.

At startup the API runs the project's Alembic migration. It stores application data in Neon; Render's temporary filesystem is not used as the database. The Blueprint disables service operations, hides Swagger/OpenAPI, retains seven days of telemetry, and samples the hosted runtime every five minutes.

### Deploy the frontend

1. In Vercel, choose **Add New → Project** and import the same GitHub repository.
2. Set **Root Directory** to `frontend`. Use the Vite framework preset, install command `npm ci`, build command `npm run build`, and output directory `dist`.
3. Add this Production environment variable, replacing the example with the Render URL:

   ```text
   VITE_API_URL=https://linux-admin-api.onrender.com/api
   ```

4. Deploy and copy the Vercel Production URL, for example `https://your-project.vercel.app`.
5. Return to Render → API service → **Environment**. Set `CORS_ORIGINS` to that exact origin, with no trailing slash, then save and let Render redeploy.
6. In Vercel, redeploy the latest build so it includes `VITE_API_URL`. Open the site and sign in as `demo` with the `DEMO_PASSWORD` you configured. Do not give reviewers the administrator password.

### What this public deployment can and cannot demonstrate

This repository does not contain a remote Ubuntu collector or agent. The cloud API samples the Render container where it runs; it does not see the developer's Windows laptop or personal Ubuntu/WSL machine. The Linux service inventory, systemd dependency graph, service-control actions, and journal are unavailable unless the API itself runs on a Linux host with systemd and the necessary journal access. The free Render container is not a supported substitute for the host you intend to monitor. Do not describe this cloud deployment as monitoring your Ubuntu computer.

The demo login has the `operator` role: it can view the hosted runtime and submit requests, but administrator-only user management, approval, and execution are protected. `ALLOWED_SERVICES` is empty in the Blueprint, so no service can be controlled by this public instance. For a live demonstration of systemd and journal features, run the backend on the Ubuntu system being demonstrated and use the Ubuntu deployment above.

### Verify and troubleshoot

- **Website only loads the login page or shows an API error:** confirm Vercel's `VITE_API_URL` contains the Render API URL and `/api`, then redeploy Vercel.
- **Browser reports a CORS error:** set Render `CORS_ORIGINS` to the exact Vercel origin (`https://…vercel.app`, without a path or trailing slash), save, and wait for its redeploy.
- **Render reports database connection failure:** check Neon is active, copy the current SSL connection string, and update Render `DATABASE_URL` without quotes or spaces.
- **The first request is slow or times out:** the Render Free service may be waking from sleep; retry after it starts.
- **Login fails:** verify `demo` and the configured `DEMO_PASSWORD`. The password is only used to create the account when it does not already exist; changing the environment variable later does not reset the stored password.
- **No services or journal entries appear:** this is expected on Render. The cloud container is not your Ubuntu host and may not run systemd or expose its journal.

After deployment, verify the public API health endpoint, demo login, dashboard API calls, and Vercel page refresh. Verify Linux-only features separately on the Ubuntu host. Do not mark them as passed based on the cloud deployment.
