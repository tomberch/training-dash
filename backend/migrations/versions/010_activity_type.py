"""Add activity_type column for distinguishing ride types.

Supports: road, gravel, mtb, virtual, indoor, commute, other.
Null means unclassified (legacy activities).

Used for:
- Filtering activity list by type
- Excluding indoor/virtual from CdA/Crr calibration
- Analytics segmentation

Revision ID: 010_activity_type
Revises: 009_direction_bearing_75
Create Date: 2026-08-20

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "010_activity_type"
down_revision: str | None = "009_direction_bearing_75"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "activities",
        sa.Column("activity_type", sa.String(20), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("activities", "activity_type")
