# Implementation phases and remaining verification

The upstream repository originally contained only its license. This document records the phases completed in the application and identifies environmental verification that still requires a real Ubuntu deployment.

## Phase 1 — Foundation and authentication

- React/Vite interface and FastAPI API.
- SQLite persistence, root environment configuration, health endpoint, password hashing, expiring hashed bearer sessions, logout, password rotation and role-aware access.
- Account creation and login throttling.

## Phase 2 — Continuous host monitoring

- Managed background collector with graceful shutdown, collector status, error state, and interval configuration.
- Actual CPU, memory, disk capacity and I/O, network totals and rates, interface state, load average, process snapshots and host data.
- Historical queries, indexed storage, stale-data indication and retention cleanup.

## Phase 3 — Explainable intelligence

- Multivariate Isolation Forest where scikit-learn is installed, with robust MAD fallback; persistent findings include score, method, baseline and explanation.
- CPU, memory and disk trend forecasts require at least 12 observations and use chronological walk-forward MAE compared with a last-value baseline.
- Evidence-ranked root-cause hypotheses include alternatives, diagnostics and confidence definitions that distinguish evidence strength from probability or causal proof.
- Systemd relationship/ordering graph, service impact and weighted risk report, and evidence-linked recommendations.

## Phase 4 — Controlled operations and incidents

- Alerts create linked incidents; incident records support assignment, investigation, resolution and notes.
- Service operations are persistent requests with expiry, exact-operation fingerprint, risk review, allowlist, protected-service policy, state revalidation, administrator approval and audit.
- High-risk requests require approval by someone other than their requester. No automatic remediation is performed.

## Phase 5 — Integrated interface and release material

- Views for dashboard, processes, services, logs, alerts/anomalies, dependencies, forecasts/models, root-cause hypotheses, recommendations, incidents, approvals/configuration, accounts and audit history.
- API guide, requirements traceability, local setup and Ubuntu deployment guidance.
- Backend tests and production frontend build pass in this Windows workspace.

## Remaining environment-dependent work

- Validate systemd inventory, dependency edge direction, journal permissions, service-operation sudo policy and state verification on the target Ubuntu release.
- Capture real Ubuntu screenshots and run integration tests against disposable systemd units.
- Select and deploy PostgreSQL/Alembic if required; this implementation intentionally retains the original SQLite store.
- Run workload-specific model evaluation with representative real history and set operational thresholds/criticality policy.
- Configure production HTTPS, reverse proxy, backup/restore, monitoring and least-privilege service account.

No production host, workload dataset, PostgreSQL instance, or real service action was available in the development environment, so those items are not marked verified.
