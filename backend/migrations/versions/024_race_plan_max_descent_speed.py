"""Add max_descent_speed_mps to race_plans table.

Revision ID: 024
Revises: 023
Create Date: 2026-08-23
"""

import sqlalchemy as sa
from alembic import op

revision = "024"
down_revision = "023"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "race_plans",
        sa.Column("max_descent_speed_mps", sa.Float(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("race_plans", "max_descent_speed_mps")
