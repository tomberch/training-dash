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

from trainingdash.use_cases.ingest_activity import IngestActivity
from trainingdash.use_cases.delete_activity import DeleteActivity

__all__ = ["IngestActivity", "DeleteActivity"]
