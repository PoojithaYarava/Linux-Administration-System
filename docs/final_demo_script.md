# Final project demonstration script

This script distinguishes the runnable local Windows demonstration from Linux-only validation. Use a disposable Ubuntu VM for real service actions; never demonstrate a stop/restart against a production service.

## Local application demonstration

1. From repository root, start FastAPI and Vite using the README commands. Sign in with the locally configured administrator account.
2. Open Dashboard. Point out the collection timestamp, stale state and actual host CPU/memory/disk/network values. Explain that on Windows these are Windows-host observations and Linux integration reports unavailable.
3. Open Processes and inspect a PID. Show the redacted command field and resource usage.
4. Open Alerts & anomalies and explain that the views distinguish configured threshold alerts from unsupervised deviations. Acknowledge an alert if one exists; do not fabricate an anomaly.
5. Open Forecasts & models. Explain that after 12 actual collection samples the displayed horizon/resource forecast is evaluated against a chronological last-value baseline. Until then, the correct state is insufficient history.
6. Open Root cause. Read one evidence-backed hypothesis, its alternatives and diagnostic steps; emphasize the evidence score is not a probability.
7. Open Services and select an allowlisted unit. Review the impact/risk confirmation, submit a reasoned request and inspect Operations & admin for its persisted state.
8. Sign in with a separate administrator when demonstrating the second-person rule. Review the JSON evidence, approve/reject with a reason, then execute only in the disposable lab. Confirm verification result and Audit history.
9. Open Incidents; show an alert-linked incident, assign it, update status, open detail and record resolution notes.
10. Open Users and create an operator with a unique 12+ character password. Sign in as the operator and show the permission boundaries.

## Ubuntu integration demonstration (requires a separate target host)

1. Deploy according to [Ubuntu deployment](deployment.md), set a dedicated OS account, exact CORS origin, durable SQLite path and narrowly scoped service permissions.
2. Verify `GET /api/health` reports `linux_integration: true`, collector success and increasing observation count.
3. Show actual service inventory, enablement state, dependency graph and journal entries visible to the service account.
4. In a disposable test VM only, use a dedicated test unit to produce a controlled failed state. Verify a service-failure alert/incident, journal evidence and dependency context appear. Restore the test unit.
5. Request a permitted non-critical operation on the test unit; inspect impact/risk, obtain separate approval if policy requires it, execute, verify systemd state, and inspect incident/audit links.
6. Verify a protected-service stop is rejected and a target outside `ALLOWED_SERVICES` cannot be submitted.
7. Capture actual screenshots and record the host version, permissions, test-unit definition, timestamps and outcomes in the submission. These screenshots are not included because this workspace had no Ubuntu target.

## Supporting commands

```bash
# From the backend directory on the configured host
curl -sS http://127.0.0.1:8000/api/health
curl -sS http://127.0.0.1:8000/docs

# Backend checks from backend/
py -3 -m pytest tests -q  # Windows
python -m pytest tests -q # Ubuntu/Linux

# Frontend build from frontend/
npm ci
npm run build
```
