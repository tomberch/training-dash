"""Backup management API endpoints (admin only).

Backup is enabled when BACKUP_HOST_PATH environment variable is set.
Configuration (schedule, retention) can be updated via PUT.
"""

import os
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

from trainingdash.auth import AdminUser
from trainingdash.dependencies import BackupRepoD

router = APIRouter(prefix="/api/admin/backup", tags=["admin-backup"])

# Container path where backups are stored (must match volume mount)
BACKUP_CONTAINER_PATH = "/data/backups"


def get_host_path() -> str | None:
    """Get the host backup path from environment. None means backup is disabled."""
    path = os.environ.get("BACKUP_HOST_PATH")
    return path if path else None  # Treat empty string as not set


def is_backup_path_valid() -> bool:
    """Check if the backup container path exists and is writable."""
    path = Path(BACKUP_CONTAINER_PATH)
    if not path.exists():
        return False
    if not path.is_dir():
        return False
    # Check if writable by attempting to create a test file
    test_file = path / ".write_test"
    try:
        test_file.touch()
        test_file.unlink()
        return True
    except (OSError, PermissionError):
        return False


def get_path_error() -> str | None:
    """Get a human-readable error message if path is invalid."""
    path = Path(BACKUP_CONTAINER_PATH)
    if not path.exists():
        return "Path does not exist or is not mounted"
    if not path.is_dir():
        return "Path exists but is not a directory"
    # Check if writable
    test_file = path / ".write_test"
    try:
        test_file.touch()
        test_file.unlink()
        return None
    except PermissionError:
        return "Path exists but is not writable (permission denied)"
    except OSError as e:
        return f"Path exists but is not writable ({e})"


def is_backup_configured() -> bool:
    """Check if backup is configured via environment."""
    return get_host_path() is not None


# --- Request/Response Models ---


class BackupConfigResponse(BaseModel):
    """Response model for backup configuration."""

    configured: bool  # True if BACKUP_HOST_PATH is set
    host_path: str | None  # The actual host path where backups go
    path_valid: bool  # True if path exists and is writable
    path_error: str | None  # Error message if path is invalid
    schedule_hour: int | None
    retention_keep_daily: int
    retention_keep_weekly: int
    retention_keep_monthly: int
    has_password: bool
    updated_at: datetime | None = None


class BackupConfigUpdate(BaseModel):
    """Request model for updating backup schedule/retention."""

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

    configured: bool
    is_running: bool
    latest_backup: LatestBackupInfo | None = None


# --- Endpoints ---


@router.get("/config", response_model=BackupConfigResponse)
async def get_backup_config(
    admin: AdminUser,
    backup_repo: BackupRepoD,
):
    """
    Get current backup configuration.

    Backup is enabled when BACKUP_HOST_PATH environment variable is set.
    """
    host_path = get_host_path()
    configured = host_path is not None
    path_valid = is_backup_path_valid() if configured else False
    path_error = get_path_error() if configured else None

    # Get stored config for schedule/retention (may not exist yet)
    config = await backup_repo.get_config()

    return BackupConfigResponse(
        configured=configured,
        host_path=host_path,
        path_valid=path_valid,
        path_error=path_error,
        schedule_hour=config.schedule_hour if config else None,
        retention_keep_daily=config.retention_keep_daily if config else 7,
        retention_keep_weekly=config.retention_keep_weekly if config else 4,
        retention_keep_monthly=config.retention_keep_monthly if config else 3,
        has_password=config.encrypted_password is not None if config else False,
        updated_at=config.updated_at if config else None,
    )


@router.put("/config", response_model=BackupConfigResponse)
async def update_backup_config(
    admin: AdminUser,
    backup_repo: BackupRepoD,
    request: BackupConfigUpdate,
):
    """
    Update backup schedule and retention settings.

    Backup must be configured via BACKUP_HOST_PATH environment variable.
    """
    host_path = get_host_path()
    if not host_path:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Backup not configured. Set BACKUP_HOST_PATH environment variable.",
        )

    config = await backup_repo.upsert_config(
        enabled=True,  # Always enabled when host_path is set
        repository_path=BACKUP_CONTAINER_PATH,
        schedule_hour=request.schedule_hour,
        retention_keep_daily=request.retention_keep_daily,
        retention_keep_weekly=request.retention_keep_weekly,
        retention_keep_monthly=request.retention_keep_monthly,
    )

    return BackupConfigResponse(
        configured=True,
        host_path=host_path,
        path_valid=is_backup_path_valid(),
        path_error=get_path_error(),
        schedule_hour=config.schedule_hour,
        retention_keep_daily=config.retention_keep_daily,
        retention_keep_weekly=config.retention_keep_weekly,
        retention_keep_monthly=config.retention_keep_monthly,
        has_password=config.encrypted_password is not None,
        updated_at=config.updated_at,
    )


@router.get("/history", response_model=BackupHistoryResponse)
async def get_backup_history(
    admin: AdminUser,
    backup_repo: BackupRepoD,
    limit: int = Query(20, ge=1, le=100, description="Max entries to return"),
):
    """Get backup history, most recent first."""
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
):
    """
    Trigger a manual backup.

    Enqueues a backup job on the worker. The backup runs asynchronously;
    check /status or /history for progress.
    """
    if not is_backup_configured():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Backup not configured. Set BACKUP_HOST_PATH environment variable.",
        )

    if not is_backup_path_valid():
        error = get_path_error() or "Unknown error"
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Backup path is invalid: {error}",
        )

    if await backup_repo.is_backup_running():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A backup is already running",
        )

    # Ensure config exists in DB (create with defaults if needed)
    config = await backup_repo.get_config()
    if config is None:
        await backup_repo.upsert_config(
            enabled=True,
            repository_path=BACKUP_CONTAINER_PATH,
            schedule_hour=None,
            retention_keep_daily=7,
            retention_keep_weekly=4,
            retention_keep_monthly=3,
        )

    from trainingdash.jobs import enqueue_backup_job

    job_key = await enqueue_backup_job()
    if job_key is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Job queue not available",
        )

    return TriggerBackupResponse(
        message="Backup job enqueued",
        history_id=None,
    )


@router.get("/status", response_model=BackupStatusResponse)
async def get_backup_status(
    admin: AdminUser,
    backup_repo: BackupRepoD,
):
    """
    Get current backup status.

    Returns whether backup is configured, running, and latest backup info.
    """
    configured = is_backup_configured()
    is_running = await backup_repo.is_backup_running() if configured else False
    latest = await backup_repo.get_latest_completed() if configured else None

    return BackupStatusResponse(
        configured=configured,
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
