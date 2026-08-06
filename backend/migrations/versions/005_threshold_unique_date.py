"""Add unique constraint on threshold_history (user_id, effective_date).

Revision ID: 005
Revises: 004
Create Date: 2025-01-10
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "005_threshold_unique_date"
down_revision = "004_routes_fk_set_null"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add unique constraint after deduplicating existing rows."""
    # First, deduplicate: keep only the row with the highest ID for each (user_id, effective_date)
    op.execute("""
        DELETE FROM threshold_history th1
        USING threshold_history th2
        WHERE th1.user_id = th2.user_id
          AND th1.effective_date = th2.effective_date
          AND th1.id < th2.id
    """)

    # Now add the unique constraint
    op.create_unique_constraint(
        "uq_threshold_user_date",
        "threshold_history",
        ["user_id", "effective_date"],
    )


def downgrade() -> None:
    """Remove the unique constraint."""
    op.drop_constraint("uq_threshold_user_date", "threshold_history", type_="unique")
