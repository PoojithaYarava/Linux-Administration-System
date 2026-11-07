"""SQLAlchemy engine and small parameterized SQL compatibility adapter."""

from __future__ import annotations

import re
from contextlib import contextmanager
from typing import Any, Iterator

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection, Engine


ID_TABLES = {"users", "system_metrics", "processes", "services", "logs", "alerts", "actions", "audit_logs", "service_dependencies", "service_snapshots", "anomaly_findings", "predictions", "model_versions", "evaluation_runs", "root_cause_findings", "impact_assessments", "risk_assessments", "recommendations", "approvals", "incidents"}


class ResultAdapter:
    def __init__(self, result: Any, lastrowid: int | None = None):
        self._result = result
        self.lastrowid = lastrowid
        self.rowcount = result.rowcount

    def fetchone(self):
        return self._result.mappings().fetchone() if self._result.returns_rows else None

    def fetchall(self):
        return self._result.mappings().fetchall() if self._result.returns_rows else []

    def __iter__(self):
        return iter(self._result.mappings()) if self._result.returns_rows else iter(())


class ConnectionAdapter:
    def __init__(self, connection: Connection):
        self.connection = connection
        self.dialect = connection.dialect.name

    def execute(self, statement: str, parameters: Any = ()) -> ResultAdapter:
        if self.dialect == "sqlite":
            sqlite_parameters = tuple(parameters) if isinstance(parameters, (list, tuple)) else parameters or ()
            result = self.connection.exec_driver_sql(statement, sqlite_parameters)
            return ResultAdapter(result, getattr(result, "lastrowid", None))

        sql = statement
        ignore_insert = bool(re.match(r"\s*INSERT\s+OR\s+IGNORE\s+INTO\b", sql, re.IGNORECASE))
        if ignore_insert:
            sql = re.sub(r"\bINSERT\s+OR\s+IGNORE\s+INTO\b", "INSERT INTO", sql, count=1, flags=re.IGNORECASE)
            if "ON CONFLICT" not in sql.upper():
                sql = sql.rstrip().rstrip(";") + " ON CONFLICT DO NOTHING"

        binds: dict[str, Any] = {}
        if isinstance(parameters, dict):
            binds = parameters
        elif parameters:
            index = 0

            def bind(_match):
                nonlocal index
                name = f"p{index}"
                binds[name] = parameters[index]
                index += 1
                return ":" + name

            sql = re.sub(r"\?", bind, sql)

        lastrowid = None
        inserted_table = re.match(r"\s*INSERT\s+INTO\s+([a-z_][a-z0-9_]*)\b", sql, re.IGNORECASE)
        if inserted_table and inserted_table.group(1).lower() in ID_TABLES and "RETURNING" not in sql.upper():
            sql = sql.rstrip().rstrip(";") + " RETURNING id"
            result = self.connection.execute(text(sql), binds)
            inserted_id = result.scalar_one_or_none()
            lastrowid = int(inserted_id) if inserted_id is not None else None
            return ResultAdapter(result, lastrowid)

        result = self.connection.execute(text(sql), binds)
        return ResultAdapter(result, lastrowid)

    def executemany(self, statement: str, parameter_rows: list[tuple[Any, ...]]) -> ResultAdapter:
        if self.dialect == "sqlite":
            result = self.connection.exec_driver_sql(statement, parameter_rows)
            return ResultAdapter(result, getattr(result, "lastrowid", None))
        if not parameter_rows:
            return ResultAdapter(self.connection.exec_driver_sql("SELECT 1 WHERE 1=0"))
        sql = statement
        if re.match(r"\s*INSERT\s+OR\s+IGNORE\s+INTO\b", sql, re.IGNORECASE):
            sql = re.sub(r"\bINSERT\s+OR\s+IGNORE\s+INTO\b", "INSERT INTO", sql, count=1, flags=re.IGNORECASE)
            if "ON CONFLICT" not in sql.upper():
                sql = sql.rstrip().rstrip(";") + " ON CONFLICT DO NOTHING"
        converted_rows = []
        for parameters in parameter_rows:
            index = 0
            binds: dict[str, Any] = {}

            def bind(_match):
                nonlocal index
                name = f"p{index}"
                binds[name] = parameters[index]
                index += 1
                return ":" + name

            converted_sql = re.sub(r"\?", bind, sql)
            converted_rows.append(binds)
        result = self.connection.execute(text(converted_sql), converted_rows)
        return ResultAdapter(result)

    def commit(self) -> None:
        self.connection.commit()

    def executescript(self, script: str) -> None:
        for statement in script.split(";"):
            if statement.strip():
                self.execute(statement)


@contextmanager
def database_session(engine: Engine) -> Iterator[ConnectionAdapter]:
    connection = engine.connect()
    transaction = connection.begin()
    try:
        yield ConnectionAdapter(connection)
        if transaction.is_active:
            transaction.commit()
    except Exception:
        if transaction.is_active:
            transaction.rollback()
        raise
    finally:
        connection.close()


def make_engine(database_url: str) -> Engine:
    options: dict[str, Any] = {"pool_pre_ping": True}
    if database_url.startswith("sqlite:"):
        options["connect_args"] = {"check_same_thread": False, "timeout": 10}
    return create_engine(database_url, **options)
