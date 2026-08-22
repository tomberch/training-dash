"""Tests for backup API endpoint models and validation."""

import pytest
from pydantic import ValidationError

from trainingdash.routers.backup import (
    BackupConfigResponse,
    BackupConfigUpdate,
    BackupHistoryEntry,
    TriggerBackupResponse,
)


class TestBackupConfigUpdate:
    """Tests for BackupConfigUpdate request model."""

    def test_valid_config(self):
        """Should accept valid config values."""
        config = BackupConfigUpdate(
            schedule_hour=3,
            retention_keep_daily=7,
            retention_keep_weekly=4,
            retention_keep_monthly=3,
        )
        assert config.schedule_hour == 3
        assert config.retention_keep_daily == 7

    def test_default_values(self):
        """Should use defaults when not provided."""
        config = BackupConfigUpdate()
        assert config.schedule_hour is None
        assert config.retention_keep_daily == 7
        assert config.retention_keep_weekly == 4
        assert config.retention_keep_monthly == 3

    def test_retention_bounds(self):
        """Should reject out-of-bounds retention values."""
        with pytest.raises(ValidationError):
            BackupConfigUpdate(retention_keep_daily=0)

        with pytest.raises(ValidationError):
            BackupConfigUpdate(retention_keep_daily=400)

        with pytest.raises(ValidationError):
            BackupConfigUpdate(retention_keep_weekly=-1)


class TestBackupConfigResponse:
    """Tests for BackupConfigResponse response model."""

    def test_serialization(self):
        """Should serialize all fields correctly."""
        response = BackupConfigResponse(
            configured=True,
            host_path="/home/user/backups",
            path_valid=True,
            path_error=None,
            schedule_hour=3,
            retention_keep_daily=7,
            retention_keep_weekly=4,
            retention_keep_monthly=3,
            has_password=True,
        )
        data = response.model_dump()
        assert data["configured"] is True
        assert data["host_path"] == "/home/user/backups"
        assert data["path_valid"] is True
        assert data["has_password"] is True
        assert data["schedule_hour"] == 3
        assert data["updated_at"] is None

    def test_not_configured(self):
        """Should handle not configured state."""
        response = BackupConfigResponse(
            configured=False,
            host_path=None,
            path_valid=False,
            path_error=None,
            schedule_hour=None,
            retention_keep_daily=7,
            retention_keep_weekly=4,
            retention_keep_monthly=3,
            has_password=False,
        )
        assert response.configured is False
        assert response.host_path is None

    def test_invalid_path(self):
        """Should include path error when path is invalid."""
        response = BackupConfigResponse(
            configured=True,
            host_path="/nonexistent/path",
            path_valid=False,
            path_error="Path does not exist or is not mounted",
            schedule_hour=None,
            retention_keep_daily=7,
            retention_keep_weekly=4,
            retention_keep_monthly=3,
            has_password=False,
        )
        assert response.configured is True
        assert response.path_valid is False
        assert response.path_error == "Path does not exist or is not mounted"


class TestBackupHistoryEntry:
    """Tests for BackupHistoryEntry response model."""

    def test_minimal_entry(self):
        """Should accept minimal required fields."""
        from datetime import datetime

        entry = BackupHistoryEntry(
            id=1,
            started_at=datetime.now(),
            completed_at=None,
            trigger_type="manual",
            status="running",
            snapshot_id=None,
            duration_seconds=None,
            files_new=None,
            files_changed=None,
            files_unmodified=None,
            bytes_added=None,
            bytes_total=None,
            db_migration_version=None,
            error_message=None,
        )
        assert entry.status == "running"
        assert entry.trigger_type == "manual"


class TestTriggerBackupResponse:
    """Tests for TriggerBackupResponse response model."""

    def test_with_history_id(self):
        """Should include history_id when backup starts."""
        response = TriggerBackupResponse(
            message="Backup started",
            history_id=42,
        )
        assert response.history_id == 42

    def test_without_history_id(self):
        """Should allow None history_id."""
        response = TriggerBackupResponse(message="Error")
        assert response.history_id is None
