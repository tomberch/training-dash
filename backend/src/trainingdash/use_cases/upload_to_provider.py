"""
UploadToProvider use case — upload an activity's FIT file to an external provider.

This use case handles:
1. Fetching the activity and its stored FIT file
2. Optionally modifying the FIT file (e.g., device spoofing)
3. Connecting to the provider with user credentials
4. Uploading the FIT file
"""

import logging
from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from trainingdash.crypto import EncryptionError, decrypt
from trainingdash.domain.fit_modifier import FitModificationError, FitModifications, modify_fit
from trainingdash.repositories.postgres.models import (
    Activity,
    GarminCredentials,
    XertCredentials,
)

logger = logging.getLogger(__name__)


class Provider(StrEnum):
    """Supported upload providers."""

    XERT = "xert"
    GARMIN = "garmin"


class UploadError(Exception):
    """Base class for upload errors."""

    pass


class ActivityNotFoundError(UploadError):
    """Raised when the activity doesn't exist or isn't owned by the user."""

    pass


class NoFitFileError(UploadError):
    """Raised when the activity has no stored FIT file."""

    pass


class CredentialsNotFoundError(UploadError):
    """Raised when the user has no credentials for the provider."""

    pass


class CredentialsDecryptError(UploadError):
    """Raised when credentials cannot be decrypted."""

    pass


class ProviderUploadError(UploadError):
    """Raised when the provider rejects the upload."""

    pass


class FitModifyError(UploadError):
    """Raised when FIT modification fails."""

    pass


@dataclass
class UploadResult:
    """Result of an upload operation."""

    success: bool
    provider: str
    provider_activity_id: str | None = None
    error: str | None = None


class UploadToProvider:
    """
    Use case for uploading an activity's FIT file to an external provider.

    Supports optional FIT file modifications (e.g., device spoofing) before upload.

    Example usage:
        use_case = UploadToProvider(db)
        result = await use_case.execute(
            user_id=1,
            activity_id=uuid,
            provider=Provider.GARMIN,
            modifications=FitModifications(device_product_id=4062),
        )
    """

    def __init__(self, db: AsyncSession) -> None:
        """Initialize the use case with dependencies."""
        self._db = db

    async def execute(
        self,
        user_id: int,
        activity_id: UUID,
        provider: Provider,
        modifications: FitModifications | None = None,
    ) -> UploadResult:
        """
        Upload an activity's FIT file to a provider.

        Args:
            user_id: User performing the upload
            activity_id: Activity to upload
            provider: Target provider (xert or garmin)
            modifications: Optional FIT modifications (device spoofing)

        Returns:
            UploadResult with success status and provider's activity ID

        Raises:
            ActivityNotFoundError: Activity doesn't exist or not owned by user
            NoFitFileError: Activity has no stored FIT file
            CredentialsNotFoundError: User has no credentials for provider
            CredentialsDecryptError: Failed to decrypt credentials
            FitModifyError: FIT modification failed
            ProviderUploadError: Provider rejected the upload
        """
        # 1. Get the activity
        activity = await self._get_activity(activity_id, user_id)
        if activity is None:
            raise ActivityNotFoundError(f"Activity {activity_id} not found")

        # 2. Get the FIT file
        if activity.raw_fit is None:
            raise NoFitFileError(f"Activity {activity_id} has no stored FIT file")

        fit_bytes = activity.raw_fit

        # 3. Apply modifications if requested
        if modifications is not None and modifications.device_product_id is not None:
            try:
                fit_bytes = modify_fit(fit_bytes, modifications)
                logger.info(
                    "Modified FIT for activity %s with device_product_id=%s",
                    activity_id,
                    modifications.device_product_id,
                )
            except FitModificationError as e:
                raise FitModifyError(f"Failed to modify FIT file: {e}") from e

        # 4. Upload to provider
        if provider == Provider.XERT:
            return await self._upload_to_xert(user_id, activity, fit_bytes)
        elif provider == Provider.GARMIN:
            return await self._upload_to_garmin(user_id, activity, fit_bytes)
        else:
            raise UploadError(f"Unsupported provider: {provider}")

    async def _get_activity(self, activity_id: UUID, user_id: int) -> Activity | None:
        """Fetch an activity owned by the user."""
        result = await self._db.execute(
            select(Activity).where(
                Activity.id == activity_id,
                Activity.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()

    async def _upload_to_xert(
        self,
        user_id: int,
        activity: Activity,
        fit_bytes: bytes,
    ) -> UploadResult:
        """Upload FIT to Xert."""
        # Get credentials
        result = await self._db.execute(select(XertCredentials).where(XertCredentials.user_id == user_id))
        creds = result.scalar_one_or_none()

        if creds is None:
            raise CredentialsNotFoundError("No Xert credentials configured")

        # Decrypt password
        try:
            password = decrypt(creds.encrypted_password)
        except EncryptionError as e:
            raise CredentialsDecryptError("Failed to decrypt Xert credentials") from e

        # Create client and upload
        from trainingdash.integrations.xert.client import XertAPIError, get_xert_client

        client = get_xert_client()
        try:
            await client.login(creds.xert_email, password)

            # Generate filename from activity date
            filename = f"{activity.started_at.strftime('%Y-%m-%d')}_{activity.id}.fit"
            provider_activity_id = await client.upload_fit(fit_bytes, filename)

            logger.info(
                "Uploaded activity %s to Xert as %s for user %s",
                activity.id,
                provider_activity_id,
                user_id,
            )

            return UploadResult(
                success=True,
                provider="xert",
                provider_activity_id=provider_activity_id,
            )

        except XertAPIError as e:
            logger.error("Xert upload failed for activity %s: %s", activity.id, e)
            raise ProviderUploadError(f"Xert upload failed: {e}") from e

        finally:
            await client.close()

    async def _upload_to_garmin(
        self,
        user_id: int,
        activity: Activity,
        fit_bytes: bytes,
    ) -> UploadResult:
        """Upload FIT to Garmin Connect."""
        # Get credentials
        result = await self._db.execute(select(GarminCredentials).where(GarminCredentials.user_id == user_id))
        creds = result.scalar_one_or_none()

        if creds is None:
            raise CredentialsNotFoundError("No Garmin credentials configured")

        # Decrypt password
        try:
            password = decrypt(creds.encrypted_password)
        except EncryptionError as e:
            raise CredentialsDecryptError("Failed to decrypt Garmin credentials") from e

        # Create client and upload
        from trainingdash.integrations.garmin.client import GarminAPIError, get_garmin_client

        client = get_garmin_client()
        try:
            client.login(creds.garmin_email, password)
            provider_activity_id = client.upload_fit(fit_bytes)

            logger.info(
                "Uploaded activity %s to Garmin as %s for user %s",
                activity.id,
                provider_activity_id,
                user_id,
            )

            return UploadResult(
                success=True,
                provider="garmin",
                provider_activity_id=provider_activity_id,
            )

        except GarminAPIError as e:
            logger.error("Garmin upload failed for activity %s: %s", activity.id, e)
            raise ProviderUploadError(f"Garmin upload failed: {e}") from e
