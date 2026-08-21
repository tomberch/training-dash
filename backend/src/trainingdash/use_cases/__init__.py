"""
Use case classes — orchestrated business operations.

Use cases coordinate repositories and domain logic to accomplish
high-level tasks. They represent the application's business operations
and are independent of delivery mechanism (HTTP router, background worker, CLI).

Use cases:
- Take repository interfaces as constructor dependencies (dependency injection)
- Have a single public `execute` method that performs the operation
- Return domain objects or simple result types
- Are testable with fake repositories (no database required)

Example:
    class IngestActivity:
        def __init__(self, activity_repo: ActivityRepo, ...):
            self._activity_repo = activity_repo

        async def execute(self, user_id, fit_data, source, source_ref) -> Activity:
            # Parse, compute metrics, save
            ...
"""

from trainingdash.use_cases.breakthrough_evaluator import BreakthroughEvaluator
from trainingdash.use_cases.calibrate_bike import (
    BikeNotEligibleError,
    BikeNotFoundError,
    CalibrateFromActivities,
    CalibrationError,
    CalibrationResult,
    InsufficientDataError,
    NoActivitiesError,
)
from trainingdash.use_cases.delete_activity import DeleteActivity
from trainingdash.use_cases.ensure_default_thresholds import EnsureDefaultThresholds
from trainingdash.use_cases.fitness_model_updater import FitnessModelUpdater
from trainingdash.use_cases.hourly_sync_scheduler import HourlySyncScheduler
from trainingdash.use_cases.ingest_activity import IngestActivity
from trainingdash.use_cases.match_route import MatchRoute
from trainingdash.use_cases.recalc_after_delete import RecalcAfterDelete
from trainingdash.use_cases.recalculate_metrics import RecalculateMetrics, RecalculationResult
from trainingdash.use_cases.sync_from_provider import SyncFromProvider, SyncResult
from trainingdash.use_cases.upload_to_provider import (
    Provider,
    UploadResult,
    UploadToProvider,
)

__all__ = [
    "BikeNotEligibleError",
    "BikeNotFoundError",
    "BreakthroughEvaluator",
    "CalibrateFromActivities",
    "CalibrationError",
    "CalibrationResult",
    "DeleteActivity",
    "EnsureDefaultThresholds",
    "FitnessModelUpdater",
    "HourlySyncScheduler",
    "IngestActivity",
    "InsufficientDataError",
    "MatchRoute",
    "NoActivitiesError",
    "Provider",
    "RecalcAfterDelete",
    "RecalculateMetrics",
    "RecalculationResult",
    "SyncFromProvider",
    "SyncResult",
    "UploadResult",
    "UploadToProvider",
]
