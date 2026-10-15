# API documentation index

The REST API uses the `/api` prefix, bearer-token authentication, Pydantic validation, role checks, and FastAPI-generated OpenAPI schemas.

- Complete routes, request behavior, access levels, and deployment notes: [API reference](API.md)
- Interactive OpenAPI UI while running: `http://localhost:8000/docs`
- OpenAPI JSON: `http://localhost:8000/openapi.json`
- Public liveness: `GET /api/health`

The route groups cover authentication/users, host/system data, metric history, processes, systemd inventory and dependencies, logs, alerts/anomalies, forecasts/models, RCA, impact/risk, recommendations, incidents, action approvals/execution, configuration and audit. All non-health routes require a valid bearer session.
