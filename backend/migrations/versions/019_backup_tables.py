"""Add backup configuration and history tables.

Implements storage for the backup feature (#581, #582):
- backup_config: Singleton configuration for restic backups
- backup_history: Log of backup operations with metadata

Revision ID: 019
Revises: 018
Create Date: 2026-08-22

"""

import sqlalchemy as sa
from alembic import op

revision = "019"
down_revision = "018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Backup configuration - singleton table (one row)
    op.create_table(
        "backup_config",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("repository_path", sa.String(500), nullable=False, server_default="/backups"),
        sa.Column("encrypted_password", sa.LargeBinary(), nullable=True),
        # Schedule: hour of day (0-23) like sync_hour, null = manual only
        sa.Column("schedule_hour", sa.Integer(), nullable=True),
        # Retention policy
        sa.Column("retention_keep_daily", sa.Integer(), nullable=False, server_default="7"),
        sa.Column("retention_keep_weekly", sa.Integer(), nullable=False, server_default="4"),
        sa.Column("retention_keep_monthly", sa.Integer(), nullable=False, server_default="3"),
        # Options
        sa.Column("exclude_raw_fit", sa.Boolean(), nullable=False, server_default="false"),
        # Timestamps
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        # Singleton constraint - only one row allowed
        sa.CheckConstraint("id = 1", name="backup_config_singleton"),
    )

    # Backup history - log of backup operations
    op.create_table(
        "backup_history",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        # Restic snapshot ID (short form, e.g. "a1b2c3d4")
        sa.Column("snapshot_id", sa.String(64), nullable=True, index=True),
        # Trigger type: scheduled, manual
        sa.Column("trigger_type", sa.String(20), nullable=False),
        # Status: running, completed, failed
        sa.Column("status", sa.String(20), nullable=False),
        # Timing
        sa.Column("started_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("duration_seconds", sa.Float(), nullable=True),
        # Backup metadata (from restic JSON output)
        sa.Column("files_new", sa.Integer(), nullable=True),
        sa.Column("files_changed", sa.Integer(), nullable=True),
        sa.Column("files_unmodified", sa.Integer(), nullable=True),
        sa.Column("bytes_added", sa.BigInteger(), nullable=True),
        sa.Column("bytes_total", sa.BigInteger(), nullable=True),
        # Database metadata
        sa.Column("db_migration_version", sa.String(50), nullable=True),
        # Error info
        sa.Column("error_message", sa.Text(), nullable=True),
    )

    op.create_index("ix_backup_history_started_at", "backup_history", ["started_at"])


def downgrade() -> None:
    op.drop_index("ix_backup_history_started_at")
    op.drop_table("backup_history")
    op.drop_table("backup_config")
