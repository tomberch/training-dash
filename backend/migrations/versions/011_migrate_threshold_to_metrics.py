"""Migrate threshold_history data to metric_entries.

Splits each threshold_history row into separate metric_entries for ftp, lthr, hrmax.

Revision ID: 011_migrate_threshold_to_metrics
Revises: 010_drop_zone_tables
Create Date: 2026-08-08
"""

from alembic import op

revision = "011_migrate_threshold_to_metrics"
down_revision = "010_drop_zone_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Migrate FTP values
    op.execute("""
        INSERT INTO metric_entries (user_id, metric_type_id, effective_date, value, source, source_detail, created_at, updated_at)
        SELECT 
            th.user_id,
            (SELECT id FROM metric_types WHERE key = 'ftp'),
            th.effective_date,
            th.ftp_watts,
            CASE WHEN th.is_auto_calculated THEN 'calculated' ELSE 'manual' END,
            CASE WHEN th.is_auto_calculated THEN 'migrated_auto' ELSE 'migrated_manual' END,
            th.created_at,
            th.created_at
        FROM threshold_history th
        WHERE th.ftp_watts IS NOT NULL
        ON CONFLICT (user_id, metric_type_id, effective_date) DO NOTHING
    """)

    # Migrate LTHR values
    op.execute("""
        INSERT INTO metric_entries (user_id, metric_type_id, effective_date, value, source, source_detail, created_at, updated_at)
        SELECT 
            th.user_id,
            (SELECT id FROM metric_types WHERE key = 'lthr'),
            th.effective_date,
            th.lthr_bpm,
            CASE WHEN th.is_auto_calculated THEN 'calculated' ELSE 'manual' END,
            CASE WHEN th.is_auto_calculated THEN 'migrated_auto' ELSE 'migrated_manual' END,
            th.created_at,
            th.created_at
        FROM threshold_history th
        WHERE th.lthr_bpm IS NOT NULL
        ON CONFLICT (user_id, metric_type_id, effective_date) DO NOTHING
    """)

    # Migrate HRmax values
    op.execute("""
        INSERT INTO metric_entries (user_id, metric_type_id, effective_date, value, source, source_detail, created_at, updated_at)
        SELECT 
            th.user_id,
            (SELECT id FROM metric_types WHERE key = 'hrmax'),
            th.effective_date,
            th.hrmax_bpm,
            CASE WHEN th.is_auto_calculated THEN 'calculated' ELSE 'manual' END,
            CASE WHEN th.is_auto_calculated THEN 'migrated_auto' ELSE 'migrated_manual' END,
            th.created_at,
            th.created_at
        FROM threshold_history th
        WHERE th.hrmax_bpm IS NOT NULL
        ON CONFLICT (user_id, metric_type_id, effective_date) DO NOTHING
    """)


def downgrade() -> None:
    # Remove migrated entries (identified by source_detail)
    op.execute("""
        DELETE FROM metric_entries
        WHERE source_detail IN ('migrated_auto', 'migrated_manual')
    """)
