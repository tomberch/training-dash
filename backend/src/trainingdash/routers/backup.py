"""Backup management API endpoints (admin only).

Provides endpoints for:
- GET/PUT backup configuration
- GET backup history
- POST trigger manual backup
"""

import contextlib
import os
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, status
from pydantic import BaseModel, Field

from trainingdash.auth import AdminUser, DbSession
from trainingdash.dependencies import BackupRepoD
from trainingdash.use_cases import (
    BackupAlreadyRunningError,
    BackupNotConfiguredError,
    CreateBackup,
)

router = APIRouter(prefix="/api/admin/backup", tags=["admin-backup"])


# --- Request/Response Models ---


class BackupConfigResponse(BaseModel):
    """Response model for backup configuration."""

    enabled: bool
    repository_path: str
    schedule_hour: int | None
    retention_keep_daily: int
    retention_keep_weekly: int
    retention_keep_monthly: int
    has_password: bool
    created_at: datetime | None = None
    updated_at: datetime | None = None


class BackupConfigUpdate(BaseModel):
    """Request model for updating backup configuration."""

    enabled: bool = Field(description="Enable or disable automated backups")
    repository_path: str = Field(
        default="/data/backups",
        description="Path to restic repository",
    )
    schedule_hour: int | None = Field(
        default=None,
        ge=0,
        le=23,
        description="Hour of day (0-23 UTC) to run scheduled backup. Null for manual-only.",
    )
    retention_keep_daily: int = Field(
        default=7,
        ge=1,
        le=365,
        description="Number of daily backups to keep",
    )
    retention_keep_weekly: int = Field(
        default=4,
        ge=0,
        le=52,
        description="Number of weekly backups to keep",
    )
    retention_keep_monthly: int = Field(
        default=3,
        ge=0,
        le=24,
        description="Number of monthly backups to keep",
    )


class BackupHistoryEntry(BaseModel):
    """Single backup history entry."""

    id: int
    started_at: datetime
    completed_at: datetime | None
    trigger_type: str
    status: str
    snapshot_id: str | None
    duration_seconds: float | None
    files_new: int | None
    files_changed: int | None
    files_unmodified: int | None
    bytes_added: int | None
    bytes_total: int | None
    db_migration_version: str | None
    error_message: str | None


class BackupHistoryResponse(BaseModel):
    """Response model for backup history list."""

    entries: list[BackupHistoryEntry]
    total: int


class TriggerBackupResponse(BaseModel):
    """Response when triggering a manual backup."""

    message: str
    history_id: int | None = None


class LatestBackupInfo(BaseModel):
    """Info about the latest completed backup."""

    id: int
    completed_at: datetime | None
    status: str
    snapshot_id: str | None


class BackupStatusResponse(BaseModel):
    """Response for backup status check."""

    is_running: bool
    latest_backup: LatestBackupInfo | None = None


# --- Endpoints ---


@router.get("/config", response_model=BackupConfigResponse | None)
async def get_backup_config(
    admin: AdminUser,
    backup_repo: BackupRepoD,
):
    """
    Get current backup configuration.

    Returns null if backup has not been configured yet.
    """
    config = await backup_repo.get_config()
    if config is None:
        return None

    return BackupConfigResponse(
        enabled=config.enabled,
        repository_path=config.repository_path,
        schedule_hour=config.schedule_hour,
        retention_keep_daily=config.retention_keep_daily,
        retention_keep_weekly=config.retention_keep_weekly,
        retention_keep_monthly=config.retention_keep_monthly,
        has_password=config.encrypted_password is not None,
        created_at=config.created_at,
        updated_at=config.updated_at,
    )


@router.put("/config", response_model=BackupConfigResponse)
async def update_backup_config(
    admin: AdminUser,
    backup_repo: BackupRepoD,
    db: DbSession,
    request: BackupConfigUpdate,
):
    """
    Create or update backup configuration.

    On first save, a restic repository password will be auto-generated
    when the first backup runs.
    """
    config = await backup_repo.upsert_config(
        enabled=request.enabled,
        repository_path=request.repository_path,
        schedule_hour=request.schedule_hour,
        retention_keep_daily=request.retention_keep_daily,
        retention_keep_weekly=request.retention_keep_weekly,
        retention_keep_monthly=request.retention_keep_monthly,
    )

    return BackupConfigResponse(
        enabled=config.enabled,
        repository_path=config.repository_path,
        schedule_hour=config.schedule_hour,
        retention_keep_daily=config.retention_keep_daily,
        retention_keep_weekly=config.retention_keep_weekly,
        retention_keep_monthly=config.retention_keep_monthly,
        has_password=config.encrypted_password is not None,
        created_at=config.created_at,
        updated_at=config.updated_at,
    )


@router.get("/history", response_model=BackupHistoryResponse)
async def get_backup_history(
    admin: AdminUser,
    backup_repo: BackupRepoD,
    limit: int = Query(20, ge=1, le=100, description="Max entries to return"),
):
    """
    Get backup history, most recent first.
    """
    entries = await backup_repo.get_history(limit=limit)
    return BackupHistoryResponse(
        entries=[
            BackupHistoryEntry(
                id=e.id,
                started_at=e.started_at,
                completed_at=e.completed_at,
                trigger_type=e.trigger_type,
                status=e.status,
                snapshot_id=e.snapshot_id,
                duration_seconds=e.duration_seconds,
                files_new=e.files_new,
                files_changed=e.files_changed,
                files_unmodified=e.files_unmodified,
                bytes_added=e.bytes_added,
                bytes_total=e.bytes_total,
                db_migration_version=e.db_migration_version,
                error_message=e.error_message,
            )
            for e in entries
        ],
        total=len(entries),
    )


@router.post("/trigger", response_model=TriggerBackupResponse)
async def trigger_backup(
    admin: AdminUser,
    backup_repo: BackupRepoD,
    db: DbSession,
    background_tasks: BackgroundTasks,
):
    """
    Trigger a manual backup.

    The backup runs in the background. Check /history for status.
    """
    # Check preconditions synchronously
    if await backup_repo.is_backup_running():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A backup is already running",
        )

    config = await backup_repo.get_config()
    if config is None or not config.enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Backup is not configured or disabled",
        )

    # Get database URL from environment
    database_url = os.environ.get("DATABASE_URL", "")
    if not database_url:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="DATABASE_URL not configured",
        )

    # Create history entry synchronously so we can return the ID
    migration_version = await backup_repo.get_migration_version()
    history = await backup_repo.create_history_entry(
        trigger_type="manual",
        status="running",
        db_migration_version=migration_version,
    )
    await db.commit()

    # Run backup in background
    async def run_backup():
        from trainingdash.db import async_session_factory

        async with async_session_factory() as session:
            from trainingdash.repositories.postgres.backup_repo import PostgresBackupRepo

            repo = PostgresBackupRepo(session)
            use_case = CreateBackup(
                backup_repo=repo,
                database_url=database_url,
            )
            # Execute continues from existing history entry
            with contextlib.suppress(BackupAlreadyRunningError, BackupNotConfiguredError):
                await use_case.execute(trigger_type="manual")
            await session.commit()

    background_tasks.add_task(run_backup)

    return TriggerBackupResponse(
        message="Backup started",
        history_id=history.id,
    )


@router.get("/status", response_model=BackupStatusResponse)
async def get_backup_status(
    admin: AdminUser,
    backup_repo: BackupRepoD,
):
    """
    Get current backup status.

    Returns whether a backup is running and the latest completed backup info.
    """
    is_running = await backup_repo.is_backup_running()
    latest = await backup_repo.get_latest_completed()

    return BackupStatusResponse(
        is_running=is_running,
        latest_backup=(
            LatestBackupInfo(
                id=latest.id,
                completed_at=latest.completed_at,
                status=latest.status,
                snapshot_id=latest.snapshot_id,
            )
            if latest
            else None
        ),
    )
