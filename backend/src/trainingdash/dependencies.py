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
from trainingdash.repositories.postgres.analytics_repo import PostgresAnalyticsRepo
from trainingdash.repositories.postgres.audit_log_repo import PostgresAuditLogRepo
from trainingdash.repositories.postgres.backup_repo import PostgresBackupRepo
from trainingdash.repositories.postgres.bike_repo import PostgresBikeRepo
from trainingdash.repositories.postgres.course_repo import PostgresCourseRepo
from trainingdash.repositories.postgres.credentials_repo import (
    PostgresGarminCredentialsRepo,
    PostgresXertCredentialsRepo,
)
from trainingdash.repositories.postgres.event_repo import PostgresEventRepo
from trainingdash.repositories.postgres.geocoding_cache_repo import PostgresGeocodingCacheRepo
from trainingdash.repositories.postgres.historical_np_repo import PostgresHistoricalNpRepo
from trainingdash.repositories.postgres.notification_repo import PostgresNotificationRepo
from trainingdash.repositories.postgres.oauth_link_repo import PostgresOAuthLinkRepo
from trainingdash.repositories.postgres.pacing_coefficients_repo import PostgresPacingCoefficientsRepo
from trainingdash.repositories.postgres.race_plan_repo import PostgresRacePlanRepo
from trainingdash.repositories.postgres.recalculation_job_repo import (
    PostgresRecalculationJobRepo,
)
from trainingdash.repositories.postgres.record_repo import PostgresRecordRepo
from trainingdash.repositories.postgres.ride_event_repo import (
    PostgresJournalEntryActivityRepo,
    PostgresJournalEntryRepo,
    PostgresRideEventLinkRepo,
    PostgresRideEventMediaRepo,
    PostgresRideEventRepo,
)
from trainingdash.repositories.postgres.saved_filter_repo import PostgresSavedFilterRepo
from trainingdash.repositories.postgres.segment_repo import (
    PostgresSegmentEffortRepo,
    PostgresSegmentRepo,
    PostgresSegmentSuggestionRepo,
)
from trainingdash.repositories.postgres.settings_repo import PostgresAppSettingsRepo
from trainingdash.repositories.postgres.threshold_repo import PostgresThresholdRepo
from trainingdash.repositories.postgres.user_repo import PostgresUserRepo
from trainingdash.repositories.protocols import (
    ActivityRepo,
    AnalyticsRepo,
    AppSettingsRepo,
    AuditLogRepo,
    BackupRepo,
    BikeRepo,
    CourseRepo,
    EventRepo,
    GarminCredentialsRepo,
    HistoricalNpRepo,
    JournalEntryActivityRepo,
    JournalEntryRepo,
    NotificationRepo,
    OAuthLinkRepo,
    PacingCoefficientsRepo,
    RacePlanRepo,
    RecalculationJobRepo,
    RecordRepo,
    RideEventLinkRepo,
    RideEventMediaRepo,
    RideEventRepo,
    SavedFilterRepo,
    SegmentEffortRepo,
    SegmentRepo,
    SegmentSuggestionRepo,
    ThresholdRepo,
    UserRepo,
    XertCredentialsRepo,
)


async def get_activity_repo(db: DbSession) -> ActivityRepo:
    """Create an ActivityRepo bound to the current session."""
    return PostgresActivityRepo(db)


async def get_analytics_repo(db: DbSession) -> AnalyticsRepo:
    """Create an AnalyticsRepo bound to the current session."""
    return PostgresAnalyticsRepo(db)


async def get_backup_repo(db: DbSession) -> BackupRepo:
    """Create a BackupRepo bound to the current session."""
    return PostgresBackupRepo(db)


async def get_bike_repo(db: DbSession) -> BikeRepo:
    """Create a BikeRepo bound to the current session."""
    return PostgresBikeRepo(db)


async def get_course_repo(db: DbSession) -> CourseRepo:
    """Create a CourseRepo bound to the current session."""
    return PostgresCourseRepo(db)


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


async def get_event_repo(db: DbSession) -> EventRepo:
    """Create an EventRepo bound to the current session."""
    return PostgresEventRepo(db)


async def get_recalculation_job_repo(db: DbSession) -> RecalculationJobRepo:
    """Create a RecalculationJobRepo bound to the current session."""
    return PostgresRecalculationJobRepo(db)


async def get_oauth_link_repo(db: DbSession) -> OAuthLinkRepo:
    """Create an OAuthLinkRepo bound to the current session."""
    return PostgresOAuthLinkRepo(db)


async def get_threshold_repo(db: DbSession) -> ThresholdRepo:
    """Create a ThresholdRepo bound to the current session."""
    return PostgresThresholdRepo(db)


async def get_saved_filter_repo(db: DbSession) -> SavedFilterRepo:
    """Create a SavedFilterRepo bound to the current session."""
    return PostgresSavedFilterRepo(db)


async def get_segment_repo(db: DbSession) -> SegmentRepo:
    """Create a SegmentRepo bound to the current session."""
    return PostgresSegmentRepo(db)


async def get_segment_effort_repo(db: DbSession) -> SegmentEffortRepo:
    """Create a SegmentEffortRepo bound to the current session."""
    return PostgresSegmentEffortRepo(db)


async def get_segment_suggestion_repo(db: DbSession) -> SegmentSuggestionRepo:
    """Create a SegmentSuggestionRepo bound to the current session."""
    return PostgresSegmentSuggestionRepo(db)


async def get_race_plan_repo(db: DbSession) -> RacePlanRepo:
    """Create a RacePlanRepo bound to the current session."""
    return PostgresRacePlanRepo(db)


async def get_historical_np_repo(db: DbSession) -> HistoricalNpRepo:
    """Create a HistoricalNpRepo bound to the current session."""
    return PostgresHistoricalNpRepo(db)


async def get_pacing_coefficients_repo(db: DbSession) -> PacingCoefficientsRepo:
    """Create a PacingCoefficientsRepo bound to the current session."""
    return PostgresPacingCoefficientsRepo(db)


async def get_record_repo(db: DbSession) -> RecordRepo:
    """Create a RecordRepo bound to the current session."""
    return PostgresRecordRepo(db)


async def get_ride_event_repo(db: DbSession) -> RideEventRepo:
    """Create a RideEventRepo bound to the current session."""
    return PostgresRideEventRepo(db)


async def get_journal_entry_repo(db: DbSession) -> JournalEntryRepo:
    """Create a JournalEntryRepo bound to the current session."""
    return PostgresJournalEntryRepo(db)


async def get_ride_event_media_repo(db: DbSession) -> RideEventMediaRepo:
    """Create a RideEventMediaRepo bound to the current session."""
    return PostgresRideEventMediaRepo(db)


async def get_ride_event_link_repo(db: DbSession) -> RideEventLinkRepo:
    """Create a RideEventLinkRepo bound to the current session."""
    return PostgresRideEventLinkRepo(db)


async def get_journal_entry_activity_repo(db: DbSession) -> JournalEntryActivityRepo:
    """Create a JournalEntryActivityRepo bound to the current session."""
    return PostgresJournalEntryActivityRepo(db)


def get_geocoding_service(db: DbSession) -> GeocodingService:
    """Wire a GeocodingService with a Postgres cache repo.

    Single assembly point for the pipeline and the title endpoint — replaces
    the inline ``PostgresGeocodingCacheRepo(db) → GeocodingService(repo)``
    blocks that were duplicated across ``activity_pipeline.py`` and
    ``routers/activities.py``.
    """
    return GeocodingService(PostgresGeocodingCacheRepo(db))


# --- Services ---

from trainingdash.services.media import MediaService


def get_media_service() -> MediaService:
    """Create a MediaService instance."""
    return MediaService()


# Annotated types for use in router function signatures
ActivityRepoD = Annotated[ActivityRepo, Depends(get_activity_repo)]
AnalyticsRepoD = Annotated[AnalyticsRepo, Depends(get_analytics_repo)]
BackupRepoD = Annotated[BackupRepo, Depends(get_backup_repo)]
BikeRepoD = Annotated[BikeRepo, Depends(get_bike_repo)]
CourseRepoD = Annotated[CourseRepo, Depends(get_course_repo)]
UserRepoD = Annotated[UserRepo, Depends(get_user_repo)]
XertCredentialsRepoD = Annotated[XertCredentialsRepo, Depends(get_xert_credentials_repo)]
GarminCredentialsRepoD = Annotated[GarminCredentialsRepo, Depends(get_garmin_credentials_repo)]
NotificationRepoD = Annotated[NotificationRepo, Depends(get_notification_repo)]
AppSettingsRepoD = Annotated[AppSettingsRepo, Depends(get_app_settings_repo)]
AuditLogRepoD = Annotated[AuditLogRepo, Depends(get_audit_log_repo)]
EventRepoD = Annotated[EventRepo, Depends(get_event_repo)]
RecalculationJobRepoD = Annotated[RecalculationJobRepo, Depends(get_recalculation_job_repo)]
OAuthLinkRepoD = Annotated[OAuthLinkRepo, Depends(get_oauth_link_repo)]
RacePlanRepoD = Annotated[RacePlanRepo, Depends(get_race_plan_repo)]
HistoricalNpRepoD = Annotated[HistoricalNpRepo, Depends(get_historical_np_repo)]
PacingCoefficientsRepoD = Annotated[PacingCoefficientsRepo, Depends(get_pacing_coefficients_repo)]
ThresholdRepoD = Annotated[ThresholdRepo, Depends(get_threshold_repo)]
SavedFilterRepoD = Annotated[SavedFilterRepo, Depends(get_saved_filter_repo)]
SegmentRepoD = Annotated[SegmentRepo, Depends(get_segment_repo)]
SegmentEffortRepoD = Annotated[SegmentEffortRepo, Depends(get_segment_effort_repo)]
SegmentSuggestionRepoD = Annotated[SegmentSuggestionRepo, Depends(get_segment_suggestion_repo)]
RecordRepoD = Annotated[RecordRepo, Depends(get_record_repo)]
RideEventRepoD = Annotated[RideEventRepo, Depends(get_ride_event_repo)]
JournalEntryRepoD = Annotated[JournalEntryRepo, Depends(get_journal_entry_repo)]
RideEventMediaRepoD = Annotated[RideEventMediaRepo, Depends(get_ride_event_media_repo)]
RideEventLinkRepoD = Annotated[RideEventLinkRepo, Depends(get_ride_event_link_repo)]
JournalEntryActivityRepoD = Annotated[JournalEntryActivityRepo, Depends(get_journal_entry_activity_repo)]
MediaServiceD = Annotated[MediaService, Depends(get_media_service)]


# --- Use Cases ---

from trainingdash.use_cases.batch_link_activities import BatchLinkActivities
from trainingdash.use_cases.delete_activity import DeleteActivity
from trainingdash.use_cases.ensure_default_thresholds import EnsureDefaultThresholds
from trainingdash.use_cases.ingest_activity import IngestActivity


async def get_ingest_activity_use_case(
    db: DbSession,
    pacing_repo: PacingCoefficientsRepoD,
) -> IngestActivity:
    """Create an IngestActivity use case bound to the current session."""
    return IngestActivity(db, pacing_repo)


async def get_delete_activity_use_case(
    activity_repo: ActivityRepoD,
    db: DbSession,
) -> DeleteActivity:
    """Create a DeleteActivity use case with its dependencies."""
    return DeleteActivity(activity_repo, db)


async def get_ensure_default_thresholds_use_case(db: DbSession) -> EnsureDefaultThresholds:
    """Create an EnsureDefaultThresholds use case bound to the current session."""
    return EnsureDefaultThresholds(db)


async def get_batch_link_activities_use_case(
    event_repo: RideEventRepoD,
    entry_repo: JournalEntryRepoD,
    activity_repo: ActivityRepoD,
    activity_link_repo: JournalEntryActivityRepoD,
) -> BatchLinkActivities:
    """Create a BatchLinkActivities use case with its dependencies."""
    return BatchLinkActivities(event_repo, entry_repo, activity_repo, activity_link_repo)


from trainingdash.use_cases.calibrate_pacing import CalibratePacing


async def get_calibrate_pacing_use_case(
    db: DbSession,
    pacing_repo: PacingCoefficientsRepoD,
) -> CalibratePacing:
    """Create a CalibratePacing use case with its dependencies."""
    return CalibratePacing(db, pacing_repo)


IngestActivityD = Annotated[IngestActivity, Depends(get_ingest_activity_use_case)]
DeleteActivityD = Annotated[DeleteActivity, Depends(get_delete_activity_use_case)]
EnsureDefaultThresholdsD = Annotated[EnsureDefaultThresholds, Depends(get_ensure_default_thresholds_use_case)]
BatchLinkActivitiesD = Annotated[BatchLinkActivities, Depends(get_batch_link_activities_use_case)]
CalibratePacingD = Annotated[CalibratePacing, Depends(get_calibrate_pacing_use_case)]


from trainingdash.use_cases.approve_suggestion import ApproveSuggestion
from trainingdash.use_cases.create_segment import CreateSegment


async def get_approve_suggestion_use_case(
    segment_repo: SegmentRepoD,
    suggestion_repo: SegmentSuggestionRepoD,
) -> ApproveSuggestion:
    """Create an ApproveSuggestion use case with its dependencies."""
    return ApproveSuggestion(segment_repo, suggestion_repo)


async def get_create_segment_use_case(
    activity_repo: ActivityRepoD,
    record_repo: RecordRepoD,
    segment_repo: SegmentRepoD,
) -> CreateSegment:
    """Create a CreateSegment use case with its dependencies."""
    return CreateSegment(activity_repo, record_repo, segment_repo)


ApproveSuggestionD = Annotated[ApproveSuggestion, Depends(get_approve_suggestion_use_case)]
CreateSegmentD = Annotated[CreateSegment, Depends(get_create_segment_use_case)]
