"""Create metric_types and metric_entries tables.

Core schema for historical athlete metrics.

Revision ID: 008_metric_tables
Revises: 007_recalculation_jobs
Create Date: 2026-08-08
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "008_metric_tables"
down_revision = "007_recalculation_jobs"
branch_labels = None
depends_on = None


# Initial metric types to seed
METRIC_TYPES = [
    {
        "key": "ftp",
        "display_name": "Functional Threshold Power",
        "unit": "W",
        "category": "threshold",
        "data_type": "integer",
        "min_value": 50,
        "max_value": 500,
        "allowed_sources": ["manual", "calculated", "device"],
        "recalc_targets": ["power_zones", "tss", "if"],
        "sort_order": 1,
    },
    {
        "key": "lthr",
        "display_name": "Lactate Threshold HR",
        "unit": "bpm",
        "category": "threshold",
        "data_type": "integer",
        "min_value": 80,
        "max_value": 220,
        "allowed_sources": ["manual", "calculated", "device"],
        "recalc_targets": ["hr_zones"],
        "sort_order": 2,
    },
    {
        "key": "hrmax",
        "display_name": "Maximum Heart Rate",
        "unit": "bpm",
        "category": "threshold",
        "data_type": "integer",
        "min_value": 100,
        "max_value": 250,
        "allowed_sources": ["manual", "calculated", "device"],
        "recalc_targets": ["hr_zones"],
        "sort_order": 3,
    },
    {
        "key": "weight_kg",
        "display_name": "Weight",
        "unit": "kg",
        "category": "body",
        "data_type": "decimal",
        "min_value": 30,
        "max_value": 200,
        "allowed_sources": ["manual", "device"],
        "recalc_targets": ["vo2max", "w_per_kg"],
        "sort_order": 4,
    },
    {
        "key": "vo2max",
        "display_name": "VO2 Max",
        "unit": "ml/kg/min",
        "category": "fitness",
        "data_type": "decimal",
        "min_value": 20,
        "max_value": 90,
        "allowed_sources": ["manual", "calculated", "device"],
        "recalc_targets": None,
        "sort_order": 5,
    },
    {
        "key": "resting_hr",
        "display_name": "Resting Heart Rate",
        "unit": "bpm",
        "category": "recovery",
        "data_type": "integer",
        "min_value": 30,
        "max_value": 100,
        "allowed_sources": ["manual", "device"],
        "recalc_targets": None,
        "sort_order": 6,
    },
    {
        "key": "hrv",
        "display_name": "Heart Rate Variability",
        "unit": "ms",
        "category": "recovery",
        "data_type": "integer",
        "min_value": 10,
        "max_value": 200,
        "allowed_sources": ["manual", "device"],
        "recalc_targets": None,
        "sort_order": 7,
    },
]


def upgrade() -> None:
    # Create metric_types table
    op.create_table(
        "metric_types",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("key", sa.String(50), unique=True, nullable=False),
        sa.Column("display_name", sa.String(100), nullable=False),
        sa.Column("unit", sa.String(20), nullable=True),
        sa.Column("category", sa.String(50), nullable=False),
        sa.Column("data_type", sa.String(20), nullable=False),
        sa.Column("min_value", sa.Numeric(), nullable=True),
        sa.Column("max_value", sa.Numeric(), nullable=True),
        sa.Column("allowed_sources", postgresql.ARRAY(sa.Text()), nullable=True),
        sa.Column("recalc_targets", postgresql.ARRAY(sa.Text()), nullable=True),
        sa.Column("sort_order", sa.Integer(), server_default="0"),
    )

    # Create metric_entries table
    op.create_table(
        "metric_entries",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column(
            "user_id",
            sa.BigInteger(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "metric_type_id",
            sa.Integer(),
            sa.ForeignKey("metric_types.id"),
            nullable=False,
        ),
        sa.Column("effective_date", sa.Date(), nullable=False),
        sa.Column("value", sa.Numeric(), nullable=False),
        sa.Column("source", sa.String(20), nullable=False),
        sa.Column("source_detail", sa.String(50), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()")),
        sa.UniqueConstraint("user_id", "metric_type_id", "effective_date", name="uq_metric_user_type_date"),
        sa.CheckConstraint("source IN ('manual', 'calculated', 'device')", name="ck_metric_source"),
    )

    # Create indexes for efficient queries
    op.create_index(
        "idx_metric_entries_user_type",
        "metric_entries",
        ["user_id", "metric_type_id"],
    )
    op.create_index(
        "idx_metric_entries_effective",
        "metric_entries",
        ["user_id", "effective_date"],
    )

    # Seed initial metric types
    metric_types_table = sa.table(
        "metric_types",
        sa.column("key", sa.String),
        sa.column("display_name", sa.String),
        sa.column("unit", sa.String),
        sa.column("category", sa.String),
        sa.column("data_type", sa.String),
        sa.column("min_value", sa.Numeric),
        sa.column("max_value", sa.Numeric),
        sa.column("allowed_sources", postgresql.ARRAY(sa.Text)),
        sa.column("recalc_targets", postgresql.ARRAY(sa.Text)),
        sa.column("sort_order", sa.Integer),
    )

    op.bulk_insert(metric_types_table, METRIC_TYPES)


def downgrade() -> None:
    op.drop_index("idx_metric_entries_effective", table_name="metric_entries")
    op.drop_index("idx_metric_entries_user_type", table_name="metric_entries")
    op.drop_table("metric_entries")
    op.drop_table("metric_types")
