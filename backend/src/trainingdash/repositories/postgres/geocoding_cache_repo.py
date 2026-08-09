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
    
    Creates the cache table on first use if it doesn't exist.
    """

    def __init__(self, db: AsyncSession):
        self._db = db
        self._table_ensured = False

    async def _ensure_table(self) -> None:
        """Create cache table if it doesn't exist."""
        if self._table_ensured:
            return
        
        await self._db.execute(text("""
            CREATE TABLE IF NOT EXISTS geocoding_cache (
                cache_key VARCHAR(100) PRIMARY KEY,
                result_json TEXT,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """))
        await self._db.commit()
        self._table_ensured = True

    async def get(self, cache_key: str) -> str | None:
        """Get cached geocoding result by key."""
        await self._ensure_table()
        
        result = await self._db.execute(
            text("SELECT result_json FROM geocoding_cache WHERE cache_key = :key"),
            {"key": cache_key}
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
            {"key": cache_key, "value": result_json}
        )
        await self._db.commit()
