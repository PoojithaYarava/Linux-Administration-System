# System architecture

## Runtime components

```mermaid
flowchart LR
  Browser[React dashboard] -->|Bearer-authenticated JSON| API[FastAPI]
  API --> Auth[Authentication and policy]
  API --> Store[(SQLite database)]
  Collector[Background collector] --> Metrics[psutil host metrics]
  Collector --> Systemd[systemd unit properties]
  Collector --> Journal[journalctl]
  Metrics --> Collector
  Systemd --> Collector
  Journal --> Collector
  Collector --> Store
  API --> Intelligence[Anomaly, trend, RCA and recommendations]
  Intelligence --> Store
  API --> Actions[Approval and controlled actions]
  Actions --> Systemd
  Actions --> Store
  Actions --> Audit[Audit records]
  Store --> Browser
```

The React client reads real API data and displays explicit empty/error/staleness states. FastAPI serves authenticated workflows. A managed background thread collects on the configured interval; stored metrics are also used for chronological resource forecasts and anomaly detection. The administration action state machine shares policy, impact, risk, persistence and audit records.

## Trust boundaries

- The browser is an untrusted client. All request fields are validated server-side.
- The API has an OS identity distinct from the browser user. Linux deployments should use a dedicated account and narrowly scoped systemd permissions.
- The SQLite file contains account hashes and operational history. Its directory requires access control and backups.
- systemd and journal data are unavailable on Windows; the health response advertises this rather than synthesizing Linux results.

## Data flow

```mermaid
flowchart TD
  Host[Ubuntu host] --> Collector[Collector and validation]
  Collector --> History[(Timestamped SQLite history)]
  History --> Features[Validated time series]
  Features --> Anomaly[Statistical / Isolation Forest anomaly detection]
  Features --> Forecast[Resource trend estimate]
  Anomaly --> Alert[Alert and correlated incident]
  Forecast --> Recommendation[Evidence-linked recommendation]
  History --> RCA[Rule-based evidence ranking]
  Alert --> RCA
  Systemd[Dependency and unit snapshots] --> RCA
  RCA --> Dashboard[Authenticated React views]
  Alert --> Dashboard
  Forecast --> Dashboard
```

Storage is SQLite in this implementation, preserving the existing repository's selected database. PostgreSQL is not part of the delivered runtime.
