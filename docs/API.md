# API reference

Base path: `/api`. Except for health and login, routes require `Authorization: Bearer <token>`. Sessions expire after `SESSION_TTL_HOURS`; tokens are stored as SHA-256 hashes and survive API process restarts. Changing the password invalidates every session for that account.

## Health and authentication

| Method | Route | Access | Description |
| --- | --- | --- | --- |
| `GET` | `/health` | Public | API status, host platform, and Linux integration availability |
| `POST` | `/auth/login` | Public | Accepts `username` and `password`; returns a bearer token and user |
| `POST` | `/auth/logout` | Signed in | Invalidates the current session |
| `POST` | `/auth/change-password` | Administrator | Accepts `current_password` and a `new_password` of at least 12 characters; revokes sessions |

## Host data

| Method | Route | Description |
| --- | --- | --- |
| `GET` | `/system/info` | Hostname, OS, kernel, architecture, uptime, CPU count, and Python version |
| `GET` | `/system/metrics?limit=60` | Collects a snapshot and returns it with up to 500 history points |
| `GET` | `/system/health` | Collects a snapshot and returns a healthy/degraded status |
| `GET` | `/processes` | Current process inventory |
| `GET` | `/processes/{pid}` | Detail for one process |
| `GET` | `/services` | systemd service inventory |
| `GET` | `/services/{name}` | Properties for an allowlisted service |
| `GET` | `/logs?limit=100&severity=warning&service=ssh&search=...` | Recent journal entries with optional filters |

## Alerts and administration

| Method | Route | Access | Description |
| --- | --- | --- | --- |
| `GET` | `/alerts` | Signed in | Recent threshold alerts |
| `PATCH` | `/alerts/{id}/acknowledge` | Administrator | Acknowledge an open alert and write an audit event |
| `GET` | `/anomalies` | Signed in | Historical metrics with anomaly flags and explanations |
| `POST` | `/services/{name}/{start\|stop\|restart}` | Administrator | Operate an allowlisted systemd service; records an action and audit event |
| `POST` | `/actions` | Administrator | Same controlled action using `{ "action_type": "restart", "target": "ssh" }` |
| `GET` | `/actions` | Administrator | Recent administrative actions |
| `GET` | `/audit` | Administrator | Recent audit events and usernames |

FastAPI's generated interactive reference is available at `/docs`; the OpenAPI document is at `/openapi.json`.

## Status and errors

Successful routes return JSON. Authentication failures return `401`, role failures return `403`, invalid operations return `400`, missing resources return `404`, and unavailable host integrations may return `503`. Error payloads use FastAPI's `detail` field.
