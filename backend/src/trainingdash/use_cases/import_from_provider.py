"""
ImportFromProvider use case — orchestrates activity import from external providers.

This use case handles the complete flow of importing activities from a provider:
1. Retrieve and decrypt credentials
2. Connect to provider API
3. List activities in date range
4. Check for duplicates
5. Ingest new activities
6. Update last_synced_at timestamp
"""

import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from trainingdash.crypto import EncryptionError, decrypt
from trainingdash.domain.events import EventOutcome, EventType
from trainingdash.ingest import finalize_batch_import, is_duplicate_activity
from trainingdash.integrations.protocols import (
    CredentialInfo,
    ImportProvider,
)
from trainingdash.notifications import create_notification
from trainingdash.repositories.postgres.event_repo import PostgresEventRepo
from trainingdash.repositories.postgres.models import Activity

logger = logging.getLogger(__name__)


@dataclass
class ImportResult:
    """Result of an import operation."""

    success: bool
    user_id: int
    imported_activities: int = 0
    skipped_duplicates: int = 0
    error: str | None = None


class ImportFromProvider:
    """
    Use case for importing activities from an external provider.

    This use case coordinates:
    - Credential retrieval and decryption
    - Provider authentication
    - Activity listing and duplicate detection
    - Ingestion of new activities
    - Updating sync timestamps

    Example usage:
        use_case = ImportFromProvider(db)
        result = await use_case.execute(user_id=1, provider=XertImportProvider())
    """

    def __init__(self, db: AsyncSession) -> None:
        """
        Initialize the use case with dependencies.

        Args:
            db: Database session for persistence
        """
        self._db = db
        self._event_repo = PostgresEventRepo(db)

    async def execute(
        self,
        user_id: int,
        provider: ImportProvider,
    ) -> ImportResult:
        """
        Import activities from a provider for a user.

        Steps:
        1. Get and decrypt credentials
        2. Determine import date range (sync_since for first import, incremental otherwise)
        3. Connect to provider
        4. List activities and filter to new ones
        5. Check for duplicates from other sources
        6. Ingest new activities (with batch mode for >10)
        7. Finalize batch import if needed
        8. Update last_synced_at

        Args:
            user_id: User to import for
            provider: ImportProvider implementation (XertImportProvider, GarminImportProvider)

        Returns:
            ImportResult with success status and counts
        """
        provider_name = provider.source_name

        # Emit import.started event
        await self._event_repo.log(
            event_type=EventType.IMPORT_STARTED.value,
            outcome=EventOutcome.INFO.value,
            user_id=user_id,
            payload={"provider": provider_name},
        )

        # Get credentials
        creds = await self._get_credentials(user_id, provider)
        if creds is None:
            await self._event_repo.log(
                event_type=EventType.IMPORT_COMPLETED.value,
                outcome=EventOutcome.FAILURE.value,
                user_id=user_id,
                payload={
                    "provider": provider_name,
                    "error": f"No {provider_name.title()} credentials configured",
                },
            )
            return ImportResult(
                success=False,
                user_id=user_id,
                error=f"No {provider.source_name.title()} credentials configured",
            )

        cred_info = provider.extract_credentials(creds)

        # Decrypt password
        try:
            password = decrypt(cred_info.encrypted_password)
        except EncryptionError:
            logger.error(
                "import_%s: Failed to decrypt credentials for user %s",
                provider.source_name,
                user_id,
            )
            await self._event_repo.log(
                event_type=EventType.IMPORT_COMPLETED.value,
                outcome=EventOutcome.FAILURE.value,
                user_id=user_id,
                payload={"provider": provider_name, "error": "Failed to decrypt credentials"},
            )
            return ImportResult(
                success=False,
                user_id=user_id,
                error="Failed to decrypt credentials",
            )

        # Get existing source_refs to skip already-imported activities
        existing_refs = await self._get_existing_refs(user_id, provider.source_name)

        # Determine import date range
        start_date, end_date, is_first_import = self._determine_import_range(cred_info, existing_refs)

        log_prefix = f"import_{provider.source_name}"
        self._log_import_range(log_prefix, user_id, cred_info, is_first_import)

        # Connect to provider
        try:
            await provider.connect(cred_info.email, password)
        except Exception as e:
            logger.error("%s: Failed to connect for user %s: %s", log_prefix, user_id, e)
            await self._event_repo.log(
                event_type=EventType.IMPORT_COMPLETED.value,
                outcome=EventOutcome.FAILURE.value,
                user_id=user_id,
                payload={"provider": provider_name, "error": str(e)},
            )
            return ImportResult(
                success=False,
                user_id=user_id,
                error=str(e),
            )

        try:
            # List activities
            try:
                activities = await provider.list_activities(start_date, end_date)
            except Exception as e:
                logger.error(
                    "%s: Failed to list activities for user %s: %s",
                    log_prefix,
                    user_id,
                    e,
                )
                await self._event_repo.log(
                    event_type=EventType.IMPORT_COMPLETED.value,
                    outcome=EventOutcome.FAILURE.value,
                    user_id=user_id,
                    payload={"provider": provider_name, "error": str(e)},
                )
                return ImportResult(success=False, user_id=user_id, error=str(e))

            # Filter to new activities (not already imported from this source)
            new_activities = [a for a in activities if provider.make_source_ref(a.id) not in existing_refs]

            if not new_activities:
                logger.info("%s: No new activities for user %s", log_prefix, user_id)
                # Still update last_synced_at so the next import uses a tight window
                await self._write_last_synced_at(creds)
                await self._event_repo.log(
                    event_type=EventType.IMPORT_COMPLETED.value,
                    outcome=EventOutcome.SUCCESS.value,
                    user_id=user_id,
                    payload={
                        "provider": provider_name,
                        "imported_activities": 0,
                        "skipped_duplicates": 0,
                    },
                )
                return ImportResult(success=True, user_id=user_id)

            # Use batch mode if >10 activities to avoid notification spam
            batch_mode = len(new_activities) > 10
            if batch_mode:
                logger.info(
                    "%s: Using batch mode for %d activities",
                    log_prefix,
                    len(new_activities),
                )

            # Ingest each activity
            imported = 0
            skipped_duplicates = 0

            for activity in new_activities:
                try:
                    # Check for duplicates from other sources
                    is_dup = await is_duplicate_activity(
                        self._db,
                        user_id,
                        activity.started_at,
                        activity.distance_m,
                        provider.source_name,
                    )
                    if is_dup:
                        skipped_duplicates += 1
                        logger.info(
                            "%s: Skipped duplicate %s for user %s",
                            log_prefix,
                            provider.make_source_ref(activity.id),
                            user_id,
                        )
                        continue

                    # Ingest the activity
                    result = await provider.ingest_activity(self._db, user_id, activity, batch_mode)

                    if result is not None:
                        imported += 1
                        logger.info(
                            "%s: Created activity %s from %s for user %s",
                            log_prefix,
                            result.id,
                            provider.make_source_ref(activity.id),
                            user_id,
                        )
                    else:
                        logger.warning(
                            "%s: Failed to ingest activity %s for user %s",
                            log_prefix,
                            activity.id,
                            user_id,
                        )

                except Exception:
                    logger.exception(
                        "%s: Unexpected error processing activity %s",
                        log_prefix,
                        activity.id,
                    )
                    continue

            logger.info(
                "%s: Imported %d activities, skipped %d duplicates for user %s",
                log_prefix,
                imported,
                skipped_duplicates,
                user_id,
            )

            # Finalize batch import if needed
            if batch_mode and imported > 0:
                await finalize_batch_import(self._db, user_id, imported)

            # Record the successful import time
            await self._write_last_synced_at(creds)

            # Emit import.completed success event
            await self._event_repo.log(
                event_type=EventType.IMPORT_COMPLETED.value,
                outcome=EventOutcome.SUCCESS.value,
                user_id=user_id,
                payload={
                    "provider": provider_name,
                    "imported_activities": imported,
                    "skipped_duplicates": skipped_duplicates,
                },
            )

            # Create notification if duplicates were skipped
            if skipped_duplicates > 0:
                await create_notification(
                    self._db,
                    user_id=user_id,
                    notification_type="import_duplicates_skipped",
                    message=(
                        f"Skipped {skipped_duplicates} duplicate "
                        f"{'activity' if skipped_duplicates == 1 else 'activities'} "
                        f"from {provider_name.title()} (already imported from another source)"
                    ),
                )
                await self._db.commit()

            return ImportResult(
                success=True,
                user_id=user_id,
                imported_activities=imported,
                skipped_duplicates=skipped_duplicates,
            )

        finally:
            await provider.close()

    async def _get_credentials(
        self,
        user_id: int,
        provider: ImportProvider,
    ) -> Any | None:
        """Get credentials for a user and provider."""
        model = provider.credentials_model
        result = await self._db.execute(select(model).where(model.user_id == user_id))
        return result.scalar_one_or_none()

    async def _get_existing_refs(
        self,
        user_id: int,
        source: str,
    ) -> set[str]:
        """Get existing source_refs for a user and source."""
        result = await self._db.execute(
            select(Activity.source_ref).where(
                Activity.user_id == user_id,
                Activity.source == source,
            )
        )
        return set(result.scalars().all())

    async def _write_last_synced_at(self, creds: Any) -> None:
        """
        Stamp last_synced_at = now(UTC) on the credentials row.

        Called after every successful import (including no-new-activities runs) so
        that _determine_import_range can use an incremental 4-hour window next time.
        """
        creds.last_synced_at = datetime.now(UTC).replace(tzinfo=None)
        await self._db.commit()

    @staticmethod
    def _determine_import_range(
        cred_info: CredentialInfo,
        existing_refs: set[str],
    ) -> tuple[datetime, datetime, bool]:
        """
        Determine import date range.

        Priority order:
          1. First import (no existing activities): use sync_since if set, else 90 days.
          2. Subsequent import with last_synced_at: use last_synced_at - 4h (incremental).
          3. Subsequent import without last_synced_at: fall back to 90 days.

        Returns (start_date, end_date, is_first_import).
        """
        end_date = datetime.now(UTC).replace(tzinfo=None)
        is_first_import = len(existing_refs) == 0

        if is_first_import:
            sync_since = cred_info.sync_since
            if sync_since is not None:
                # sync_since may be a date or a datetime
                if hasattr(sync_since, "hour"):
                    start_date = sync_since
                else:
                    start_date = datetime.combine(sync_since, datetime.min.time())
            else:
                start_date = end_date - timedelta(days=90)
        else:
            last_synced_at = cred_info.last_synced_at
            if last_synced_at is not None:
                # Incremental window: last import time minus 4-hour buffer
                start_date = last_synced_at - timedelta(hours=4)
            else:
                # No last_synced_at recorded yet — fall back to 90 days
                start_date = end_date - timedelta(days=90)

        return start_date, end_date, is_first_import

    def _log_import_range(
        self,
        log_prefix: str,
        user_id: int,
        cred_info: CredentialInfo,
        is_first_import: bool,
    ) -> None:
        """Log the import range being used."""
        if is_first_import:
            if cred_info.sync_since:
                logger.info(
                    "%s: First import for user %s, using sync_since %s",
                    log_prefix,
                    user_id,
                    cred_info.sync_since,
                )
            else:
                logger.info(
                    "%s: First import for user %s, no sync_since set, using 90 days",
                    log_prefix,
                    user_id,
                )
        else:
            if cred_info.last_synced_at:
                logger.info(
                    "%s: Incremental import for user %s, using last_synced_at %s - 4h",
                    log_prefix,
                    user_id,
                    cred_info.last_synced_at,
                )
            else:
                logger.info(
                    "%s: Subsequent import for user %s, no last_synced_at, using 90 days",
                    log_prefix,
                    user_id,
                )
