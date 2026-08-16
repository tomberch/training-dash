"""Add sync_enabled column to credentials tables.

Revision ID: 007
Revises: 006
Create Date: 2026-08-15

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "007_sync_enabled"
down_revision = "006_map_tile_style"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add sync_enabled to xert_credentials with default True
    op.add_column(
        "xert_credentials",
        sa.Column("sync_enabled", sa.Boolean(), server_default="true", nullable=False),
    )

    # Add sync_enabled to garmin_credentials with default True
    op.add_column(
        "garmin_credentials",
        sa.Column("sync_enabled", sa.Boolean(), server_default="true", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("garmin_credentials", "sync_enabled")
    op.drop_column("xert_credentials", "sync_enabled")
