from datetime import datetime, timedelta, timezone

from app.forecasting import forecast_resources
from app.safety import WEIGHTS, action_fingerprint, assess_action


def test_forecast_requires_real_history_and_uses_walk_forward_metrics():
    short = forecast_resources([])
    assert all(item["status"] == "insufficient_data" for item in short)
    start = datetime.now(timezone.utc) - timedelta(hours=24)
    rows = [
        {"timestamp": (start + timedelta(hours=index)).isoformat(), "cpu_usage": 30 + index, "memory_usage": 40, "disk_usage": 55}
        for index in range(16)
    ]
    forecasts = forecast_resources(rows)
    cpu = next(item for item in forecasts if item["metric"] == "cpu_usage")
    assert cpu["sample_count"] == 16
    assert cpu["evaluation_count"] > 0
    assert cpu["baseline_mae"] is not None
    assert "not a prediction that a system failure" in cpu["explanation"]


def test_risk_weights_and_protected_service_policy_are_explicit():
    assert sum(WEIGHTS.values()) == 1
    result = assess_action("stop", "ssh", "active", [], [], None)
    assert result["score"] <= 100
    assert result["policy"]["decision"] == "prohibited"
    assert result["unknowns"]
    assert action_fingerprint("restart", "ssh") != action_fingerprint("stop", "ssh")


def test_postgres_schema_compiles_and_insert_adapter_binds_parameters():
    from sqlalchemy import BigInteger
    from sqlalchemy.dialects import postgresql
    from sqlalchemy.schema import CreateTable

    from app.database import ConnectionAdapter
    from app.models import Base, ProcessSnapshot, SystemMetric

    assert len(Base.metadata.tables) == 24
    assert all(isinstance(SystemMetric.__table__.c[name].type, BigInteger) for name in (
        "network_received", "network_sent", "memory_available", "disk_total_bytes",
        "disk_used_bytes", "disk_read_bytes", "disk_write_bytes",
    ))
    assert isinstance(ProcessSnapshot.__table__.c.memory_bytes.type, BigInteger)
    ddl = [str(CreateTable(table).compile(dialect=postgresql.dialect())) for table in Base.metadata.sorted_tables]
    assert all("CREATE TABLE" in statement for statement in ddl)

    class Result:
        rowcount = 1
        returns_rows = True

        @staticmethod
        def scalar_one_or_none():
            return 27

    class Connection:
        class Dialect:
            name = "postgresql"

        dialect = Dialect()

        def execute(self, statement, parameters):
            self.statement = statement
            self.parameters = parameters
            return Result()

    connection = Connection()
    result = ConnectionAdapter(connection).execute(
        "INSERT OR IGNORE INTO logs(timestamp,message) VALUES (?,?)",
        ("2026-01-01T00:00:00+00:00", "safe bound value"),
    )
    sql = str(connection.statement.compile(dialect=postgresql.dialect()))
    assert "ON CONFLICT DO NOTHING RETURNING id" in sql
    assert connection.parameters == {"p0": "2026-01-01T00:00:00+00:00", "p1": "safe bound value"}
    assert result.lastrowid == 27
