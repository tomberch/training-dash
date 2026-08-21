"""
CalibrateFromActivities use case — orchestrates CdA calibration from ride history.

This use case handles the complete flow of calibrating a bike's aerodynamic
drag coefficient (CdA) from the user's ride data:
1. Validate bike eligibility (not e-bike, owned by user)
2. Fetch recent activities tagged to the bike
3. For each activity, load power/speed/elevation records
4. Select valid calibration segments
5. Filter out segments with drafting
6. Estimate CdA using linear regression
7. Optionally update the bike if confidence meets threshold

The use case can be called by HTTP routers or background workers.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np

from trainingdash.domain.bike import (
    BIKE_TYPE_DEFAULTS,
    is_calibration_eligible_type,
)
from trainingdash.domain.calibration_segments import (
    CalibrationSegment,
    calculate_grade,
    filter_drafting_segments,
    select_calibration_segments,
)
from trainingdash.domain.cda_estimation import (
    CdAEstimate,
    estimate_cda,
    inputs_from_segments,
)
from trainingdash.domain.physics import air_density_from_altitude
from trainingdash.repositories.protocols import ActivityRepo, BikeRepo, RecordRepo

logger = logging.getLogger(__name__)


class CalibrationError(Exception):
    """Base exception for calibration errors."""

    pass


class BikeNotFoundError(CalibrationError):
    """Raised when the bike is not found or not owned by user."""

    pass


class BikeNotEligibleError(CalibrationError):
    """Raised when the bike type is not eligible for calibration (e.g., e-bike)."""

    pass


class NoActivitiesError(CalibrationError):
    """Raised when no activities are tagged to the bike."""

    pass


class InsufficientDataError(CalibrationError):
    """Raised when not enough valid segments are found for calibration."""

    pass


@dataclass(frozen=True, slots=True)
class CalibrationResult:
    """Result of CdA calibration.

    Attributes:
        bike_id: ID of the calibrated bike.
        cda: Estimated CdA value in m².
        confidence: Confidence tier ('high', 'medium', 'low').
        n_activities_used: Number of activities that contributed data.
        n_segments_used: Number of valid calibration segments.
        total_calibration_duration_s: Total duration of all segments.
        previous_cda: Previous CdA value (None if using default).
        warnings: List of warning messages.
        updated: Whether the bike record was actually updated.
        rejection_summary: Summary of why segments were rejected.
    """

    bike_id: int
    cda: float
    confidence: str
    n_activities_used: int
    n_segments_used: int
    total_calibration_duration_s: float
    previous_cda: float | None
    warnings: list[str]
    updated: bool
    rejection_summary: dict[str, int]


class CalibrateFromActivities:
    """
    Use case for calibrating a bike's CdA from user's ride history.

    This use case coordinates:
    - Validating bike eligibility
    - Loading activities and their records
    - Selecting valid calibration segments
    - Filtering out drafting segments
    - Running CdA estimation
    - Updating the bike record if confidence is sufficient

    Example usage:
        use_case = CalibrateFromActivities(activity_repo, bike_repo, record_repo)
        result = await use_case.execute(
            user_id=1,
            bike_id=42,
            min_confidence='medium',
        )
    """

    def __init__(
        self,
        activity_repo: ActivityRepo,
        bike_repo: BikeRepo,
        record_repo: RecordRepo,
    ) -> None:
        """
        Initialize the use case with repository dependencies.

        Args:
            activity_repo: Repository for activity data.
            bike_repo: Repository for bike data.
            record_repo: Repository for activity records.
        """
        self._activity_repo = activity_repo
        self._bike_repo = bike_repo
        self._record_repo = record_repo

    async def execute(
        self,
        user_id: int,
        bike_id: int,
        max_activities: int = 50,
        min_confidence: str = "medium",
        rider_mass_kg: float | None = None,
    ) -> CalibrationResult:
        """
        Calibrate CdA for a bike from user's ride history.

        Pipeline:
        1. Get bike to find type (for default Crr)
        2. Get recent activities tagged to this bike
        3. For each activity:
           a. Load power/speed/elevation records
           b. Calculate grade from elevation
           c. Select valid calibration segments
        4. Aggregate all segments
        5. Filter out drafting segments
        6. Run CdA estimation
        7. If confidence >= min_confidence:
           a. Update bike.cda and bike.cda_source='calibrated'
           b. Set bike.calibrated_at
        8. Return result with diagnostics

        Args:
            user_id: User ID (for ownership validation).
            bike_id: Bike ID to calibrate.
            max_activities: Maximum number of recent activities to analyze.
            min_confidence: Minimum confidence to update bike ('low', 'medium', 'high').
            rider_mass_kg: Rider mass in kg (if None, uses default 75kg).

        Returns:
            CalibrationResult with the estimated CdA and diagnostics.

        Raises:
            BikeNotFoundError: If bike not found or not owned by user.
            BikeNotEligibleError: If bike type is not eligible (e.g., e-bike).
            NoActivitiesError: If no activities are tagged to the bike.
            InsufficientDataError: If not enough valid segments found.
        """
        warnings: list[str] = []

        # Step 1: Get and validate bike
        bike = await self._bike_repo.get_by_id(bike_id, user_id)
        if bike is None:
            raise BikeNotFoundError(f"Bike {bike_id} not found or not owned by user")

        if not is_calibration_eligible_type(bike.bike_type):
            raise BikeNotEligibleError(f"Bike type '{bike.bike_type}' is not eligible for CdA calibration")

        # Get default Crr for bike type (we fix Crr and solve for CdA)
        crr = BIKE_TYPE_DEFAULTS[bike.bike_type]["crr"]
        previous_cda = float(bike.cda) if bike.cda is not None else None

        # Use provided rider mass or default
        if rider_mass_kg is None:
            rider_mass_kg = 75.0  # Default rider mass
            warnings.append("Using default rider mass of 75kg")

        # Add bike weight
        bike_weight = float(bike.weight_kg) if bike.weight_kg else 8.0  # Default 8kg
        total_mass = rider_mass_kg + bike_weight

        # Step 2: Get activities tagged to this bike
        activities = await self._activity_repo.list_by_bike(bike_id, user_id, max_activities)
        if not activities:
            raise NoActivitiesError(f"No activities found tagged to bike {bike_id}. Tag some rides to this bike first.")

        # Step 3: Process each activity to extract calibration segments
        all_segments: list[CalibrationSegment] = []
        total_rejection_reasons: dict[str, int] = {}
        activities_with_segments = 0

        # Track arrays for calibration inputs and drafting detection
        all_power: list[float] = []
        all_speed: list[float] = []
        all_grade: list[float] = []
        segment_offset = 0  # Track offset for segment indices
        avg_air_density = 1.225  # Default, will be updated

        for activity in activities:
            # Skip activities without power data
            if activity.avg_power_w is None or activity.avg_power_w <= 0:
                total_rejection_reasons["no_power_data"] = total_rejection_reasons.get("no_power_data", 0) + 1
                continue

            # Load records for this activity
            records = await self._record_repo.list_for_activity(activity.id)
            if len(records) < 60:  # Need at least 60 samples for calibration
                total_rejection_reasons["too_few_records"] = total_rejection_reasons.get("too_few_records", 0) + 1
                continue

            # Extract arrays
            power, speed, grade, timestamps, avg_altitude = self._extract_arrays(records)

            # Skip if no valid data
            if len(power) < 60:
                total_rejection_reasons["insufficient_valid_data"] = (
                    total_rejection_reasons.get("insufficient_valid_data", 0) + 1
                )
                continue

            # Select calibration segments
            result = select_calibration_segments(
                power=power,
                speed=speed,
                grade=grade,
                timestamps=timestamps,
            )

            # Accumulate rejection reasons
            for reason, count in result.rejection_reasons.items():
                total_rejection_reasons[reason] = total_rejection_reasons.get(reason, 0) + count

            if result.segments:
                # Adjust segment indices for global array and store
                adjusted_segments = [
                    CalibrationSegment(
                        start_idx=seg.start_idx + segment_offset,
                        end_idx=seg.end_idx + segment_offset,
                        duration_s=seg.duration_s,
                        mean_speed_mps=seg.mean_speed_mps,
                        mean_power_w=seg.mean_power_w,
                        mean_grade_pct=seg.mean_grade_pct,
                        power_cv=seg.power_cv,
                        speed_cv=seg.speed_cv,
                        quality_score=seg.quality_score,
                    )
                    for seg in result.segments
                ]
                all_segments.extend(adjusted_segments)
                activities_with_segments += 1

                # Accumulate arrays for drafting detection and calibration
                all_power.extend(power.tolist())
                all_speed.extend(speed.tolist())
                all_grade.extend(grade.tolist())

                # Calculate air density from average altitude (use last activity's value)
                avg_air_density = air_density_from_altitude(avg_altitude)

            segment_offset += len(power)

        # Step 4: Check if we have enough data before drafting filter
        if not all_segments:
            raise InsufficientDataError(
                "No valid calibration segments found. "
                "Calibration requires steady-state riding at 30+ km/h on flat terrain."
            )

        # Step 5: Filter out segments with drafting
        # Use current CdA estimate (or default) for drafting detection
        current_cda = previous_cda if previous_cda else BIKE_TYPE_DEFAULTS[bike.bike_type]["cda"]

        power_arr = np.array(all_power)
        speed_arr = np.array(all_speed)
        grade_arr = np.array(all_grade)

        filtered_segments, drafting_rejected = filter_drafting_segments(
            segments=all_segments,
            power=power_arr,
            speed=speed_arr,
            baseline_cda=current_cda,
            rider_mass=total_mass,
        )

        if drafting_rejected > 0:
            total_rejection_reasons["drafting_detected"] = drafting_rejected
            warnings.append(f"{drafting_rejected} segment(s) excluded due to likely drafting")

        if not filtered_segments:
            raise InsufficientDataError(
                "No valid calibration segments remaining after drafting filter. "
                "Calibration requires solo riding without drafting."
            )

        # Build CalibrationInputs from filtered segments using array data
        filtered_inputs = inputs_from_segments(
            segments=filtered_segments,
            power=power_arr,
            speed=speed_arr,
            grade=grade_arr,
            air_density=avg_air_density,
            rider_mass=total_mass,
            crr=crr,
        )

        # Step 6: Run CdA estimation with fixed Crr
        estimate: CdAEstimate = estimate_cda(filtered_inputs, crr_fixed=crr)

        # Step 7: Determine if we should update the bike
        confidence_order = {"low": 0, "medium": 1, "high": 2}
        should_update = confidence_order.get(estimate.confidence, 0) >= confidence_order.get(min_confidence, 1)

        if should_update:
            await self._bike_repo.update_calibration(bike_id, user_id, estimate.cda)
            updated = True
        else:
            warnings.append(
                f"Confidence '{estimate.confidence}' is below minimum '{min_confidence}'. Bike CdA not updated."
            )
            updated = False

        return CalibrationResult(
            bike_id=bike_id,
            cda=estimate.cda,
            confidence=estimate.confidence,
            n_activities_used=activities_with_segments,
            n_segments_used=estimate.n_segments,
            total_calibration_duration_s=estimate.total_duration_s,
            previous_cda=previous_cda,
            warnings=warnings,
            updated=updated,
            rejection_summary=total_rejection_reasons,
        )

    def _extract_arrays(self, records: list) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, float]:
        """Extract numpy arrays from records.

        Returns:
            Tuple of (power, speed, grade, timestamps, avg_altitude)
        """
        # Extract raw data
        power_list: list[float] = []
        speed_list: list[float] = []
        altitude_list: list[float] = []
        timestamp_list: list[float] = []
        distance_list: list[float] = []

        for rec in records:
            # Skip records without required data
            if rec.power_w is None or rec.speed_mps is None:
                continue

            power_list.append(float(rec.power_w))
            speed_list.append(float(rec.speed_mps))
            altitude_list.append(float(rec.altitude_m) if rec.altitude_m else 0.0)
            timestamp_list.append(rec.timestamp.timestamp())
            distance_list.append(float(rec.distance_m))

        if len(power_list) < 2:
            return (
                np.array([]),
                np.array([]),
                np.array([]),
                np.array([]),
                0.0,
            )

        power = np.array(power_list)
        speed = np.array(speed_list)
        altitude = np.array(altitude_list)
        timestamps = np.array(timestamp_list)
        distance = np.array(distance_list)

        # Calculate grade from elevation changes using domain function
        grade = calculate_grade(altitude, distance)

        # Average altitude for air density calculation
        avg_altitude = float(np.mean(altitude))

        return power, speed, grade, timestamps, avg_altitude
