"""Add ride_type columns to race_plans table.

Stores ride type preset name and resolved values for descent aggressiveness
and stop percentage. Enables different time predictions for race vs training.

Revision ID: 026
Revises: 025
Create Date: 2026-08-25
"""

import sqlalchemy as sa
from alembic import op

revision = "026"
down_revision = "025"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "race_plans",
        sa.Column("ride_type", sa.String(20), nullable=True),
    )
    op.add_column(
        "race_plans",
        sa.Column("descent_aggressiveness", sa.Integer(), nullable=True),
    )
    op.add_column(
        "race_plans",
        sa.Column("stop_pct", sa.Float(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("race_plans", "stop_pct")
    op.drop_column("race_plans", "descent_aggressiveness")
    op.drop_column("race_plans", "ride_type")
