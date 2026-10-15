# Master prompt delivery checklist

This matrix distinguishes implemented software behavior from host-dependent evidence. A Windows development host cannot verify Ubuntu systemd, journal access, or Linux service operations.

| Area | Delivered implementation | Verification / limit |
| --- | --- | --- |
| Monitoring | Background collector; validated CPU, memory, disk, disk I/O, network totals/rates, interfaces, load, process snapshots, timestamps and freshness | API tests and Windows host run; systemd integrations are Linux-only |
| History and retention | SQLite history, time filters, indexes, configurable retention cleanup | Test suite; deploy with a persistent writable data volume and backup schedule |
| Anomaly detection | Multivariate Isolation Forest when available; robust MAD fallback; persisted score, method, baseline, explanation, acknowledgement/resolution | Unit/API paths; no synthetic production scores are claimed |
| Forecasting | Resource threshold trend estimate, minimum history, chronological walk-forward MAE versus last-value baseline, persisted model/evaluation metadata | Unit tests; not a failure probability and accuracy requires workload history |
| Root cause | Ranked correlation hypotheses with evidence, alternatives, diagnostics, score definition and explicit uncertainty | Rule-based explanation; not causal proof |
| Dependencies | systemd unit relationship and ordering edges with source and coverage notes | Requires Ubuntu/systemd and unit visibility for representative graph evidence |
| Impact and risk | Weighted, explainable 0–100 score; unknown evidence surfaced; protected service stop is prohibited | Unit tests; tune criticality and policy for the deployment |
| Recommendations | Evidence-linked, persistent, dismissible/resolvable guidance; no automatic remediation | API/frontend paths; operational benefit depends on operator review |
| Approval workflow | Persistent request, expiry, requester/reviewer separation for high risk, operation fingerprint, state revalidation, allowlist and audit | API tests; actual systemctl execution cannot be verified on Windows |
| Incidents | Threshold/anomaly alert correlation, status, assignee, resolution notes, linked action records | API/UI paths; broader alert correlation policy remains deploy-specific |
| Security | PBKDF2 passwords, hashed bearer tokens, expiry/revocation, login throttling, role checks, allowlisted service actions and command redaction | API tests; configure strong initial password, HTTPS and least-privilege Linux service account |
| Database | Existing SQLite preserved; idempotent schema bootstrap and additive compatibility columns | No PostgreSQL backend or versioned Alembic migrations in this delivery |
| Frontend | Dashboard, process/service/log views, dependencies, forecasts/models, RCA, recommendations, incidents, approvals/config, user management and audit | `npm.cmd run build` completed successfully; local API and browser preview smoke-check in progress |
| Ubuntu deployment | Environment settings, run guide, privilege guidance, architecture and backup notes | Ubuntu/systemd execution and screenshots require a real Ubuntu host, not present in this workspace |

No real Ubuntu workflow, production dataset, PostgreSQL deployment, or model quality claim is reported without the infrastructure and observations needed to verify it.
