"""Add race_plans table.

Database storage for generated race plans with rider/bike parameters,
optimization settings, results, and per-segment power targets.

Revision ID: 013_race_plans_table
Revises: 012_race_courses_table
Create Date: 2026-08-21

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "013_race_plans_table"
down_revision: str | None = "012_race_courses_table"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "race_plans",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("course_id", sa.BigInteger, sa.ForeignKey("race_courses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("bike_id", sa.BigInteger, sa.ForeignKey("bikes.id", ondelete="SET NULL"), nullable=True),
        # Plan metadata
        sa.Column("name", sa.String(200), nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.text("now()")),
        # Rider parameters used
        sa.Column("rider_weight_kg", sa.Numeric(5, 2), nullable=False),
        sa.Column("ftp_watts", sa.Integer, nullable=False),
        sa.Column("cp_watts", sa.Integer, nullable=True),
        sa.Column("w_prime_joules", sa.Integer, nullable=True),
        # Bike parameters used
        sa.Column("bike_weight_kg", sa.Numeric(5, 2), nullable=True),
        sa.Column("cda", sa.Numeric(4, 3), nullable=False),
        sa.Column("crr", sa.Numeric(5, 4), nullable=False),
        # Plan configuration
        sa.Column("target_intensity", sa.Numeric(3, 2), nullable=True),  # e.g., 0.85 for 85% IF
        sa.Column("optimization_method", sa.String(20), nullable=True),  # heuristic, optimized
        # Results
        sa.Column("total_time_s", sa.Float, nullable=False),
        sa.Column("total_distance_m", sa.Float, nullable=False),
        sa.Column("avg_power_w", sa.Float, nullable=False),
        sa.Column("normalized_power_w", sa.Float, nullable=True),
        sa.Column("intensity_factor", sa.Numeric(3, 2), nullable=True),
        # Segment targets (JSONB)
        # [{segment_idx, power_w, time_s, speed_mps}, ...]
        sa.Column("segment_targets", sa.dialects.postgresql.JSONB, nullable=False),
        # W'bal prediction
        sa.Column("wbal_min", sa.Float, nullable=True),
        sa.Column("wbal_min_distance_m", sa.Float, nullable=True),
        # Constraints
        sa.CheckConstraint(
            "optimization_method IN ('heuristic', 'optimized') OR optimization_method IS NULL",
            name="valid_optimization_method",
        ),
    )

    # Indices
    op.create_index("idx_race_plans_user", "race_plans", ["user_id"])
    op.create_index("idx_race_plans_course", "race_plans", ["course_id"])
    op.create_index("idx_race_plans_created", "race_plans", ["created_at"], postgresql_ops={"created_at": "DESC"})


def downgrade() -> None:
    op.drop_index("idx_race_plans_created", table_name="race_plans")
    op.drop_index("idx_race_plans_course", table_name="race_plans")
    op.drop_index("idx_race_plans_user", table_name="race_plans")
    op.drop_table("race_plans")
