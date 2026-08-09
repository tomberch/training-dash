"""
SAQ Queue configuration for TrainingDash.

This module provides the SAQ queue instance using Postgres as the backend,
eliminating the need for Redis. The queue is initialized lazily on first use.

Usage:
    from trainingdash.queue import get_queue

    queue = await get_queue()
    await queue.enqueue("job_name", arg1=value1)
"""

import os
from functools import lru_cache

from saq import Queue


def get_queue_url() -> str:
    """
    Get the Postgres URL for SAQ queue.
    
    SAQ requires psycopg3 format (postgresql:// not postgresql+asyncpg://).
    We derive it from DATABASE_URL by stripping the +asyncpg suffix.
    """
    db_url = os.environ.get("DATABASE_URL", "")
    if not db_url:
        raise RuntimeError("DATABASE_URL environment variable not set")
    
    # Convert SQLAlchemy async URL to psycopg3 URL
    # postgresql+asyncpg://... -> postgresql://...
    if "+asyncpg" in db_url:
        db_url = db_url.replace("+asyncpg", "")
    
    return db_url


def queue_available() -> bool:
    """Check if the queue backend (Postgres) is available."""
    return bool(os.environ.get("DATABASE_URL"))


@lru_cache(maxsize=1)
def _get_queue_instance() -> Queue:
    """Get or create the singleton SAQ queue instance."""
    from saq.queue.postgres import PostgresQueue
    
    return PostgresQueue.from_url(
        get_queue_url(),
        name="default",
        min_size=2,
        max_size=10,
    )


async def get_queue() -> Queue:
    """
    Get the SAQ queue instance, connecting if needed.
    
    The queue connects lazily on first call and reuses the connection.
    SAQ automatically creates the required tables (saq_jobs, saq_stats, saq_versions)
    on first connect via init_db().
    """
    queue = _get_queue_instance()
    if not queue._connected:
        await queue.connect()
    return queue


async def close_queue() -> None:
    """Disconnect the queue. Call this during application shutdown."""
    queue = _get_queue_instance()
    if queue._connected:
        await queue.disconnect()
        # Clear the cache so next get_queue() creates a fresh instance
        _get_queue_instance.cache_clear()
