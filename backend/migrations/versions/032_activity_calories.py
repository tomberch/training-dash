"""Add calories columns to activities table.

Stores calorie value and provenance (device-reported vs computed from power).
Part of #670 (Activity Calories feature).

Revision ID: 032
Revises: 031
Create Date: 2026-09-18
"""

import sqlalchemy as sa
from alembic import op

revision = "032"
down_revision = "031"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "activities",
        sa.Column("calories", sa.Integer(), nullable=True),
    )
    op.add_column(
        "activities",
        sa.Column("calories_source", sa.String(20), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("activities", "calories_source")
    op.drop_column("activities", "calories")
