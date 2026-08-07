"""Backfill first threshold to sentinel date 2000-01-01.

For users who have exactly one threshold entry (i.e. their first ever FTP),
move its effective_date to 2000-01-01 so that all historical activities
predate the threshold and metrics can be computed for them.

Users with more than one threshold entry are left untouched — their history
is intentional and changing it could corrupt relative ordering.

Revision ID: 006
Revises: 005
Create Date: 2026-08-07
"""

from alembic import op


# revision identifiers, used by Alembic.
revision = "006_first_threshold_sentinel_date"
down_revision = "005_threshold_unique_date"
branch_labels = None
depends_on = None

SENTINEL = "2000-01-01"


def upgrade() -> None:
    """Move the sole threshold row for single-threshold users to 2000-01-01."""
    # Only update users who have exactly one threshold row.
    # The unique constraint on (user_id, effective_date) from migration 005
    # guarantees no collision — a user with one row cannot already have a
    # row on 2000-01-01 unless that row IS their only row (idempotent).
    op.execute(f"""
        UPDATE threshold_history
        SET effective_date = '{SENTINEL}'
        WHERE user_id IN (
            SELECT user_id
            FROM threshold_history
            GROUP BY user_id
            HAVING COUNT(*) = 1
        )
        AND effective_date != '{SENTINEL}'
    """)


def downgrade() -> None:
    """Cannot reverse: we don't know what the original date was."""
    pass
