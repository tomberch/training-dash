"""PostgreSQL implementation of BackupRepo."""

from datetime import UTC, datetime

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from trainingdash.repositories.postgres.models import BackupConfig, BackupHistory


class PostgresBackupRepo:
    """PostgreSQL implementation of BackupRepo."""

    def __init__(self, db: AsyncSession):
        self._db = db

    async def get_config(self) -> BackupConfig | None:
        """Get the backup configuration singleton."""
        result = await self._db.execute(select(BackupConfig).where(BackupConfig.id == 1))
        return result.scalar_one_or_none()

    async def save_config(self, config: BackupConfig) -> BackupConfig:
        """Save backup configuration (upsert singleton)."""
        # Ensure id=1 for singleton
        config.id = 1
        config.updated_at = datetime.now(UTC).replace(tzinfo=None)

        existing = await self.get_config()
        if existing:
            # Update existing
            existing.enabled = config.enabled
            existing.repository_path = config.repository_path
            existing.encrypted_password = config.encrypted_password
            existing.schedule_hour = config.schedule_hour
            existing.retention_keep_daily = config.retention_keep_daily
            existing.retention_keep_weekly = config.retention_keep_weekly
            existing.retention_keep_monthly = config.retention_keep_monthly
            existing.exclude_raw_fit = config.exclude_raw_fit
            existing.updated_at = config.updated_at
            await self._db.flush()
            await self._db.refresh(existing)
            return existing
        else:
            # Insert new
            self._db.add(config)
            await self._db.flush()
            await self._db.refresh(config)
            return config

    async def upsert_config(
        self,
        *,
        enabled: bool,
        repository_path: str,
        schedule_hour: int | None,
        retention_keep_daily: int,
        retention_keep_weekly: int,
        retention_keep_monthly: int,
    ) -> BackupConfig:
        """Create or update backup configuration from primitive values."""
        existing = await self.get_config()
        if existing:
            existing.enabled = enabled
            existing.repository_path = repository_path
            existing.schedule_hour = schedule_hour
            existing.retention_keep_daily = retention_keep_daily
            existing.retention_keep_weekly = retention_keep_weekly
            existing.retention_keep_monthly = retention_keep_monthly
            existing.updated_at = datetime.now(UTC).replace(tzinfo=None)
            await self._db.flush()
            await self._db.refresh(existing)
            return existing
        else:
            config = BackupConfig(
                id=1,
                enabled=enabled,
                repository_path=repository_path,
                schedule_hour=schedule_hour,
                retention_keep_daily=retention_keep_daily,
                retention_keep_weekly=retention_keep_weekly,
                retention_keep_monthly=retention_keep_monthly,
            )
            self._db.add(config)
            await self._db.flush()
            await self._db.refresh(config)
            return config

    async def create_history_entry(
        self,
        trigger_type: str,
        status: str,
        db_migration_version: str | None = None,
    ) -> BackupHistory:
        """Create a new backup history entry."""
        entry = BackupHistory(
            trigger_type=trigger_type,
            status=status,
            db_migration_version=db_migration_version,
            started_at=datetime.now(UTC).replace(tzinfo=None),
        )
        self._db.add(entry)
        await self._db.flush()
        await self._db.refresh(entry)
        return entry

    async def update_history_entry(
        self,
        entry_id: int,
        *,
        snapshot_id: str | None = None,
        status: str | None = None,
        completed_at: datetime | None = None,
        duration_seconds: float | None = None,
        files_new: int | None = None,
        files_changed: int | None = None,
        files_unmodified: int | None = None,
        bytes_added: int | None = None,
        bytes_total: int | None = None,
        error_message: str | None = None,
    ) -> BackupHistory | None:
        """Update a backup history entry."""
        result = await self._db.execute(select(BackupHistory).where(BackupHistory.id == entry_id))
        entry = result.scalar_one_or_none()
        if entry is None:
            return None

        if snapshot_id is not None:
            entry.snapshot_id = snapshot_id
        if status is not None:
            entry.status = status
        if completed_at is not None:
            entry.completed_at = completed_at
        if duration_seconds is not None:
            entry.duration_seconds = duration_seconds
        if files_new is not None:
            entry.files_new = files_new
        if files_changed is not None:
            entry.files_changed = files_changed
        if files_unmodified is not None:
            entry.files_unmodified = files_unmodified
        if bytes_added is not None:
            entry.bytes_added = bytes_added
        if bytes_total is not None:
            entry.bytes_total = bytes_total
        if error_message is not None:
            entry.error_message = error_message

        await self._db.flush()
        await self._db.refresh(entry)
        return entry

    async def get_history(self, limit: int = 20) -> list[BackupHistory]:
        """List backup history entries, most recent first."""
        result = await self._db.execute(select(BackupHistory).order_by(BackupHistory.started_at.desc()).limit(limit))
        return list(result.scalars().all())

    async def get_history_entry(self, entry_id: int) -> BackupHistory | None:
        """Get a specific backup history entry by ID."""
        result = await self._db.execute(select(BackupHistory).where(BackupHistory.id == entry_id))
        return result.scalar_one_or_none()

    async def get_latest_completed(self) -> BackupHistory | None:
        """Get the most recent completed backup."""
        result = await self._db.execute(
            select(BackupHistory)
            .where(BackupHistory.status == "completed")
            .order_by(BackupHistory.started_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def is_backup_running(self) -> bool:
        """Check if a backup is currently running."""
        result = await self._db.execute(select(BackupHistory.id).where(BackupHistory.status == "running").limit(1))
        return result.scalar_one_or_none() is not None

    async def get_migration_version(self) -> str | None:
        """Get current alembic migration version from database."""
        result = await self._db.execute(text("SELECT version_num FROM alembic_version LIMIT 1"))
        row = result.scalar_one_or_none()
        return row
