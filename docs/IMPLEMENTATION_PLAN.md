# Implementation phases

The initial GitHub repository did not include a phase plan or source beyond its license. This plan records the completed phases represented by the working application and gives the next work a clear boundary.

## Delivered

### Phase 1 — Application foundation

- Responsive React navigation, login screen, dashboard layout, charts, tables, and empty/loading/error states.
- FastAPI application structure, SQLite persistence, environment configuration, and Vite `/api` proxy for local development.

### Phase 2 — Authentication and administration

- Password hashing with PBKDF2, expiring bearer sessions persisted as token hashes, sign-out, session revocation after password changes, and administrator-only operations.
- Allowlisted systemd actions, recorded results, and an audit trail.

### Phase 3 — Host observability

- CPU, memory, disk, network, uptime, host metadata, process inventory, systemd service inventory, and journal access.
- Search and severity filters for log entries; service search and controlled restart actions.

### Phase 4 — Intelligence and response

- Threshold alert generation with open-alert deduplication.
- Historical anomaly detection with Isolation Forest when scikit-learn is installed and a documented statistical fallback otherwise.
- Alert acknowledgement, audit recording, and dashboard refresh/recovery behavior.

### Phase 5 — Local setup and release readiness

- Reproducible pinned frontend dependencies, environment example, ignored local data/secrets, API documentation, implementation plan, and setup/troubleshooting guide.

## Follow-up work

- Add automated frontend and backend checks to CI and publish a reviewed release workflow.
- Add role management, per-user accounts, and stronger production authentication (for example, rate limiting and an external identity provider).
- Add a background telemetry collector so metric history continues when no dashboard is open.
- Add Linux integration tests using disposable systemd units and access-controlled journal fixtures.
- Add model evaluation, feature-window controls, and operator feedback for anomaly quality.
- Add deployment packaging for a native Ubuntu host and a reverse proxy with TLS.

These follow-ups require deployment and operational choices that are not present in the initial project brief; the local application remains useful without them.
