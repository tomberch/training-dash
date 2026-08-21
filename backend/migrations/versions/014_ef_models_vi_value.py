"""Add vi_value column to ef_models table

Revision ID: 014_ef_models_vi_value
Revises: 013_race_plans_table
Create Date: 2026-08-21
"""

import sqlalchemy as sa
from alembic import op

revision = "014_ef_models_vi_value"
down_revision = "013_race_plans_table"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "ef_models",
        sa.Column("vi_value", sa.Numeric(5, 4), nullable=False, server_default="1.25"),
    )
    # Remove the server default after adding the column (it's for existing rows)
    op.alter_column("ef_models", "vi_value", server_default=None)


def downgrade() -> None:
    op.drop_column("ef_models", "vi_value")
