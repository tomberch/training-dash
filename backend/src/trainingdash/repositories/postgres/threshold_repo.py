"""PostgreSQL implementation of ThresholdRepo.

Data access for threshold metric entries (FTP, LTHR, HRmax). Resolves
``metric_key -> metric_type_id`` inline per call — no cache (the
``metric_types`` table is a 7-row seed-only reference table).
"""

from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from trainingdash.domain.thresholds import ThresholdHistoryEntry, ThresholdValues
from trainingdash.repositories.postgres.models import MetricEntry, MetricType


class PostgresThresholdRepo:
    """PostgreSQL implementation of the ThresholdRepo protocol.

    All methods are read-only or flush-only; the caller owns the
    transaction (commits).
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def _get_metric_type_id(self, key: str) -> int | None:
        """Resolve a metric key (e.g. 'ftp') to its metric_type id."""
        result = await self._session.execute(select(MetricType.id).where(MetricType.key == key))
        return result.scalar_one_or_none()

    async def get_for_date(self, user_id: int, target_date: date) -> ThresholdValues:
        """Threshold values (FTP, LTHR, HRmax) effective on ``target_date``."""
        ftp = await self._get_metric_for_date(user_id, "ftp", target_date)
        lthr = await self._get_metric_for_date(user_id, "lthr", target_date)
        hrmax = await self._get_metric_for_date(user_id, "hrmax", target_date)
        return ThresholdValues(
            ftp_watts=ftp,
            lthr_bpm=lthr,
            hrmax_bpm=hrmax,
            effective_date=target_date,
        )

    async def _get_metric_for_date(self, user_id: int, metric_key: str, target_date: date) -> int | None:
        """Most recent metric value effective on ``target_date``."""
        type_id = await self._get_metric_type_id(metric_key)
        if not type_id:
            return None

        result = await self._session.execute(
            select(MetricEntry.value)
            .where(
                MetricEntry.user_id == user_id,
                MetricEntry.metric_type_id == type_id,
                MetricEntry.effective_date <= target_date,
            )
            .order_by(MetricEntry.effective_date.desc())
            .limit(1)
        )
        value = result.scalar_one_or_none()
        return int(value) if value is not None else None

    async def get_history(self, user_id: int) -> list[ThresholdHistoryEntry]:
        """All threshold entries for the user, grouped by effective_date (desc)."""
        ftp_id = await self._get_metric_type_id("ftp")
        lthr_id = await self._get_metric_type_id("lthr")
        hrmax_id = await self._get_metric_type_id("hrmax")

        type_ids = [t for t in [ftp_id, lthr_id, hrmax_id] if t]
        if not type_ids:
            return []

        result = await self._session.execute(
            select(MetricEntry)
            .where(
                MetricEntry.user_id == user_id,
                MetricEntry.metric_type_id.in_(type_ids),
            )
            .order_by(MetricEntry.effective_date.desc())
        )
        entries = result.scalars().all()

        by_date: dict[date, ThresholdHistoryEntry] = {}
        for entry in entries:
            d = entry.effective_date
            if d not in by_date:
                by_date[d] = ThresholdHistoryEntry(
                    effective_date=d,
                    source=entry.source,
                    created_at=entry.created_at,
                )
            if entry.metric_type_id == ftp_id:
                by_date[d].ftp_watts = int(entry.value)
            elif entry.metric_type_id == lthr_id:
                by_date[d].lthr_bpm = int(entry.value)
            elif entry.metric_type_id == hrmax_id:
                by_date[d].hrmax_bpm = int(entry.value)

        return sorted(by_date.values(), key=lambda e: e.effective_date, reverse=True)

    async def create(
        self,
        user_id: int,
        effective_date: date,
        ftp_watts: int | None = None,
        lthr_bpm: int | None = None,
        hrmax_bpm: int | None = None,
        source: str = "manual",
        source_detail: str | None = None,
    ) -> None:
        """Create threshold metric entries for the provided values. Flushes; caller commits."""
        for key, value in [
            ("ftp", ftp_watts),
            ("lthr", lthr_bpm),
            ("hrmax", hrmax_bpm),
        ]:
            if value is None:
                continue
            type_id = await self._get_metric_type_id(key)
            if not type_id:
                continue
            self._session.add(
                MetricEntry(
                    user_id=user_id,
                    metric_type_id=type_id,
                    effective_date=effective_date,
                    value=Decimal(str(value)),
                    source=source,
                    source_detail=source_detail,
                )
            )
        await self._session.flush()

    async def has_any_threshold(self, user_id: int) -> bool:
        """True if the user has at least one FTP threshold entry."""
        ftp_id = await self._get_metric_type_id("ftp")
        if not ftp_id:
            return False
        result = await self._session.execute(
            select(MetricEntry.id)
            .where(
                MetricEntry.user_id == user_id,
                MetricEntry.metric_type_id == ftp_id,
            )
            .limit(1)
        )
        return result.scalar_one_or_none() is not None
