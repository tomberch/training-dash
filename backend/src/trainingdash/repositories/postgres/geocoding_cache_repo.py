"""
PostgreSQL implementation of GeocodingCacheRepo.

Stores reverse geocoding results to respect OpenStreetMap/Photon rate limits
and usage policy.
"""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


class PostgresGeocodingCacheRepo:
    """
    PostgreSQL-backed geocoding cache repository.

    The ``geocoding_cache`` table is created by Alembic migration 013. The
    ``_ensure_table`` no-op guard below keeps tests working (the table isn't a
    SQLAlchemy model, so ``Base.metadata.create_all`` doesn't cover it) without
    committing on the caller's session — the previous version committed, a
    transaction-safety bug.
    """

    def __init__(self, db: AsyncSession):
        self._db = db
        self._table_ensured = False

    async def _ensure_table(self) -> None:
        """Create the cache table if it doesn't exist (idempotent, no commit).

        In prod the table is created by migration 013; this guard exists so
        tests (which build the schema via ``Base.metadata.create_all`` and
        don't run Alembic) still work. It does not commit — the caller owns
        the transaction.
        """
        if self._table_ensured:
            return
        await self._db.execute(
            text("""
            CREATE TABLE IF NOT EXISTS geocoding_cache (
                cache_key VARCHAR(100) PRIMARY KEY,
                result_json TEXT,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)
        )
        self._table_ensured = True

    async def get(self, cache_key: str) -> str | None:
        """Get cached geocoding result by key."""
        await self._ensure_table()

        result = await self._db.execute(
            text("SELECT result_json FROM geocoding_cache WHERE cache_key = :key"), {"key": cache_key}
        )
        row = result.fetchone()
        return row[0] if row else None

    async def set(self, cache_key: str, result_json: str) -> None:
        """Store geocoding result in cache (upsert)."""
        await self._ensure_table()

        await self._db.execute(
            text("""
                INSERT INTO geocoding_cache (cache_key, result_json)
                VALUES (:key, :value)
                ON CONFLICT (cache_key) DO UPDATE 
                SET result_json = :value, created_at = NOW()
            """),
            {"key": cache_key, "value": result_json},
        )
        await self._db.commit()
