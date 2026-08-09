"""Drop threshold_history table.

Data has been migrated to metric_entries in migration 011.

Revision ID: 012_drop_threshold_history
Revises: 011_migrate_threshold_to_metrics
Create Date: 2026-08-08
"""

import sqlalchemy as sa
from alembic import op

revision = "012_drop_threshold_history"
down_revision = "011_migrate_threshold_to_metrics"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_table("threshold_history")


def downgrade() -> None:
    # Recreate threshold_history table
    op.create_table(
        "threshold_history",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column(
            "user_id",
            sa.BigInteger(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("effective_date", sa.Date(), nullable=False),
        sa.Column("ftp_watts", sa.Integer(), nullable=True),
        sa.Column("lthr_bpm", sa.Integer(), nullable=True),
        sa.Column("hrmax_bpm", sa.Integer(), nullable=True),
        sa.Column("is_auto_calculated", sa.Boolean(), default=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index(
        "ix_threshold_history_user_effective",
        "threshold_history",
        ["user_id", "effective_date"],
    )
    op.create_unique_constraint(
        "uq_threshold_user_date",
        "threshold_history",
        ["user_id", "effective_date"],
    )

    # Migrate data back from metric_entries
    # This is a best-effort reconstruction - group by user_id and effective_date
    op.execute("""
        INSERT INTO threshold_history (user_id, effective_date, ftp_watts, lthr_bpm, hrmax_bpm, is_auto_calculated, created_at)
        SELECT 
            me.user_id,
            me.effective_date,
            MAX(CASE WHEN mt.key = 'ftp' THEN me.value::integer END) as ftp_watts,
            MAX(CASE WHEN mt.key = 'lthr' THEN me.value::integer END) as lthr_bpm,
            MAX(CASE WHEN mt.key = 'hrmax' THEN me.value::integer END) as hrmax_bpm,
            bool_or(me.source = 'calculated') as is_auto_calculated,
            MIN(me.created_at) as created_at
        FROM metric_entries me
        JOIN metric_types mt ON me.metric_type_id = mt.id
        WHERE mt.key IN ('ftp', 'lthr', 'hrmax')
        GROUP BY me.user_id, me.effective_date
        ON CONFLICT DO NOTHING
    """)
