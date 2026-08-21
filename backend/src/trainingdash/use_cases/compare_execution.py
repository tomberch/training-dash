"""
CompareExecution use case.

Compares an executed ride against a race plan to analyze pacing execution.
"""

from dataclasses import dataclass
from uuid import UUID

import numpy as np

from trainingdash.repositories.protocols import (
    ActivityRepo,
    CourseRepo,
    RacePlanRepo,
    RecordRepo,
)


@dataclass
class SegmentComparison:
    """Comparison data for a single segment."""

    segment_idx: int
    planned_power_w: float
    actual_power_w: float | None
    power_delta_w: float | None
    power_delta_pct: float | None
    planned_time_s: float
    actual_time_s: float | None
    time_delta_s: float | None
    planned_speed_mps: float
    actual_speed_mps: float | None
    speed_delta_mps: float | None
    distance_m: float
    grade_pct: float


@dataclass
class ComparisonResult:
    """Complete comparison between plan and executed activity."""

    plan_id: int
    activity_id: UUID
    segment_comparisons: list[SegmentComparison]

    # Summary stats
    total_planned_time_s: float
    total_actual_time_s: float
    time_delta_s: float
    time_delta_pct: float

    avg_power_planned_w: float
    avg_power_actual_w: float | None

    # Pacing analysis
    pacing_consistency: float  # 0-100, how well power matched plan
    segments_over_target: int
    segments_under_target: int
    segments_no_power: int

    # Key insights
    insights: list[str]


class CompareExecution:
    """
    Use case for comparing executed activity against race plan.

    Pipeline:
    1. Load plan with segment targets
    2. Load activity with records
    3. Match activity records to course segments by distance
    4. For each segment: extract actual power/speed/time and compare
    5. Generate summary stats
    6. Generate insights based on patterns
    """

    def __init__(
        self,
        plan_repo: RacePlanRepo,
        activity_repo: ActivityRepo,
        record_repo: RecordRepo,
        course_repo: CourseRepo,
    ) -> None:
        self._plan_repo = plan_repo
        self._activity_repo = activity_repo
        self._record_repo = record_repo
        self._course_repo = course_repo

    async def execute(
        self,
        user_id: int,
        plan_id: int,
        activity_id: UUID,
    ) -> ComparisonResult:
        """
        Compare executed activity against race plan.

        Args:
            user_id: User ID for access control
            plan_id: Race plan to compare against
            activity_id: Executed activity to analyze

        Returns:
            ComparisonResult with segment-by-segment and summary analysis

        Raises:
            ValueError: If plan or activity not found, or activity has no records
        """
        # 1. Load plan
        plan = await self._plan_repo.get_by_id(plan_id, user_id)
        if plan is None:
            raise ValueError(f"Plan {plan_id} not found")

        segment_targets = plan.segment_targets or []
        if not segment_targets:
            raise ValueError("Plan has no segment targets")

        # 2. Load activity
        activity = await self._activity_repo.get_by_id(activity_id, user_id)
        if activity is None:
            raise ValueError(f"Activity {activity_id} not found")

        # 3. Load records
        records = await self._record_repo.list_for_activity(activity_id)
        if not records:
            raise ValueError("Activity has no records")

        # 4. Load course for segment boundaries
        course = await self._course_repo.get_by_id(plan.course_id, user_id)
        if course is None:
            raise ValueError(f"Course {plan.course_id} not found")

        course_segments = course.segments or []

        # 5. Match records to segments and compute comparisons
        segment_comparisons = self._compute_segment_comparisons(
            segment_targets, course_segments, records
        )

        # 6. Compute summary stats
        total_planned_time = sum(t.get("time_s", 0) for t in segment_targets)
        total_actual_time = sum(
            c.actual_time_s for c in segment_comparisons if c.actual_time_s is not None
        )
        time_delta = total_actual_time - total_planned_time
        time_delta_pct = (time_delta / total_planned_time * 100) if total_planned_time > 0 else 0

        # Average powers
        avg_power_planned = plan.avg_power_w

        actual_powers = [c.actual_power_w for c in segment_comparisons if c.actual_power_w is not None]
        actual_times = [c.actual_time_s for c in segment_comparisons if c.actual_time_s is not None and c.actual_power_w is not None]

        if actual_powers and actual_times:
            # Time-weighted average
            total_energy = sum(p * t for p, t in zip(actual_powers, actual_times))
            total_time_with_power = sum(actual_times)
            avg_power_actual = total_energy / total_time_with_power if total_time_with_power > 0 else None
        else:
            avg_power_actual = None

        # Pacing consistency and over/under counts
        pacing_consistency, over_count, under_count, no_power_count = self._compute_pacing_stats(
            segment_comparisons
        )

        # 7. Generate insights
        insights = generate_insights(segment_comparisons, segment_targets, course_segments)

        return ComparisonResult(
            plan_id=plan_id,
            activity_id=activity_id,
            segment_comparisons=segment_comparisons,
            total_planned_time_s=total_planned_time,
            total_actual_time_s=total_actual_time,
            time_delta_s=time_delta,
            time_delta_pct=time_delta_pct,
            avg_power_planned_w=avg_power_planned,
            avg_power_actual_w=avg_power_actual,
            pacing_consistency=pacing_consistency,
            segments_over_target=over_count,
            segments_under_target=under_count,
            segments_no_power=no_power_count,
            insights=insights,
        )

    def _compute_segment_comparisons(
        self,
        segment_targets: list[dict],
        course_segments: list[dict],
        records: list,
    ) -> list[SegmentComparison]:
        """
        Match activity records to segments and compute comparisons.

        Uses cumulative distance from records to map to segment boundaries.
        """
        comparisons = []

        # Build segment boundaries from course
        segment_bounds = []
        for i, seg in enumerate(course_segments):
            start_m = seg.get("start_m", 0)
            end_m = seg.get("end_m", 0)
            segment_bounds.append((start_m, end_m))

        # Group records by segment
        segment_records: dict[int, list] = {i: [] for i in range(len(segment_bounds))}

        for record in records:
            distance_m = record.distance_m or 0

            # Find which segment this record belongs to
            for seg_idx, (start_m, end_m) in enumerate(segment_bounds):
                # Allow small tolerance for GPS drift
                if start_m - 50 <= distance_m < end_m + 50:
                    segment_records[seg_idx].append(record)
                    break

        # Compute comparison for each segment
        for i, target in enumerate(segment_targets):
            seg_idx = target.get("segment_idx", i)
            planned_power = target.get("power_w", 0)
            planned_time = target.get("time_s", 0)
            planned_speed = target.get("speed_mps", 0)

            # Get course segment info
            course_seg = course_segments[seg_idx] if seg_idx < len(course_segments) else {}
            distance_m = course_seg.get("distance_m", course_seg.get("end_m", 0) - course_seg.get("start_m", 0))
            grade_pct = course_seg.get("avg_grade_pct", 0)

            # Get records for this segment
            recs = segment_records.get(seg_idx, [])

            if recs:
                # Compute actual values from records
                powers = [r.power_w for r in recs if r.power_w is not None and r.power_w > 0]
                speeds = [r.speed_mps for r in recs if r.speed_mps is not None and r.speed_mps > 0]

                actual_power = float(np.mean(powers)) if powers else None
                actual_speed = float(np.mean(speeds)) if speeds else None

                # Time from first to last record in segment
                timestamps = sorted(r.timestamp for r in recs)
                if len(timestamps) >= 2:
                    actual_time = (timestamps[-1] - timestamps[0]).total_seconds()
                elif actual_speed and actual_speed > 0:
                    actual_time = distance_m / actual_speed
                else:
                    actual_time = None

                # Compute deltas
                if actual_power is not None:
                    power_delta = actual_power - planned_power
                    power_delta_pct = (power_delta / planned_power * 100) if planned_power > 0 else 0
                else:
                    power_delta = None
                    power_delta_pct = None

                if actual_time is not None:
                    time_delta = actual_time - planned_time
                else:
                    time_delta = None
            else:
                # No records for this segment
                actual_power = None
                actual_speed = None
                actual_time = None
                power_delta = None
                power_delta_pct = None
                time_delta = None

            comparisons.append(
                SegmentComparison(
                    segment_idx=seg_idx,
                    planned_power_w=planned_power,
                    actual_power_w=actual_power,
                    power_delta_w=power_delta,
                    power_delta_pct=power_delta_pct,
                    planned_time_s=planned_time,
                    actual_time_s=actual_time,
                    time_delta_s=time_delta,
                    planned_speed_mps=planned_speed,
                    actual_speed_mps=actual_speed,
                    speed_delta_mps=(actual_speed - planned_speed) if actual_speed is not None else None,
                    distance_m=distance_m,
                    grade_pct=grade_pct,
                )
            )

        return comparisons

    def _compute_pacing_stats(
        self,
        comparisons: list[SegmentComparison],
    ) -> tuple[float, int, int, int]:
        """
        Compute pacing consistency score and segment counts.

        Returns:
            (pacing_consistency, over_count, under_count, no_power_count)
        """
        over_count = 0
        under_count = 0
        no_power_count = 0
        deviations = []

        for comp in comparisons:
            if comp.actual_power_w is None:
                no_power_count += 1
                continue

            if comp.power_delta_pct is not None:
                deviation = abs(comp.power_delta_pct)
                deviations.append(deviation)

                # Threshold: >5% over or under
                if comp.power_delta_pct > 5:
                    over_count += 1
                elif comp.power_delta_pct < -5:
                    under_count += 1

        # Pacing consistency: 100 - average absolute deviation (capped at 0-100)
        if deviations:
            avg_deviation = np.mean(deviations)
            pacing_consistency = max(0, min(100, 100 - avg_deviation))
        else:
            pacing_consistency = 0.0

        return pacing_consistency, over_count, under_count, no_power_count


def generate_insights(
    comparisons: list[SegmentComparison],
    segment_targets: list[dict],
    course_segments: list[dict],
) -> list[str]:
    """
    Generate human-readable insights about pacing execution.

    Patterns detected:
    - Started too fast / too slow
    - Good/poor climb pacing
    - Faded in final portion
    - Overall pacing quality
    """
    insights = []

    if not comparisons:
        return ["No comparison data available"]

    n_segments = len(comparisons)
    segments_with_power = [c for c in comparisons if c.actual_power_w is not None]

    if not segments_with_power:
        return ["No power data in activity"]

    # Check start pacing (first 25% of segments)
    early_count = max(1, n_segments // 4)
    early_segments = [c for c in comparisons[:early_count] if c.power_delta_pct is not None]

    if early_segments:
        early_avg_delta = np.mean([c.power_delta_pct for c in early_segments])
        if early_avg_delta > 8:
            insights.append(f"Started too fast: first {early_count} segments averaged {early_avg_delta:.0f}% over target")
        elif early_avg_delta < -8:
            insights.append(f"Started conservatively: first {early_count} segments averaged {abs(early_avg_delta):.0f}% under target")

    # Check final portion (last 25% of segments)
    late_count = max(1, n_segments // 4)
    late_segments = [c for c in comparisons[-late_count:] if c.power_delta_pct is not None]

    if late_segments:
        late_avg_delta = np.mean([c.power_delta_pct for c in late_segments])
        if late_avg_delta < -10:
            insights.append(f"Faded on final {late_count} segments: {abs(late_avg_delta):.0f}% under target power")

    # Check climb pacing (segments with grade > 3%)
    climb_comparisons = [c for c in comparisons if c.grade_pct > 3 and c.power_delta_pct is not None]

    if climb_comparisons:
        climb_avg_delta = np.mean([abs(c.power_delta_pct) for c in climb_comparisons])
        if climb_avg_delta < 5:
            insights.append(f"Good climb pacing: within {climb_avg_delta:.0f}% of target on climbs")
        elif climb_avg_delta > 15:
            # Check if consistently over or under
            climb_over = sum(1 for c in climb_comparisons if c.power_delta_pct and c.power_delta_pct > 5)
            if climb_over > len(climb_comparisons) * 0.6:
                insights.append(f"Pushed too hard on climbs: averaged {np.mean([c.power_delta_pct for c in climb_comparisons]):.0f}% over target")

    # Overall summary
    all_deltas = [c.power_delta_pct for c in comparisons if c.power_delta_pct is not None]
    if all_deltas:
        avg_deviation = np.mean([abs(d) for d in all_deltas])
        if avg_deviation < 5:
            insights.append("Excellent pacing execution overall")
        elif avg_deviation < 10:
            insights.append("Good pacing execution with minor variations")
        elif avg_deviation < 20:
            insights.append("Pacing varied significantly from plan")
        else:
            insights.append("Large deviations from planned pacing")

    # Time comparison
    total_planned = sum(c.planned_time_s for c in comparisons)
    total_actual = sum(c.actual_time_s for c in comparisons if c.actual_time_s is not None)

    if total_planned > 0 and total_actual > 0:
        time_diff = total_actual - total_planned
        time_diff_pct = abs(time_diff) / total_planned * 100
        if time_diff < 0:
            insights.append(f"Finished {abs(time_diff):.0f}s faster than planned ({time_diff_pct:.1f}%)")
        elif time_diff > 0:
            insights.append(f"Finished {time_diff:.0f}s slower than planned ({time_diff_pct:.1f}%)")

    return insights if insights else ["Pacing analysis complete"]
