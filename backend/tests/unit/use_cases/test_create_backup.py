"""Tests for CreateBackup use case."""

from unittest import mock

import pytest

from trainingdash.use_cases.create_backup import (
    BackupAlreadyRunningError,
    BackupNotConfiguredError,
    CreateBackup,
    ResticError,
)


class FakeBackupRepo:
    """In-memory fake for BackupRepo."""

    def __init__(self):
        self.config = None
        self.history_entries: dict[int, dict] = {}
        self._next_id = 1
        self._backup_running = False

    async def get_config(self):
        return self.config

    async def save_config(self, config):
        self.config = config
        return config

    async def upsert_config(
        self,
        *,
        enabled: bool,
        repository_path: str,
        schedule_hour: int | None = None,
        retention_keep_daily: int,
        retention_keep_weekly: int,
        retention_keep_monthly: int,
    ):
        config = mock.MagicMock()
        config.enabled = enabled
        config.repository_path = repository_path
        config.schedule_hour = schedule_hour
        config.retention_keep_daily = retention_keep_daily
        config.retention_keep_weekly = retention_keep_weekly
        config.retention_keep_monthly = retention_keep_monthly
        config.encrypted_password = None
        config.created_at = None
        config.updated_at = None
        self.config = config
        return config

    async def create_history_entry(self, trigger_type: str, status: str, db_migration_version: str | None = None):
        entry_id = self._next_id
        self._next_id += 1
        entry = mock.MagicMock()
        entry.id = entry_id
        entry.trigger_type = trigger_type
        entry.status = status
        entry.db_migration_version = db_migration_version
        self.history_entries[entry_id] = {
            "id": entry_id,
            "trigger_type": trigger_type,
            "status": status,
            "db_migration_version": db_migration_version,
        }
        return entry

    async def update_history_entry(self, entry_id: int, **kwargs):
        if entry_id in self.history_entries:
            self.history_entries[entry_id].update({k: v for k, v in kwargs.items() if v is not None})
            entry = mock.MagicMock()
            for k, v in self.history_entries[entry_id].items():
                setattr(entry, k, v)
            return entry
        return None

    async def get_history(self, limit: int = 20):
        return list(self.history_entries.values())[:limit]

    async def get_history_entry(self, entry_id: int):
        return self.history_entries.get(entry_id)

    async def get_latest_completed(self):
        for entry in reversed(list(self.history_entries.values())):
            if entry.get("status") == "completed":
                return entry
        return None

    async def is_backup_running(self) -> bool:
        return self._backup_running

    async def get_migration_version(self) -> str | None:
        return "019"


class TestCreateBackupValidation:
    """Tests for backup precondition validation."""

    @pytest.mark.asyncio
    async def test_raises_when_backup_already_running(self):
        """Should raise BackupAlreadyRunningError if backup is in progress."""
        repo = FakeBackupRepo()
        repo._backup_running = True

        use_case = CreateBackup(
            backup_repo=repo,
            database_url="postgresql://test",
        )

        with pytest.raises(BackupAlreadyRunningError):
            await use_case.execute()

    @pytest.mark.asyncio
    async def test_raises_when_not_configured(self):
        """Should raise BackupNotConfiguredError if no config exists."""
        repo = FakeBackupRepo()

        use_case = CreateBackup(
            backup_repo=repo,
            database_url="postgresql://test",
        )

        with pytest.raises(BackupNotConfiguredError):
            await use_case.execute()

    @pytest.mark.asyncio
    async def test_raises_when_disabled(self):
        """Should raise BackupNotConfiguredError if backup is disabled."""
        repo = FakeBackupRepo()
        config = mock.MagicMock()
        config.enabled = False
        repo.config = config

        use_case = CreateBackup(
            backup_repo=repo,
            database_url="postgresql://test",
        )

        with pytest.raises(BackupNotConfiguredError):
            await use_case.execute()


class TestCreateBackupExecution:
    """Tests for backup execution flow."""

    @pytest.fixture
    def mock_config(self, tmp_path):
        """Create a mock backup config."""
        config = mock.MagicMock()
        config.enabled = True
        config.repository_path = str(tmp_path / "backup-repo")
        config.encrypted_password = b"encrypted"
        config.retention_keep_daily = 7
        config.retention_keep_weekly = 4
        config.retention_keep_monthly = 3
        return config

    @pytest.mark.asyncio
    async def test_creates_history_entry_on_start(self, mock_config, tmp_path):
        """Should create history entry with status='running' at start."""
        repo = FakeBackupRepo()
        repo.config = mock_config

        use_case = CreateBackup(
            backup_repo=repo,
            database_url="postgresql://test",
            uploads_dir=tmp_path,
        )

        # Mock all subprocess calls to avoid actual execution
        with mock.patch.object(use_case, "_get_migration_version", return_value="019"):
            with mock.patch.object(use_case, "_get_or_create_password", return_value="test-password"):
                with mock.patch.object(use_case, "_ensure_repo_initialized"):
                    with mock.patch.object(use_case, "_backup_database", return_value={"snapshot_id": "abc123"}):
                        with mock.patch.object(use_case, "_backup_metadata", return_value={"snapshot_id": "meta123"}):
                            with mock.patch.object(use_case, "_backup_uploads", return_value={"snapshot_id": "def456", "summary": {}}):
                                with mock.patch.object(use_case, "_apply_retention"):
                                    result = await use_case.execute(trigger_type="manual")

        assert len(repo.history_entries) == 1
        entry = next(iter(repo.history_entries.values()))
        assert entry["trigger_type"] == "manual"
        assert entry["db_migration_version"] == "019"

    @pytest.mark.asyncio
    async def test_records_success_on_completion(self, mock_config, tmp_path):
        """Should update history with status='completed' on success."""
        repo = FakeBackupRepo()
        repo.config = mock_config

        use_case = CreateBackup(
            backup_repo=repo,
            database_url="postgresql://test",
            uploads_dir=tmp_path,
        )

        with mock.patch.object(use_case, "_get_migration_version", return_value="019"):
            with mock.patch.object(use_case, "_get_or_create_password", return_value="test-password"):
                with mock.patch.object(use_case, "_ensure_repo_initialized"):
                    with mock.patch.object(use_case, "_backup_database", return_value={"snapshot_id": "abc123"}):
                        with mock.patch.object(use_case, "_backup_metadata", return_value={"snapshot_id": "meta123"}):
                            with mock.patch.object(use_case, "_backup_uploads", return_value={
                                "snapshot_id": "def456",
                                "summary": {"files_new": 10, "files_changed": 5, "data_added": 1024}
                            }):
                                with mock.patch.object(use_case, "_apply_retention"):
                                    result = await use_case.execute()

        assert result.success is True
        assert result.snapshot_id == "def456"
        assert result.files_new == 10
        assert result.files_changed == 5
        assert result.bytes_added == 1024

        entry = next(iter(repo.history_entries.values()))
        assert entry["status"] == "completed"
        assert entry["snapshot_id"] == "def456"

    @pytest.mark.asyncio
    async def test_records_failure_on_error(self, mock_config, tmp_path):
        """Should update history with status='failed' on error."""
        repo = FakeBackupRepo()
        repo.config = mock_config

        use_case = CreateBackup(
            backup_repo=repo,
            database_url="postgresql://test",
            uploads_dir=tmp_path,
        )

        with mock.patch.object(use_case, "_get_migration_version", return_value="019"):
            with mock.patch.object(use_case, "_get_or_create_password", return_value="test-password"):
                with mock.patch.object(use_case, "_ensure_repo_initialized"):
                    with mock.patch.object(use_case, "_backup_database", side_effect=ResticError("pg_dump failed")):
                        result = await use_case.execute()

        assert result.success is False
        assert "pg_dump failed" in result.error

        entry = next(iter(repo.history_entries.values()))
        assert entry["status"] == "failed"
        assert "pg_dump failed" in entry["error_message"]


class TestResticCommands:
    """Tests for restic command handling."""

    @pytest.mark.asyncio
    async def test_run_restic_parses_json_output(self, tmp_path):
        """Should parse restic JSON output correctly."""
        repo = FakeBackupRepo()
        config = mock.MagicMock()
        config.enabled = True
        config.repository_path = str(tmp_path / "repo")
        config.encrypted_password = None
        repo.config = config

        use_case = CreateBackup(
            backup_repo=repo,
            database_url="postgresql://test",
            uploads_dir=tmp_path,
        )

        # Mock subprocess to return JSON
        json_output = b'{"message_type": "summary", "snapshot_id": "abc123", "files_new": 5}\n'

        with mock.patch("asyncio.create_subprocess_exec") as mock_exec:
            mock_proc = mock.AsyncMock()
            mock_proc.returncode = 0
            mock_proc.communicate.return_value = (json_output, b"")
            mock_exec.return_value = mock_proc

            result = await use_case._run_restic(
                ["backup", "/test"],
                str(tmp_path / "repo"),
                "password",
            )

        assert result["snapshot_id"] == "abc123"
        assert result["summary"]["files_new"] == 5

    @pytest.mark.asyncio
    async def test_run_restic_raises_on_failure(self, tmp_path):
        """Should raise ResticError on non-zero exit."""
        repo = FakeBackupRepo()

        use_case = CreateBackup(
            backup_repo=repo,
            database_url="postgresql://test",
            uploads_dir=tmp_path,
        )

        with mock.patch("asyncio.create_subprocess_exec") as mock_exec:
            mock_proc = mock.AsyncMock()
            mock_proc.returncode = 1
            mock_proc.communicate.return_value = (b"", b"error: repository not found")
            mock_exec.return_value = mock_proc

            with pytest.raises(ResticError) as exc_info:
                await use_case._run_restic(
                    ["snapshots"],
                    str(tmp_path / "repo"),
                    "password",
                )

        assert "repository not found" in exc_info.value.stderr
