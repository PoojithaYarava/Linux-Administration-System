# Final project report — Predictive and Explainable Linux Administration Platform

## Problem and objective

Linux administrators need a single view of resource health, service state, logs and safe operational decisions. This project connects host collection and stored history to explainable statistical signals, an approval-based operation path, incidents and audit records. The objective is diagnostic support with accountable human control, not autonomous remediation.

## Delivered architecture

The React/Vite client calls a FastAPI service. A background collector stores psutil metrics and process snapshots in SQLite; on Linux it also queries systemd and journalctl. Analytics calculate statistical anomalies, a resource trend forecast and evidence-ranked root-cause hypotheses. Alert-linked incidents and separate recommendation records are persisted. Service operation requests use a persistent approval/revalidation state machine with risk/impact reports, and administrator decisions/actions are audited.

See [architecture](architecture.md), [system design](system_design.md), [database schema](database_schema.md), and the [API guide](api_documentation.md).

## Methods

- Anomaly detection uses multivariate Isolation Forest when scikit-learn is available, with robust MAD fallback; findings are explicitly not confirmed failures.
- Resource forecasting estimates CPU, memory and disk utilization from chronological host history. It compares a linear trend against a last-value baseline with walk-forward MAE. It does not claim failure prediction without labels.
- Root-cause support correlates actual metric/process/service/log/dependency/action/anomaly/forecast evidence. Its score definitions represent evidence strength rather than probability or causal certainty.
- Action risk is a documented weighted 0–100 score. Authorization, protected-operation policy and approval requirements remain separate gates.

Detailed assumptions and limitations are in [ML methodology](ml_methodology.md) and [security](security.md).

## Verification results

At the current verification checkpoint, the backend suite reported 12 passed with five framework deprecation warnings, and the pinned frontend dependencies produced a successful Vite production build. API/preview health probes returned HTTP 200, and the API reported a running collector on Windows. These checks establish local software behavior only.

No Ubuntu host, systemd test service, representative Linux dataset, PostgreSQL instance, or labeled failure dataset was available. Therefore systemd dependency accuracy, journal visibility, privileged operation execution, real Ubuntu failure recovery and workload-specific ML quality remain unverified. No model accuracy claim or synthetic result is included.

## Security and operations

Passwords are PBKDF2-hashed, session tokens are stored only as hashes, roles protect administrative routes, operation targets are allowlisted, protected service stop requests are prohibited, and command execution avoids shell interpolation. Deploy behind HTTPS, use a dedicated unprivileged account, scope OS permissions to named services, configure a strong initial password and back up SQLite consistently.

## Reproduction

Follow [Ubuntu deployment](deployment.md), [user manual](user_manual.md), and [testing/evaluation](testing_and_evaluation.md). The local database is created at application startup. For a real Linux project demonstration, use a disposable test unit and collect enough history to exercise forecasting.

## Remaining work

The current deliverable preserves SQLite rather than PostgreSQL/SQLAlchemy/Alembic. It has an inline idempotent bootstrap, not an Alembic migration history. It does not include Docker Compose, notebooks, a trained serialized model artifact, per-system tenant model, or captured Ubuntu screenshots. Those are not claimed complete; see the traceability checklist for the exact evidence boundary.
