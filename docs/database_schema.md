# Database schema and data management

## Storage selection

The starting repository already used SQLite, so this delivery retains it for compatible local operation. FastAPI initializes the schema at startup with `CREATE TABLE IF NOT EXISTS` and additive column migrations based on `PRAGMA table_info`. There is no SQLAlchemy ORM, Alembic history, PostgreSQL driver, or per-monitored-host tenancy. Deployments that require PostgreSQL need a separate reviewed migration and concurrency effort; SQLite is the verified implementation here.

## Tables

| Table | Purpose / important links |
| --- | --- |
| `users` | Unique username, PBKDF2 hash, role, created time |
| `sessions` | SHA-256 token hash, user FK, created/expiry; deleted on logout/password change |
| `system_metrics` | Timestamped validated host CPU, memory, filesystem, I/O, network, load, availability and process count |
| `processes` | Timestamped PID/name/resource/user/start/command snapshots; secret-like arguments are redacted |
| `services` | Latest systemd unit inventory and enablement state |
| `service_snapshots` | Historical active/sub/load/enabled state |
| `service_dependencies` | Typed source/target systemd relationship with observation time/source |
| `logs` | Journal entries indexed by cursor; no raw command output is persisted |
| `alerts` | Threshold, service-failure and anomaly alerts with lifecycle status |
| `anomaly_findings` | Metric FK, detector, baseline, observed value, score, explanation and lifecycle |
| `predictions` | Resource estimate, horizon, threshold crossing, walk-forward and baseline MAE |
| `model_versions`, `evaluation_runs` | Model method/version/configuration and chronological evaluation results |
| `root_cause_findings` | Hypothesis, evidence, confidence definition, alternatives, diagnostics, incident link |
| `recommendations` | Unique recommendation key, evidence, risk, expected benefit, verification and review status |
| `incidents` | Alert-linked title, severity, component, status, assignee, resolution and timestamps |
| `actions`, `approvals`, `incident_actions` | Persistent operation workflow, exact-target approval records and incident links |
| `impact_assessments`, `risk_assessments` | Structured reports with actor/action/incident references and timestamp |
| `audit_logs` | Actor, action, target, result and UTC timestamp |
| `collector_state` | Sampling health, last attempt/success, error and count |
| `app_config` | Audited administrator-managed alert thresholds |

Indexes cover metric/process timestamps, log journal cursors, alert/incident status, action state, prediction/anomaly history and service snapshots. Foreign keys are enabled for each connection. Collection values are validated before insert; timestamps use ISO-8601 UTC.

## Initialization and retention

No manual migration command is needed: the app creates and upgrades the SQLite schema during startup. Set `DATABASE_PATH` to a durable, writable path before starting the backend. `RETENTION_DAYS` controls cleanup of metric, process, service, journal and prediction rows. Incident, audit, model and recommendation records are retained for traceability and need an explicit organizational retention policy.

## Backup and restore

On Ubuntu with the SQLite CLI, stop the backend for a simple consistent file backup, or use the SQLite online backup command while it is running:

```bash
sqlite3 /var/lib/linux-admin-platform/platform.db ".backup '/var/backups/linux-admin-platform-$(date +%F).db'"
```

To restore, stop the service, preserve the current database, copy the selected backup to the configured `DATABASE_PATH`, set ownership/mode for the service account, and restart. Verify health and inspect recent metric/action/incident rows. Test restores in a separate environment. Never copy a live SQLite database as a plain file and assume the copy is consistent.
