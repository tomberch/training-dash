"""Add height_cm, gender, and zone percentages to users table.

Profile fields for body metrics and custom zone definitions.

Revision ID: 009_user_profile_zones
Revises: 008_metric_tables
Create Date: 2026-08-08
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "009_user_profile_zones"
down_revision = "008_metric_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add height_cm column with range constraint
    op.add_column(
        "users",
        sa.Column("height_cm", sa.Integer(), nullable=True),
    )
    op.create_check_constraint(
        "ck_users_height_cm_range",
        "users",
        "height_cm IS NULL OR (height_cm >= 100 AND height_cm <= 250)",
    )

    # Add gender column with value constraint
    op.add_column(
        "users",
        sa.Column("gender", sa.String(10), nullable=True),
    )
    op.create_check_constraint(
        "ck_users_gender_values",
        "users",
        "gender IS NULL OR gender IN ('male', 'female')",
    )

    # Add zone percentages as JSONB (null = use defaults)
    op.add_column(
        "users",
        sa.Column("power_zone_percentages", postgresql.JSONB(), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("hr_zone_percentages", postgresql.JSONB(), nullable=True),
    )


def downgrade() -> None:
    op.drop_constraint("ck_users_gender_values", "users", type_="check")
    op.drop_constraint("ck_users_height_cm_range", "users", type_="check")
    op.drop_column("users", "hr_zone_percentages")
    op.drop_column("users", "power_zone_percentages")
    op.drop_column("users", "gender")
    op.drop_column("users", "height_cm")
