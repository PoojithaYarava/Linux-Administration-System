# Testing and evaluation record

## Automated checks run in the current workspace

| Check | Command | Result |
| --- | --- | --- |
| Backend API/unit suite | `cd backend && py -3 -m pytest tests -q` | 12 passed; 5 framework deprecation warnings |
| Frontend production bundle | `cd frontend && npm.cmd run build` | Successful Vite 8.3 production build; React bundle and lazy chart chunks emitted |
| Patch whitespace | `git diff --check` | Clean at the time of the repository audit |
| Local health smoke check | `GET http://127.0.0.1:8000/api/health` | HTTP 200; collector was running and reported Windows/Linux integration unavailable |
| Browser origin smoke check | `GET http://127.0.0.1:5173/api/health` | HTTP 200 through the Vite proxy |

The twelve automated tests cover login/metrics, authentication failure, absence of the old direct service endpoint, password rotation/session revocation, action request persistence, config validation, impact/risk persistence and protected stop policy, incident detail/lifecycle, root-cause uncertainty fields, expiry handling, exact target binding and unavailable-systemd execution failure, chronological forecasting, and risk formula behavior. These tests use the local SQLite test database and do not demonstrate privileged Linux execution.

## Actual model measurements

No representative Ubuntu workload history or labeled outage dataset was available when this record was prepared. Therefore no production forecast MAE, anomaly precision/recall, failure prediction accuracy, or Ubuntu benchmark is claimed. Forecast evaluation rows are generated only after at least 12 real stored observations and contain chronological walk-forward MAE versus a last-value baseline. Anomaly findings are unsupervised and have no labeled quality score.

## Unverified scenarios

- Workflow A needs an actual unusual host observation to verify collector-to-alert-to-acknowledgment through the complete runtime.
- Workflow B's code and UI are tested with deterministic unit observations; sufficient live history and target workload forecast behavior remain to be collected.
- Workflow C needs an Ubuntu disposable test service that can be failed safely and its journal/dependencies observed.
- Workflow D's request/approval safety logic is API-tested, but actual systemctl execution and resulting state verification were not run on this Windows host.
- Workflow E has unit/API coverage for selected invalid, prohibited and session cases; expired/revalidation failure and failed Linux command scenarios require additional integration fixtures.

## Framework warnings

FastAPI's `on_event` startup/shutdown API and the installed Starlette/httpx test integration emit deprecation warnings. The tests pass; this should be migrated with the pinned framework compatibility update before long-term maintenance.
