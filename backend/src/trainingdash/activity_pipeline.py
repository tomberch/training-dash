"""
Explicit activity ingestion pipeline with typed step results.

This module defines the processing steps for activity ingestion as a clear,
ordered pipeline where each step receives typed inputs and produces typed outputs.
Independent steps (route matching, title generation) run in parallel.
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from trainingdash.metrics import (
    compute_normalized_power,
    compute_intensity_factor,
    compute_tss,
    compute_zone_times,
)
from trainingdash.models import (
    Activity,
    ActivityPeakPower,
    FitnessHistory,
    HrZone,
    Notification,
    PowerZone,
    ThresholdHistory,
    User,
)
from trainingdash.peaks import extract_peak_powers
from trainingdash.wbal import compute_wbal_series
from trainingdash.fitness import detect_breakthrough, get_all_time_bests, fit_cp_model

logger = logging.getLogger(__name__)


# --- Step Result Dataclasses ---


@dataclass
class MetricsResult:
    """Result of computing training metrics from power/HR data."""

    np_power_w: int | None = None
    intensity_factor: float | None = None
    tss: float | None = None
    training_load: float | None = None
    power_zone_times: dict[int, int] | None = None
    hr_zone_times: dict[int, int] | None = None
    wbal_min_joules: int | None = None
    wbal_min_pct: float | None = None


@dataclass
class PeaksResult:
    """Result of extracting peak powers at standard durations."""

    peaks: dict[int, int | None] = field(default_factory=dict)


@dataclass
class HrPowerResult:
    """Result of HR-power model update or estimation."""

    power_source: str | None = None
    power_confidence: float | None = None
    estimated_power: int | None = None


@dataclass
class BreakthroughResult:
    """Result of breakthrough detection."""

    is_breakthrough: bool = False
    fitness_updated: bool = False


@dataclass
class RouteMatchResult:
    """Result of route matching step."""

    route_id: int | None = None


@dataclass
class TitleResult:
    """Result of title generation step."""

    title: str | None = None
    title_source: str | None = None


@dataclass
class PipelineResult:
    """Combined result of all pipeline steps."""

    metrics: MetricsResult = field(default_factory=MetricsResult)
    peaks: PeaksResult = field(default_factory=PeaksResult)
    hr_power: HrPowerResult = field(default_factory=HrPowerResult)
    breakthrough: BreakthroughResult = field(default_factory=BreakthroughResult)
    route: RouteMatchResult = field(default_factory=RouteMatchResult)
    title: TitleResult = field(default_factory=TitleResult)


# --- Pipeline Class ---


class ActivityPipeline:
    """
    Explicit pipeline for processing activity data after initial ingestion.
    
    The pipeline processes activity data through ordered steps:
    1. Compute training metrics (NP, IF, TSS, zones, W'bal)
    2. Update HR-power model (if dual-sensor)
    3. Estimate HR-derived power (if HR-only)
    4. Extract peak powers
    5. Detect breakthroughs and update fitness model (unless batch_mode)
    6. Route matching and title generation (parallel, independent)
    
    Each step receives typed inputs and produces typed outputs, making the
    data flow explicit and testable.
    """

    def __init__(
        self,
        db: AsyncSession,
        activity: Activity,
        records: list[dict],
        batch_mode: bool = False,
    ) -> None:
        """
        Initialize the pipeline.
        
        Args:
            db: Database session
            activity: The Activity model instance (already persisted with id)
            records: List of record dicts with power_w, hr_bpm, etc.
            batch_mode: If True, skip per-activity fitness updates and use
                time-of-day title instead of geocoding
        """
        self.db = db
        self.activity = activity
        self.records = records
        self.batch_mode = batch_mode
        self.result = PipelineResult()

    async def run(self) -> PipelineResult:
        """
        Execute all pipeline steps in order, returning combined results.
        
        Steps 1-4 run sequentially (later steps depend on earlier results).
        Steps 5-6 (route matching, title generation) run in parallel as they
        are independent of each other.
        """
        # Step 1: Compute training metrics
        self.result.metrics = await self.compute_metrics()

        # Step 2: Update HR-power model (if dual-sensor ride)
        await self.update_hr_power_model()

        # Step 3: Estimate HR-derived power (if HR-only)
        hr_power_result = await self.estimate_hr_derived_power()
        self.result.hr_power = hr_power_result

        # Step 4: Extract peak powers
        self.result.peaks = await self.extract_peaks()

        # Step 5: Detect breakthroughs (skip in batch mode)
        if not self.batch_mode:
            self.result.breakthrough = await self.detect_breakthrough()

        # Step 6 & 7: Route matching and title generation (parallel)
        route_task = self.match_route()
        title_task = self.generate_title()
        
        route_result, title_result = await asyncio.gather(route_task, title_task)
        self.result.route = route_result
        self.result.title = title_result

        return self.result

    async def compute_metrics(self) -> MetricsResult:
        """
        Step 1: Compute training metrics from power/HR data.
        
        Computes NP, IF, TSS, power zone times, HR zone times, and W'bal.
        Requires user's threshold history and zone definitions.
        
        Returns:
            MetricsResult with computed values (None for missing data)
        """
        result = MetricsResult()
        
        # Get threshold effective at activity date
        activity_date = self.activity.started_at.date()
        threshold = await self._get_threshold_for_date(activity_date)
        
        if threshold is None:
            return result
        
        # Extract power and HR arrays
        power_array = [r.get("power_w") for r in self.records]
        hr_array = [r.get("hr_bpm") for r in self.records]
        
        has_power = any(p is not None and p > 0 for p in power_array)
        has_hr = any(h is not None and h > 0 for h in hr_array)
        
        if has_power:
            result = await self._compute_power_metrics(
                power_array, threshold, result
            )
        
        if has_hr:
            result = await self._compute_hr_metrics(hr_array, result)
        
        # Apply results to activity
        await self._apply_metrics_to_activity(result)
        
        return result

    async def _get_threshold_for_date(self, activity_date) -> ThresholdHistory | None:
        """Get the threshold effective at the given date."""
        query = await self.db.execute(
            select(ThresholdHistory)
            .where(
                ThresholdHistory.user_id == self.activity.user_id,
                ThresholdHistory.effective_date <= activity_date,
            )
            .order_by(ThresholdHistory.effective_date.desc())
            .limit(1)
        )
        return query.scalar_one_or_none()

    async def _compute_power_metrics(
        self,
        power_array: list,
        threshold: ThresholdHistory,
        result: MetricsResult,
    ) -> MetricsResult:
        """Compute power-based metrics: NP, IF, TSS, zones, W'bal."""
        # Compute NP
        np_watts = compute_normalized_power(power_array)
        if np_watts is not None:
            result.np_power_w = int(np_watts)
            
            # Compute IF and TSS
            if_value = compute_intensity_factor(np_watts, threshold.ftp_watts)
            if if_value is not None:
                result.intensity_factor = if_value
                
                duration_s = self.activity.moving_time_s or self.activity.elapsed_time_s
                tss = compute_tss(duration_s, np_watts, if_value, threshold.ftp_watts)
                if tss is not None:
                    result.tss = tss
                    result.training_load = tss
        
        # Compute power zone times
        power_zones = await self._get_power_zones()
        if power_zones:
            zones_list = [
                {
                    "zone_number": z.zone_number,
                    "min_watts": z.min_watts,
                    "max_watts": z.max_watts,
                }
                for z in power_zones
            ]
            result.power_zone_times = compute_zone_times(power_array, zones_list)
        
        # Compute W'bal
        w_prime_joules = threshold.ftp_watts * 60  # Simple estimate
        cp_watts = int(threshold.ftp_watts * 0.95)
        wbal_result = compute_wbal_series(power_array, cp_watts, w_prime_joules)
        if wbal_result["min_wbal"] is not None:
            result.wbal_min_joules = wbal_result["min_wbal"]
            result.wbal_min_pct = wbal_result["min_wbal_pct"]
        
        return result

    async def _get_power_zones(self) -> list[PowerZone]:
        """Get power zones for the user."""
        query = await self.db.execute(
            select(PowerZone)
            .where(PowerZone.user_id == self.activity.user_id)
            .order_by(PowerZone.zone_number)
        )
        return list(query.scalars().all())

    async def _compute_hr_metrics(
        self,
        hr_array: list,
        result: MetricsResult,
    ) -> MetricsResult:
        """Compute HR zone times."""
        hr_zones = await self._get_hr_zones()
        if hr_zones:
            zones_list = [
                {
                    "zone_number": z.zone_number,
                    "min_bpm": z.min_bpm,
                    "max_bpm": z.max_bpm,
                }
                for z in hr_zones
            ]
            result.hr_zone_times = compute_zone_times(
                hr_array, zones_list,
                value_key_min="min_bpm", value_key_max="max_bpm"
            )
        return result

    async def _get_hr_zones(self) -> list[HrZone]:
        """Get HR zones for the user."""
        query = await self.db.execute(
            select(HrZone)
            .where(HrZone.user_id == self.activity.user_id)
            .order_by(HrZone.zone_number)
        )
        return list(query.scalars().all())

    async def _apply_metrics_to_activity(self, metrics: MetricsResult) -> None:
        """Apply computed metrics to the activity model."""
        if metrics.np_power_w is not None:
            self.activity.np_power_w = metrics.np_power_w
        if metrics.intensity_factor is not None:
            self.activity.intensity_factor = metrics.intensity_factor
        if metrics.tss is not None:
            self.activity.tss = metrics.tss
        if metrics.training_load is not None:
            self.activity.training_load = metrics.training_load
        if metrics.power_zone_times:
            self.activity.power_zone_times = json.dumps(metrics.power_zone_times)
        if metrics.hr_zone_times:
            self.activity.hr_zone_times = json.dumps(metrics.hr_zone_times)
        if metrics.wbal_min_joules is not None:
            self.activity.wbal_min_joules = metrics.wbal_min_joules
        if metrics.wbal_min_pct is not None:
            self.activity.wbal_min_pct = metrics.wbal_min_pct
        
        await self.db.commit()
        await self.db.refresh(self.activity)

    async def update_hr_power_model(self) -> None:
        """
        Step 2: Update HR-power model if this is a dual-sensor ride.
        
        A dual-sensor ride has both measured power (NP) and heart rate.
        """
        from trainingdash.hr_power import update_ef_model
        
        if self.activity.np_power_w is None or self.activity.avg_hr_bpm is None:
            return
        
        if self.activity.avg_hr_bpm <= 0:
            return
        
        # Mark as measured power
        self.activity.power_source = "measured"
        await self.db.commit()
        
        # Update EF model
        await update_ef_model(self.db, self.activity.user_id)

    async def estimate_hr_derived_power(self) -> HrPowerResult:
        """
        Step 3: Estimate power from HR for HR-only activities.
        
        Only applies if:
        - Activity has no measured power
        - Activity has HR data
        - User has HR-derived power enabled
        - EF model exists
        
        Returns:
            HrPowerResult with estimated power and confidence
        """
        from trainingdash.hr_power import estimate_power_from_hr
        
        result = HrPowerResult()
        
        # Skip if already has power
        if self.activity.avg_power_w is not None:
            return result
        
        # Skip if no HR data
        if self.activity.avg_hr_bpm is None or self.activity.avg_hr_bpm <= 0:
            return result
        
        # Check if user has HR-derived power enabled
        user = await self._get_user()
        if user is None or not user.hr_derived_power_enabled:
            return result
        
        # Try to estimate power
        estimated_power, confidence = await estimate_power_from_hr(
            self.db, self.activity.user_id, self.activity.avg_hr_bpm
        )
        
        if estimated_power is None:
            return result
        
        # Store results
        result.power_source = "hr_derived"
        result.power_confidence = confidence
        result.estimated_power = estimated_power
        
        # Update activity
        self.activity.avg_power_w = estimated_power
        self.activity.power_source = "hr_derived"
        self.activity.power_confidence = confidence
        
        # Recompute metrics with estimated power
        await self._recompute_metrics_with_estimated_power(estimated_power)
        
        await self.db.commit()
        await self.db.refresh(self.activity)
        
        return result

    async def _get_user(self) -> User | None:
        """Get the user for this activity."""
        query = await self.db.execute(
            select(User).where(User.id == self.activity.user_id)
        )
        return query.scalar_one_or_none()

    async def _recompute_metrics_with_estimated_power(
        self, estimated_power: int
    ) -> None:
        """Recompute NP, IF, TSS using estimated power."""
        activity_date = self.activity.started_at.date()
        threshold = await self._get_threshold_for_date(activity_date)
        
        if threshold is None:
            return
        
        ftp = threshold.ftp_watts
        
        # For HR-derived power, estimate NP as slightly lower than avg
        np_estimate = int(estimated_power * 0.95)
        self.activity.np_power_w = np_estimate
        
        if ftp > 0:
            intensity_factor = compute_intensity_factor(np_estimate, ftp)
            self.activity.intensity_factor = intensity_factor
            
            duration_s = self.activity.moving_time_s or self.activity.elapsed_time_s
            if intensity_factor is not None:
                tss = compute_tss(duration_s, np_estimate, intensity_factor, ftp)
                self.activity.tss = tss

    async def extract_peaks(self) -> PeaksResult:
        """
        Step 4: Extract peak powers at standard durations.
        
        Stores peaks in ActivityPeakPower table for power curve analysis.
        
        Returns:
            PeaksResult with peaks dict mapping duration to watts
        """
        result = PeaksResult()
        
        power_array = [r.get("power_w") for r in self.records]
        has_power = any(p is not None and p > 0 for p in power_array)
        
        if not has_power:
            return result
        
        # Extract peaks at all standard durations
        peaks = extract_peak_powers(power_array)
        result.peaks = peaks
        
        # Store each peak
        for duration_seconds, watts in peaks.items():
            if watts is not None:
                peak = ActivityPeakPower(
                    activity_id=self.activity.id,
                    duration_seconds=duration_seconds,
                    watts=watts,
                )
                self.db.add(peak)
        
        await self.db.commit()
        
        return result

    async def detect_breakthrough(self) -> BreakthroughResult:
        """
        Step 5: Detect if activity is a breakthrough and update fitness model.
        
        A breakthrough occurs when the activity sets PRs at key durations.
        
        Returns:
            BreakthroughResult with is_breakthrough flag
        """
        result = BreakthroughResult()
        
        # Get this activity's peaks
        query = await self.db.execute(
            select(ActivityPeakPower)
            .where(ActivityPeakPower.activity_id == self.activity.id)
        )
        activity_peaks_rows = query.scalars().all()
        
        if not activity_peaks_rows:
            return result
        
        activity_peaks = {p.duration_seconds: p.watts for p in activity_peaks_rows}
        
        # Get all previous peaks
        all_time_bests = await self._get_all_time_bests()
        
        # Check for breakthrough
        is_breakthrough = detect_breakthrough(activity_peaks, all_time_bests)
        result.is_breakthrough = is_breakthrough
        
        if is_breakthrough:
            self.activity.is_breakthrough = True
            await self.db.commit()
            await self.db.refresh(self.activity)
            
            # Update fitness model
            await self._update_fitness_model()
            result.fitness_updated = True
        
        return result

    async def _get_all_time_bests(self) -> dict[int, int]:
        """Get all-time best powers before this activity."""
        query = await self.db.execute(
            select(ActivityPeakPower)
            .join(Activity, ActivityPeakPower.activity_id == Activity.id)
            .where(
                Activity.user_id == self.activity.user_id,
                Activity.id != self.activity.id,
            )
        )
        previous_peaks_rows = query.scalars().all()
        
        peaks_by_activity: dict[int, dict[int, int]] = {}
        for p in previous_peaks_rows:
            if p.activity_id not in peaks_by_activity:
                peaks_by_activity[p.activity_id] = {}
            peaks_by_activity[p.activity_id][p.duration_seconds] = p.watts
        
        return get_all_time_bests(list(peaks_by_activity.values()))

    async def _update_fitness_model(self) -> None:
        """Recalculate and store user's fitness model."""
        # Get all activities with peaks
        query = await self.db.execute(
            select(Activity)
            .where(Activity.user_id == self.activity.user_id)
            .order_by(Activity.started_at.desc())
        )
        activities = query.scalars().all()
        
        if not activities:
            return
        
        # Get peaks for all activities
        activity_ids = [a.id for a in activities]
        query = await self.db.execute(
            select(ActivityPeakPower)
            .where(ActivityPeakPower.activity_id.in_(activity_ids))
        )
        all_peaks = query.scalars().all()
        
        peaks_by_activity: dict[int, dict[int, int]] = {}
        for p in all_peaks:
            if p.activity_id not in peaks_by_activity:
                peaks_by_activity[p.activity_id] = {}
            peaks_by_activity[p.activity_id][p.duration_seconds] = p.watts
        
        peak_powers = []
        activity_dates = []
        for a in activities:
            if a.id in peaks_by_activity:
                peak_powers.append(peaks_by_activity[a.id])
                activity_dates.append(a.started_at)
        
        if not peak_powers:
            return
        
        model = fit_cp_model(peak_powers, activity_dates)
        if model is None:
            return
        
        # Store fitness snapshot
        fitness = FitnessHistory(
            user_id=self.activity.user_id,
            computed_at=datetime.now(timezone.utc).replace(tzinfo=None),
            pp_watts=model["pp_watts"],
            w_prime_joules=model["w_prime_joules"],
            cp_watts=model["cp_watts"],
        )
        self.db.add(fitness)
        await self.db.commit()
        
        # Check for FTP notification
        await self._check_ftp_notification(model["cp_watts"])

    async def _check_ftp_notification(self, cp_watts: int) -> None:
        """Check if CP diverges from FTP and create notification."""
        threshold = await self._get_threshold_for_date(self.activity.started_at.date())
        if threshold is None:
            return
        
        current_ftp = threshold.ftp_watts
        ratio = cp_watts / current_ftp
        
        if 0.95 <= ratio <= 1.05:
            return
        
        # Check for existing notification
        query = await self.db.execute(
            select(Notification)
            .where(
                Notification.user_id == self.activity.user_id,
                Notification.type == "ftp_suggestion",
                Notification.status == "pending",
            )
        )
        existing = query.scalar_one_or_none()
        
        if existing is not None:
            existing.message = f"Your fitness model suggests updating your FTP from {current_ftp}W to {cp_watts}W"
            existing.payload = json.dumps({
                "current_ftp": current_ftp,
                "suggested_ftp": cp_watts,
                "divergence_pct": round((ratio - 1) * 100, 1),
            })
            await self.db.commit()
            return
        
        notification = Notification(
            user_id=self.activity.user_id,
            type="ftp_suggestion",
            message=f"Your fitness model suggests updating your FTP from {current_ftp}W to {cp_watts}W",
            payload=json.dumps({
                "current_ftp": current_ftp,
                "suggested_ftp": cp_watts,
                "divergence_pct": round((ratio - 1) * 100, 1),
            }),
            status="pending",
        )
        self.db.add(notification)
        await self.db.commit()

    async def match_route(self) -> RouteMatchResult:
        """
        Step 6: Match activity to existing route or create new one.
        
        Uses GPS track similarity to identify recurring routes.
        
        Returns:
            RouteMatchResult with route_id if matched
        """
        from trainingdash.route_matching import find_or_create_route_id
        
        result = RouteMatchResult()
        
        route_id = await find_or_create_route_id(
            self.db, self.activity, self.records
        )
        
        if route_id is not None:
            result.route_id = route_id
            self.activity.route_id = route_id
            await self.db.commit()
            await self.db.refresh(self.activity)
        
        return result

    async def generate_title(self) -> TitleResult:
        """
        Step 7: Generate activity title from GPS data.
        
        In batch_mode, uses time-of-day title to avoid rate limits.
        Otherwise, uses reverse geocoding for descriptive title.
        
        Returns:
            TitleResult with title and source
        """
        result = TitleResult()
        
        if self.batch_mode:
            # Use time-of-day title for batch imports
            result.title = _time_of_day_title(self.activity.started_at)
            result.title_source = "pending"
        else:
            try:
                from trainingdash.title_generator import generate_activity_title
                
                title = await generate_activity_title(
                    self.records, self.activity.started_at
                )
                if title:
                    result.title = title
                    result.title_source = "auto"
                else:
                    result.title = _time_of_day_title(self.activity.started_at)
                    result.title_source = "pending"
            except Exception as e:
                logger.warning(
                    f"Failed to generate title for activity {self.activity.id}: {e}"
                )
                # Fall back to time-of-day title
                result.title = _time_of_day_title(self.activity.started_at)
                result.title_source = "pending"
        
        if result.title:
            self.activity.title = result.title
            self.activity.title_source = result.title_source
            await self.db.commit()
            await self.db.refresh(self.activity)
        
        return result


# --- Helper Functions ---


def _time_of_day_title(started_at: datetime) -> str:
    """
    Generate a time-of-day based title like "Morning Ride".
    
    Time ranges:
    - 05:00-11:59 -> Morning Ride
    - 12:00-16:59 -> Afternoon Ride
    - 17:00-20:59 -> Evening Ride
    - 21:00-04:59 -> Night Ride
    """
    hour = started_at.hour
    
    if 5 <= hour < 12:
        return "Morning Ride"
    elif 12 <= hour < 17:
        return "Afternoon Ride"
    elif 17 <= hour < 21:
        return "Evening Ride"
    else:
        return "Night Ride"
