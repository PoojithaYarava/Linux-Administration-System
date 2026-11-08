"""Widen telemetry byte counters to PostgreSQL BIGINT."""

from alembic import op
from sqlalchemy import BigInteger, Integer

revision = "0002_widen_telemetry_bytes"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


BYTE_COLUMNS = {
    "system_metrics": (
        "network_received",
        "network_sent",
        "memory_available",
        "disk_total_bytes",
        "disk_used_bytes",
        "disk_read_bytes",
        "disk_write_bytes",
    ),
    "processes": ("memory_bytes",),
}


def upgrade():
    for table, columns in BYTE_COLUMNS.items():
        for column in columns:
            op.alter_column(
                table,
                column,
                existing_type=Integer(),
                type_=BigInteger(),
                existing_nullable=False,
                postgresql_using=f"{column}::bigint",
            )


def downgrade():
    for table, columns in BYTE_COLUMNS.items():
        for column in columns:
            op.alter_column(
                table,
                column,
                existing_type=BigInteger(),
                type_=Integer(),
                existing_nullable=False,
                postgresql_using=f"{column}::integer",
            )
