"""Add direction_bearing_75 column for dual-bearing direction detection.

The existing direction_bearing column captures bearing at 25% of route distance.
This new column captures bearing at 75% of route distance, enabling detection
of opposite-direction loops where both directions initially head the same way.

Revision ID: 009_direction_bearing_75
Revises: 008_ride_events
Create Date: 2026-08-16

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "009_direction_bearing_75"
down_revision: str | None = "008_ride_events"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "activities",
        sa.Column("direction_bearing_75", sa.SmallInteger(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("activities", "direction_bearing_75")
