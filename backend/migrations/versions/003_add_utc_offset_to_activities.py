"""Add utc_offset_minutes to activities table.

Stores the UTC offset (in minutes) at the time and place the activity was
recorded, derived from the FIT file's local_timestamp field. NULL means
unknown — historical activities and devices that omit local_timestamp fall
back to the viewer's browser timezone for display.

Revision ID: 003_add_utc_offset_to_activities
Revises: 002_add_last_synced_at
Create Date: 2026-08-06

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "003_add_utc_offset_to_activities"
down_revision: Union[str, None] = "002_add_last_synced_at"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "activities",
        sa.Column("utc_offset_minutes", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("activities", "utc_offset_minutes")
