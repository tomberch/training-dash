"""Create recalculation_jobs table.

One row per user (unique constraint on user_id). Upserted on each run.
Tracks status of async metric recalculation jobs (pending → running →
completed | failed).

Revision ID: 007
Revises: 006
Create Date: 2026-08-07
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "007_recalculation_jobs"
down_revision = "006_threshold_sentinel"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create the recalculation_jobs table."""
    op.create_table(
        "recalculation_jobs",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column(
            "user_id",
            sa.BigInteger(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column(
            "started_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("activities_updated", sa.Integer(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    """Drop the recalculation_jobs table."""
    op.drop_table("recalculation_jobs")
