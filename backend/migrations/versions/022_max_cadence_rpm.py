"""Add max_cadence_rpm to activities table.

Revision ID: 022
Revises: 021
Create Date: 2026-08-23

"""

import sqlalchemy as sa
from alembic import op

revision = "022"
down_revision = "021"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("activities", sa.Column("max_cadence_rpm", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("activities", "max_cadence_rpm")
