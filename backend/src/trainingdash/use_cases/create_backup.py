"""
CreateBackup use case — orchestrates database and file backup using restic.

This use case handles the complete backup flow:
1. Read backup configuration from database
2. Initialize restic repository if needed (first run)
3. Backup PostgreSQL database via pg_dump piped to restic
4. Backup uploads directory
5. Apply retention policy (forget + prune)
6. Record backup history with restic metadata
"""

import asyncio
import json
import logging
import os
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

from trainingdash.crypto import decrypt, encrypt
from trainingdash.repositories.protocols import BackupRepo

if TYPE_CHECKING:
    from trainingdash.repositories.postgres.models import BackupConfig

logger = logging.getLogger(__name__)


class BackupError(Exception):
    """Base exception for backup errors."""

    pass


class BackupAlreadyRunningError(BackupError):
    """Raised when a backup is already in progress."""

    pass


class BackupNotConfiguredError(BackupError):
    """Raised when backup is not configured or disabled."""

    pass


class ResticError(BackupError):
    """Raised when a restic command fails."""

    def __init__(self, message: str, stderr: str | None = None):
        super().__init__(message)
        self.stderr = stderr


@dataclass
class BackupResult:
    """Result of a backup operation."""

    success: bool
    history_id: int
    snapshot_id: str | None = None
    duration_seconds: float | None = None
    files_new: int | None = None
    files_changed: int | None = None
    bytes_added: int | None = None
    error: str | None = None


class CreateBackup:
    """
    Use case for creating a backup of database and uploads.

    This use case coordinates:
    - Reading backup configuration
    - Restic repository initialization (if needed)
    - PostgreSQL dump via pg_dump to restic stdin
    - Uploads directory backup
    - Retention policy enforcement
    - Backup history recording

    Example usage:
        use_case = CreateBackup(backup_repo, database_url, uploads_dir)
        result = await use_case.execute(trigger_type="manual")
    """

    def __init__(
        self,
        backup_repo: BackupRepo,
        database_url: str,
        uploads_dir: Path | None = None,
    ) -> None:
        """
        Initialize the use case with dependencies.

        Args:
            backup_repo: Repository for backup config and history
            database_url: PostgreSQL connection URL
            uploads_dir: Path to uploads directory (defaults to TRAININGDASH_UPLOADS_DIR)
        """
        self._backup_repo = backup_repo
        self._database_url = database_url
        self._uploads_dir = uploads_dir or Path(os.environ.get("TRAININGDASH_UPLOADS_DIR", "/app/uploads"))

    async def execute(
        self,
        trigger_type: str = "manual",
    ) -> BackupResult:
        """
        Execute a backup.

        Steps:
        1. Check no backup is running
        2. Read and validate config
        3. Create history entry with status='running'
        4. Initialize restic repo if needed
        5. Backup database (pg_dump → restic stdin)
        6. Backup uploads directory
        7. Apply retention policy
        8. Update history with results

        Args:
            trigger_type: "manual" or "scheduled"

        Returns:
            BackupResult with success status and metadata

        Raises:
            BackupAlreadyRunningError: If a backup is already in progress
            BackupNotConfiguredError: If backup is not configured or disabled
        """
        # Check if backup is already running
        if await self._backup_repo.is_backup_running():
            raise BackupAlreadyRunningError("A backup is already in progress")

        # Get config
        config = await self._backup_repo.get_config()
        if config is None or not config.enabled:
            raise BackupNotConfiguredError("Backup is not configured or disabled")

        # Get current migration version
        migration_version = await self._get_migration_version()

        # Create history entry
        history = await self._backup_repo.create_history_entry(
            trigger_type=trigger_type,
            status="running",
            db_migration_version=migration_version,
        )

        start_time = datetime.now(UTC)
        snapshot_id: str | None = None
        error_message: str | None = None
        files_new: int | None = None
        files_changed: int | None = None
        files_unmodified: int | None = None
        bytes_added: int | None = None
        bytes_total: int | None = None

        try:
            # Get or generate restic password
            password = await self._get_or_create_password(config)

            # Initialize repo if needed
            await self._ensure_repo_initialized(config.repository_path, password)

            # Backup database
            db_result = await self._backup_database(config.repository_path, password)
            logger.info("Database backup completed: snapshot=%s", db_result.get("snapshot_id"))

            # Create and backup metadata JSON
            metadata_result = await self._backup_metadata(
                config.repository_path,
                password,
                migration_version=migration_version,
                trigger_type=trigger_type,
                started_at=start_time,
            )
            logger.info("Metadata backup completed: snapshot=%s", metadata_result.get("snapshot_id"))

            # Backup uploads directory
            if self._uploads_dir.exists():
                uploads_result = await self._backup_uploads(config.repository_path, password)
                logger.info("Uploads backup completed: snapshot=%s", uploads_result.get("snapshot_id"))

                # Use uploads result for stats (it's the larger backup usually)
                snapshot_id = uploads_result.get("snapshot_id")
                summary = uploads_result.get("summary", {})
            else:
                # No uploads to backup, use db result
                snapshot_id = db_result.get("snapshot_id")
                summary = db_result.get("summary", {})

            files_new = summary.get("files_new")
            files_changed = summary.get("files_changed")
            files_unmodified = summary.get("files_unmodified")
            bytes_added = summary.get("data_added")
            bytes_total = summary.get("total_bytes_processed")

            # Apply retention policy
            await self._apply_retention(
                config.repository_path,
                password,
                keep_daily=config.retention_keep_daily,
                keep_weekly=config.retention_keep_weekly,
                keep_monthly=config.retention_keep_monthly,
            )
            logger.info("Retention policy applied")

            status = "completed"

        except Exception as e:
            logger.exception("Backup failed: %s", e)
            error_message = str(e)
            status = "failed"

        # Calculate duration
        end_time = datetime.now(UTC)
        duration_seconds = (end_time - start_time).total_seconds()

        # Update history
        await self._backup_repo.update_history_entry(
            history.id,
            snapshot_id=snapshot_id,
            status=status,
            completed_at=end_time.replace(tzinfo=None),
            duration_seconds=duration_seconds,
            files_new=files_new,
            files_changed=files_changed,
            files_unmodified=files_unmodified,
            bytes_added=bytes_added,
            bytes_total=bytes_total,
            error_message=error_message,
        )

        return BackupResult(
            success=status == "completed",
            history_id=history.id,
            snapshot_id=snapshot_id,
            duration_seconds=duration_seconds,
            files_new=files_new,
            files_changed=files_changed,
            bytes_added=bytes_added,
            error=error_message,
        )

    async def _get_migration_version(self) -> str | None:
        """Get current alembic migration version from database."""
        try:
            return await self._backup_repo.get_migration_version()
        except Exception as e:
            logger.warning("Could not get migration version: %s", e)
            return None

    async def _get_or_create_password(self, config: "BackupConfig") -> str:
        """Get existing password or generate a new one."""
        if config.encrypted_password:
            return decrypt(config.encrypted_password)

        # Generate new password
        password = secrets.token_urlsafe(32)
        config.encrypted_password = encrypt(password)
        await self._backup_repo.save_config(config)
        logger.info("Generated new restic repository password")
        return password

    async def _run_restic(
        self,
        args: list[str],
        repo_path: str,
        password: str,
        stdin_data: bytes | None = None,
        stdin_pipe: asyncio.subprocess.Process | None = None,
    ) -> dict:
        """
        Run a restic command and parse JSON output.

        Args:
            args: Restic command arguments (without restic binary)
            repo_path: Path to restic repository
            password: Repository password
            stdin_data: Optional data to pipe to stdin
            stdin_pipe: Optional process whose stdout to pipe to restic stdin

        Returns:
            Parsed JSON output (or empty dict if no JSON)

        Raises:
            ResticError: If command fails
        """
        env = os.environ.copy()
        env["RESTIC_REPOSITORY"] = repo_path
        env["RESTIC_PASSWORD"] = password

        full_args = ["restic", "--json"] + args

        if stdin_pipe:
            # Pipe from another process
            proc = await asyncio.create_subprocess_exec(
                *full_args,
                stdin=stdin_pipe.stdout,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
            )
            stdout, stderr = await proc.communicate()
            # Also wait for the stdin pipe process
            await stdin_pipe.wait()
        elif stdin_data is not None:
            proc = await asyncio.create_subprocess_exec(
                *full_args,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
            )
            stdout, stderr = await proc.communicate(input=stdin_data)
        else:
            proc = await asyncio.create_subprocess_exec(
                *full_args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
            )
            stdout, stderr = await proc.communicate()

        if proc.returncode != 0:
            stderr_text = stderr.decode() if stderr else ""
            raise ResticError(
                f"Restic command failed: {' '.join(args)}",
                stderr=stderr_text,
            )

        # Parse JSON output (restic outputs JSON lines for some commands)
        result: dict = {}
        if stdout:
            for line in stdout.decode().strip().split("\n"):
                if line:
                    try:
                        parsed = json.loads(line)
                        # Merge or update based on message_type
                        if isinstance(parsed, dict):
                            msg_type = parsed.get("message_type", "")
                            if msg_type == "summary":
                                result["summary"] = parsed
                                result["snapshot_id"] = parsed.get("snapshot_id")
                            elif msg_type == "initialized":
                                result["initialized"] = True
                                result["id"] = parsed.get("id")
                            else:
                                result.update(parsed)
                    except json.JSONDecodeError:
                        pass

        return result

    async def _ensure_repo_initialized(self, repo_path: str, password: str) -> None:
        """Initialize restic repository if it doesn't exist."""
        # Try to list snapshots to check if repo exists
        try:
            await self._run_restic(["snapshots"], repo_path, password)
            logger.debug("Restic repository already initialized")
        except ResticError as e:
            # Check if it's a "repo not found" error
            if e.stderr and ("unable to open config file" in e.stderr or "Is there a repository" in e.stderr):
                logger.info("Initializing restic repository at %s", repo_path)
                # Create directory if needed
                Path(repo_path).mkdir(parents=True, exist_ok=True)
                await self._run_restic(["init"], repo_path, password)
            else:
                raise

    async def _backup_database(self, repo_path: str, password: str) -> dict:
        """Backup PostgreSQL database using pg_dump piped to restic."""
        # Convert asyncpg URL to psql format
        db_url = self._database_url.replace("+asyncpg", "")

        # Start pg_dump process
        pg_dump = await asyncio.create_subprocess_exec(
            "pg_dump",
            "--format=custom",  # Custom format is compressed and supports parallel restore
            db_url,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        # Pipe to restic
        result = await self._run_restic(
            ["backup", "--stdin", "--stdin-filename", "database.dump"],
            repo_path,
            password,
            stdin_pipe=pg_dump,
        )

        return result

    async def _backup_metadata(
        self,
        repo_path: str,
        password: str,
        *,
        migration_version: str | None,
        trigger_type: str,
        started_at: datetime,
    ) -> dict:
        """Create and backup metadata JSON file."""
        metadata = {
            "backup_type": "trainingdash",
            "version": "1.0",
            "timestamp": started_at.isoformat(),
            "trigger": trigger_type,
            "db_migration_version": migration_version,
        }
        metadata_json = json.dumps(metadata, indent=2).encode("utf-8")

        return await self._run_restic(
            ["backup", "--stdin", "--stdin-filename", "backup-metadata.json"],
            repo_path,
            password,
            stdin_data=metadata_json,
        )

    async def _backup_uploads(self, repo_path: str, password: str) -> dict:
        """Backup uploads directory."""
        return await self._run_restic(
            ["backup", str(self._uploads_dir)],
            repo_path,
            password,
        )

    async def _apply_retention(
        self,
        repo_path: str,
        password: str,
        keep_daily: int,
        keep_weekly: int,
        keep_monthly: int,
    ) -> None:
        """Apply retention policy and prune old snapshots."""
        await self._run_restic(
            [
                "forget",
                "--prune",
                f"--keep-daily={keep_daily}",
                f"--keep-weekly={keep_weekly}",
                f"--keep-monthly={keep_monthly}",
            ],
            repo_path,
            password,
        )
