"""Add last_synced_at to xert_credentials and garmin_credentials.

Enables incremental sync: subsequent syncs use last_synced_at - 4h as the
start date instead of always re-querying the full 90-day window.

Revision ID: 002_add_last_synced_at
Revises: 001_initial
Create Date: 2026-08-06

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "002_add_last_synced_at"
down_revision: Union[str, None] = "001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "xert_credentials",
        sa.Column("last_synced_at", sa.DateTime(), nullable=True),
    )
    op.add_column(
        "garmin_credentials",
        sa.Column("last_synced_at", sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("garmin_credentials", "last_synced_at")
    op.drop_column("xert_credentials", "last_synced_at")
