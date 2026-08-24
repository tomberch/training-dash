"""Add pacing_coefficients table for personalized pacing models.

Stores per-user and optionally per-bike pacing model coefficients learned
from actual ride data. Enables personalized power predictions based on
individual riding style.

Parameters stored:
- Climb: grade_power_intercept, grade_power_slope
- Descent: max_descent_speed_mps, descent_power_multiplier, curvature_speed_coefficient

Fallback chain: bike-specific → user default (bike_id=NULL) → global defaults

Revision ID: 025
Revises: 024
Create Date: 2026-08-24

"""

import sqlalchemy as sa
from alembic import op

revision = "025"
down_revision = "024"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "pacing_coefficients",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "bike_id",
            sa.BigInteger(),
            sa.ForeignKey("bikes.id", ondelete="CASCADE"),
            nullable=True,
            comment="NULL = user default (applies to all bikes without specific coefficients)",
        ),
        # Climb coefficients
        sa.Column(
            "grade_power_intercept",
            sa.Numeric(4, 3),
            nullable=False,
            server_default="1.100",
            comment="Base power multiplier at 0% grade",
        ),
        sa.Column(
            "grade_power_slope",
            sa.Numeric(5, 4),
            nullable=False,
            server_default="0.0350",
            comment="Power multiplier increase per 1% grade",
        ),
        # Descent coefficients
        sa.Column(
            "max_descent_speed_mps",
            sa.Numeric(4, 1),
            nullable=False,
            server_default="18.0",
            comment="Absolute speed limit on descents (m/s)",
        ),
        sa.Column(
            "descent_power_multiplier",
            sa.Numeric(3, 2),
            nullable=False,
            server_default="0.50",
            comment="Power multiplier on descents (grade < -3%)",
        ),
        sa.Column(
            "curvature_speed_coefficient",
            sa.Numeric(6, 1),
            nullable=False,
            server_default="-68.0",
            comment="Speed reduction per unit curvature (m/s per 1/m)",
        ),
        # Learning metadata
        sa.Column(
            "climb_sample_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
            comment="Number of climb data points used for regression",
        ),
        sa.Column(
            "descent_sample_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
            comment="Number of descent data points used for regression",
        ),
        sa.Column(
            "activity_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
            comment="Number of activities contributing to coefficients",
        ),
        sa.Column(
            "last_calibrated_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="When coefficients were last updated",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        # Unique constraint: one row per user/bike combination
        sa.UniqueConstraint("user_id", "bike_id", name="uq_pacing_coefficients_user_bike"),
    )

    # Index for fast lookup by user
    op.create_index(
        "ix_pacing_coefficients_user_id",
        "pacing_coefficients",
        ["user_id"],
    )

    # Partial index for user defaults (bike_id IS NULL)
    op.create_index(
        "ix_pacing_coefficients_user_default",
        "pacing_coefficients",
        ["user_id"],
        unique=True,
        postgresql_where=sa.text("bike_id IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_pacing_coefficients_user_default")
    op.drop_index("ix_pacing_coefficients_user_id")
    op.drop_table("pacing_coefficients")
