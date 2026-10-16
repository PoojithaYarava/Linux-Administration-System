# API reference

The API is rooted at `/api`. `GET /api/health` is public for liveness checks; all other routes require `Authorization: Bearer <token>` unless marked Administrator. OpenAPI is available at `/docs` while the backend runs.

## Authentication and accounts

| Method | Route | Access |
| --- | --- | --- |
| POST | `/auth/login` | Public; returns bearer token and user |
| POST | `/auth/logout` | Signed in |
| POST | `/auth/change-password` | Administrator |
| GET, POST | `/users` | Administrator; create validates 12-character minimum password |

## Telemetry and diagnostics

| Method | Route | Purpose |
| --- | --- | --- |
| GET | `/health` | Collector state, platform and Linux integration availability |
| GET | `/system/info` | Host and OS details |
| GET | `/system/metrics?limit=60` | Latest stored observation, history, staleness |
| GET | `/system/metrics/history?start=<ISO>&end=<ISO>&limit=500` | Time-filtered metric history; when a time filter matches more rows than `limit`, evenly spaced observations (including both range endpoints) are returned |
| GET | `/system/disk` | Partition capacities and device I/O counters |
| GET | `/system/health` | Latest host health assessment |
| GET | `/processes` and `/processes/{pid}` | Process snapshots and detail; credential-like command args are redacted |
| GET | `/services` and `/services/{name}` | systemd inventory and allowlisted unit detail |
| GET | `/dependencies?service=<name>&depth=2` | Observed systemd dependency and ordering graph |
| GET | `/logs?limit=100&severity=<level>&service=<name>&search=<text>` | journal entries, filtered and persisted by cursor |
| GET | `/anomalies?status_filter=open` | Stored anomaly evidence |
| PATCH | `/anomalies/{id}?state=acknowledged\|resolved` | Administrator lifecycle update |
| GET | `/forecasts?horizon_hours=1` | Current resource trend estimates and data sufficiency |
| GET | `/predictions?metric=cpu_usage&limit=100` | Persisted forecast history |
| GET | `/models/status` | Model metadata, evaluation runs and observations |
| GET | `/root-causes?limit=50` | Evidence-ranked hypotheses, alternatives and diagnostics |
| GET | `/impact/{service}?operation=restart` | Explainable risk/impact report |
| GET | `/risk/{service}?operation=restart` | Persisted explainable 0–100 risk assessment and policy outcome |
| GET, PATCH | `/recommendations` and `/recommendations/{id}` | Review guidance and mark active/dismissed/resolved |

## Alerts, incidents and safe operations

| Method | Route | Access / behavior |
| --- | --- | --- |
| GET | `/alerts` | Signed in |
| PATCH | `/alerts/{id}/acknowledge` or `/alerts/{id}/resolve` | Administrator; resolve also updates linked active incident |
| GET | `/incidents?status_filter=open` | Signed in |
| PATCH | `/incidents/{id}` | Administrator; assign, investigate, resolve or close with notes |
| POST | `/actions` | Signed in; creates an expiring request, never executes immediately |
| GET | `/actions`, `/actions/{id}` | Admin sees all; operator sees own requests |
| POST | `/actions/{id}/decision` | Administrator approval/rejection; high-risk request requires a reviewer distinct from requester |
| POST | `/actions/{id}/execute` | Administrator; revalidates expiry, fingerprint, allowlist and pre-approved service state |
| POST | `/actions/{id}/cancel` | Requester or administrator |
| GET, PUT | `/config` | Administrator; update CPU, memory and disk alert thresholds |
| GET | `/audit` | Administrator |

Supported operation requests are fixed start/stop/restart actions for `ALLOWED_SERVICES`. Protected service stops are prohibited by policy. The backend does not accept arbitrary shell commands. A request can execute only on a Linux systemd host with the relevant permissions; otherwise it records the unavailable integration result.

## Data and deployment notes

SQLite is the delivered storage backend. `DATABASE_PATH` selects its file, and the service account must be able to write it. The collector runs in a managed background thread, stores timestamps in UTC, and prunes metric/process/service/log/prediction history according to `RETENTION_DAYS`. Back up the database file using a SQLite-consistent backup method.

For a browser client hosted on another origin, set `CORS_ORIGINS` to the exact trusted origin list. Protect the API with HTTPS and a least-privilege OS account. Service allowlist and protected-service settings are deployment policy, not per-request input.
