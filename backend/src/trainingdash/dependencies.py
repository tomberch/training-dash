"""
FastAPI dependency injection for repositories and use cases.

This module provides factory functions that create repository instances
wired to the current database session. Routers use these as FastAPI
dependencies via Annotated types.

Example usage in a router:
    from trainingdash.dependencies import ActivityRepoD, UserRepoD

    @router.get("/activities/{activity_id}")
    async def get_activity(repo: ActivityRepoD, activity_id: UUID):
        return await repo.get_by_id(activity_id, user_id)
"""

from typing import Annotated

from fastapi import Depends

from trainingdash.auth import DbSession
from trainingdash.integrations.geocoding import GeocodingService
from trainingdash.repositories.postgres.activity_repo import PostgresActivityRepo
from trainingdash.repositories.postgres.audit_log_repo import PostgresAuditLogRepo
from trainingdash.repositories.postgres.credentials_repo import (
    PostgresGarminCredentialsRepo,
    PostgresXertCredentialsRepo,
)
from trainingdash.repositories.postgres.geocoding_cache_repo import PostgresGeocodingCacheRepo
from trainingdash.repositories.postgres.notification_repo import PostgresNotificationRepo
from trainingdash.repositories.postgres.oauth_link_repo import PostgresOAuthLinkRepo
from trainingdash.repositories.postgres.recalculation_job_repo import (
    PostgresRecalculationJobRepo,
)
from trainingdash.repositories.postgres.settings_repo import PostgresAppSettingsRepo
from trainingdash.repositories.postgres.user_repo import PostgresUserRepo
from trainingdash.repositories.protocols import (
    ActivityRepo,
    AppSettingsRepo,
    AuditLogRepo,
    GarminCredentialsRepo,
    NotificationRepo,
    OAuthLinkRepo,
    RecalculationJobRepo,
    UserRepo,
    XertCredentialsRepo,
)


async def get_activity_repo(db: DbSession) -> ActivityRepo:
    """Create an ActivityRepo bound to the current session."""
    return PostgresActivityRepo(db)


async def get_user_repo(db: DbSession) -> UserRepo:
    """Create a UserRepo bound to the current session."""
    return PostgresUserRepo(db)


async def get_xert_credentials_repo(db: DbSession) -> XertCredentialsRepo:
    """Create an XertCredentialsRepo bound to the current session."""
    return PostgresXertCredentialsRepo(db)


async def get_garmin_credentials_repo(db: DbSession) -> GarminCredentialsRepo:
    """Create a GarminCredentialsRepo bound to the current session."""
    return PostgresGarminCredentialsRepo(db)


async def get_notification_repo(db: DbSession) -> NotificationRepo:
    """Create a NotificationRepo bound to the current session."""
    return PostgresNotificationRepo(db)


async def get_app_settings_repo(db: DbSession) -> AppSettingsRepo:
    """Create an AppSettingsRepo bound to the current session."""
    return PostgresAppSettingsRepo(db)


async def get_audit_log_repo(db: DbSession) -> AuditLogRepo:
    """Create an AuditLogRepo bound to the current session."""
    return PostgresAuditLogRepo(db)


async def get_recalculation_job_repo(db: DbSession) -> RecalculationJobRepo:
    """Create a RecalculationJobRepo bound to the current session."""
    return PostgresRecalculationJobRepo(db)


async def get_oauth_link_repo(db: DbSession) -> OAuthLinkRepo:
    """Create an OAuthLinkRepo bound to the current session."""
    return PostgresOAuthLinkRepo(db)


def get_geocoding_service(db: DbSession) -> GeocodingService:
    """Wire a GeocodingService with a Postgres cache repo.

    Single assembly point for the pipeline and the title endpoint — replaces
    the inline ``PostgresGeocodingCacheRepo(db) → GeocodingService(repo)``
    blocks that were duplicated across ``activity_pipeline.py`` and
    ``routers/activities.py``.
    """
    return GeocodingService(PostgresGeocodingCacheRepo(db))


# Annotated types for use in router function signatures
ActivityRepoD = Annotated[ActivityRepo, Depends(get_activity_repo)]
UserRepoD = Annotated[UserRepo, Depends(get_user_repo)]
XertCredentialsRepoD = Annotated[XertCredentialsRepo, Depends(get_xert_credentials_repo)]
GarminCredentialsRepoD = Annotated[GarminCredentialsRepo, Depends(get_garmin_credentials_repo)]
NotificationRepoD = Annotated[NotificationRepo, Depends(get_notification_repo)]
AppSettingsRepoD = Annotated[AppSettingsRepo, Depends(get_app_settings_repo)]
AuditLogRepoD = Annotated[AuditLogRepo, Depends(get_audit_log_repo)]
RecalculationJobRepoD = Annotated[RecalculationJobRepo, Depends(get_recalculation_job_repo)]
OAuthLinkRepoD = Annotated[OAuthLinkRepo, Depends(get_oauth_link_repo)]


# --- Use Cases ---

from trainingdash.use_cases.delete_activity import DeleteActivity
from trainingdash.use_cases.ingest_activity import IngestActivity


async def get_ingest_activity_use_case(db: DbSession) -> IngestActivity:
    """Create an IngestActivity use case bound to the current session."""
    return IngestActivity(db)


async def get_delete_activity_use_case(
    activity_repo: ActivityRepoD,
) -> DeleteActivity:
    """Create a DeleteActivity use case with its dependencies."""
    return DeleteActivity(activity_repo)


IngestActivityD = Annotated[IngestActivity, Depends(get_ingest_activity_use_case)]
DeleteActivityD = Annotated[DeleteActivity, Depends(get_delete_activity_use_case)]
