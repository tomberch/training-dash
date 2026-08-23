"""Add temperature_c column to records table.

Revision ID: 017
Revises: 016
Create Date: 2026-08-21

"""

import sqlalchemy as sa
from alembic import op

revision = "017"
down_revision = "016_time_targeted"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("records", sa.Column("temperature_c", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("records", "temperature_c")
