"""Add bikes table and bike_id to activities.

Supports gear management with per-bike CdA/Crr calibration.

Bike types: road, tt, gravel, mtb, ebike
CdA/Crr sources: default, manual, calibrated

Revision ID: 011_bikes_table
Revises: 010_activity_type
Create Date: 2026-08-20

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "011_bikes_table"
down_revision: str | None = "010_activity_type"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Create bikes table
    op.create_table(
        "bikes",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("bike_type", sa.String(20), nullable=False),
        sa.Column("model_year", sa.Integer, nullable=True),
        sa.Column("weight_kg", sa.Numeric(5, 2), nullable=True),
        sa.Column("photo_path", sa.String(500), nullable=True),
        sa.Column("total_distance_m", sa.Float, nullable=False, server_default="0"),
        sa.Column("cda", sa.Numeric(4, 3), nullable=True),
        sa.Column("crr", sa.Numeric(5, 4), nullable=True),
        sa.Column("cda_source", sa.String(20), nullable=True),
        sa.Column("crr_source", sa.String(20), nullable=True),
        sa.Column("calibrated_at", sa.DateTime, nullable=True),
        sa.Column("is_default", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("retired_at", sa.DateTime, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime, nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint(
            "bike_type IN ('road', 'tt', 'gravel', 'mtb', 'ebike')",
            name="valid_bike_type",
        ),
        sa.CheckConstraint(
            "cda_source IN ('default', 'manual', 'calibrated') OR cda_source IS NULL",
            name="valid_cda_source",
        ),
        sa.CheckConstraint(
            "crr_source IN ('default', 'manual', 'calibrated') OR crr_source IS NULL",
            name="valid_crr_source",
        ),
    )

    # Indices for bikes table
    op.create_index("idx_bikes_user", "bikes", ["user_id"])
    # Unique partial index: only one default bike per user (among non-retired bikes)
    op.execute(
        "CREATE UNIQUE INDEX idx_bikes_default ON bikes (user_id) "
        "WHERE is_default = TRUE AND retired_at IS NULL"
    )

    # Add bike_id to activities
    op.add_column(
        "activities",
        sa.Column("bike_id", sa.BigInteger, sa.ForeignKey("bikes.id", ondelete="SET NULL"), nullable=True),
    )
    op.create_index("idx_activities_bike", "activities", ["bike_id"])


def downgrade() -> None:
    # Remove bike_id from activities
    op.drop_index("idx_activities_bike", table_name="activities")
    op.drop_column("activities", "bike_id")

    # Drop bikes table (indices dropped automatically)
    op.drop_index("idx_bikes_default", table_name="bikes")
    op.drop_index("idx_bikes_user", table_name="bikes")
    op.drop_table("bikes")
