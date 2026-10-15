# Operator and administrator manual

## Sign in

Open the configured web origin and sign in using the administrator account initialized by `ADMIN_USERNAME` and `ADMIN_PASSWORD`. The environment password is used only when the database has no account. After first sign-in, change the password under Operations & admin. An expired or revoked session returns to sign-in.

## Monitoring

- Dashboard shows the latest sampled host CPU, memory, disk, network and runtime context with a rolling chart.
- Processes lists the latest observed processes. Search by name/PID/user and select the PID for detail. Secret-like command arguments are redacted.
- Services lists observed systemd units. Only configured allowlisted targets expose an operation control; other rows are read-only.
- System logs searches/severity-filters the journal entries visible to the backend OS account.
- Alerts & anomalies distinguishes alert severity from stored statistical anomaly findings. Administrators can acknowledge alerts and resolve anomaly records.
- Dependencies shows typed unit relationships and the source/coverage of the observed graph. `After`/`Before` edges describe ordering, not functional requirements.

On Windows, service, dependency and journal data may be empty because systemd is not available. The health endpoint is authoritative for integration availability. Forecasts require at least 12 actual observations; anomaly detection requires at least 20.

## Predictive and diagnostic pages

- Forecasts & models shows current CPU/memory/disk trend estimates, threshold crossing when measurable, selected method, sample count, walk-forward MAE and its baseline comparison.
- Root cause lists hypotheses with evidence strength definitions, supporting observations, alternatives and diagnostic steps. The score is not a probability and a correlation is not proof of cause.
- Recommendations are advisory. Review evidence, risk factors, benefit, potential impact, verification and “do not follow when” guidance. Dismiss or resolve a recommendation to update its state; this does not execute an operation.

## Incidents

Open Incidents, click the incident ID for linked alert, related anomalies/predictions, root-cause findings, operation records, impact/risk reports and audit events. Administrators can change status, assign an account, and provide resolution/closure notes. Automated threshold and observed service-failure alerts create incidents under a deterministic alert-ID key.

## Safe service operation

1. On Services, request an allowlisted restart. The interface fetches the latest impact and risk assessment first.
2. Review classification, potential dependents, risk score and unknown evidence. Cancel if the target or dependencies are unclear.
3. Enter a specific reason. The API persists a request that expires after 30 minutes.
4. An administrator reviews impact/risk factors and approves or rejects with a reason. High-risk approval must come from someone other than the requester.
5. An administrator can execute an approved request. The server rechecks expiry, operation fingerprint, allowlist, protected-service rules and prior service state before using a fixed `systemctl` command.
6. The API verifies expected active state, records VERIFIED or FAILED, updates a linked incident if present, and writes an audit event.

Protected-service stop requests are prohibited regardless of score or approval. No arbitrary command input is available. On a host without systemd, an approved execution is recorded as failed with the integration limitation.

## Administration

Administrators can inspect the approval queue, execute previously approved actions, set CPU/memory/disk alert percentages, create user accounts and rotate their password. Audit history is administrator-only. Use distinct named accounts and least privilege; do not share the bootstrap account.
