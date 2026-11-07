"""Copy an existing SQLite installation into a migrated PostgreSQL database.

The SQLite source is read-only. Set SOURCE_SQLITE_PATH and DATABASE_URL first.
Run this once against an empty PostgreSQL target and take a source backup before use.
"""

from __future__ import annotations

import os
import sqlite3
import sys
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import func, select, text

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from app.database import make_engine
from app.models import Base


TABLE_ORDER = (
    "users", "system_metrics", "processes", "services", "logs", "alerts", "incidents",
    "actions", "audit_logs", "sessions", "service_dependencies", "service_snapshots",
    "anomaly_findings", "predictions", "model_versions", "evaluation_runs", "root_cause_findings",
    "impact_assessments", "risk_assessments", "recommendations", "approvals", "incident_actions",
    "collector_state", "app_config",
)


def main() -> None:
    env_file = ROOT / ".env"
    if env_file.is_file():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                os.environ.setdefault(key.strip(), value.strip().strip("\"'"))
    source_path = os.getenv("SOURCE_SQLITE_PATH") or os.getenv("DATABASE_PATH")
    database_url = os.getenv("DATABASE_URL")
    if not source_path or not Path(source_path).is_file():
        raise SystemExit("Set SOURCE_SQLITE_PATH to the existing SQLite database file.")
    if not database_url or not database_url.startswith("postgresql"):
        raise SystemExit("Set DATABASE_URL to the PostgreSQL target URL.")

    config = Config(str(ROOT / "backend" / "alembic.ini"))
    config.set_main_option("script_location", str(ROOT / "backend" / "alembic"))
config.set_section_option("alembic", "sqlalchemy.url", database_url.replace("%", "%%"))
    command.upgrade(config, "head")
    engine = make_engine(database_url)
    source = sqlite3.connect(f"file:{Path(source_path).resolve().as_posix()}?mode=ro", uri=True)
    source.row_factory = sqlite3.Row

    try:
        with engine.begin() as target:
            for table_name in TABLE_ORDER:
                target_table = Base.metadata.tables[table_name]
                existing = target.execute(select(func.count()).select_from(target_table)).scalar_one()
                if existing:
                    raise RuntimeError(f"PostgreSQL table {table_name} is not empty; migrate into a fresh target database.")

            available = {row[0] for row in source.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            copied: dict[str, int] = {}
            for table_name in TABLE_ORDER:
                if table_name not in available:
                    copied[table_name] = 0
                    continue
                target_table = Base.metadata.tables[table_name]
                source_columns = {column[1] for column in source.execute(f"PRAGMA table_info({table_name})")}
                common_columns = [column.name for column in target_table.columns if column.name in source_columns]
                cursor = source.execute(f"SELECT {', '.join(common_columns)} FROM {table_name}")
                copied[table_name] = 0
                while batch := cursor.fetchmany(500):
                    records = [{column: record[column] for column in common_columns} for record in batch]
                    target.execute(target_table.insert(), records)
                    copied[table_name] += len(records)

            for table_name in TABLE_ORDER:
                table = Base.metadata.tables[table_name]
                if "id" in table.columns and table_name not in {"sessions", "app_config"}:
                    target.execute(
                        text("SELECT setval(pg_get_serial_sequence(:table_name, 'id'), COALESCE(MAX(id), 1), COUNT(*) > 0) FROM " + table_name),
                        {"table_name": table_name},
                    )
    finally:
        source.close()
        engine.dispose()

    print("Copied rows by table:")
    for table_name, count in copied.items():
        print(f"  {table_name}: {count}")
    print("SQLite source was read-only; retain it until the PostgreSQL deployment is verified.")


if __name__ == "__main__":
    main()
