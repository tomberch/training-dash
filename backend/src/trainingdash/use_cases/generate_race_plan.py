"""
GenerateRacePlan use case.

Orchestrates race plan generation by combining course data, rider/bike
parameters, and pacing algorithms (heuristic or optimized).
"""

from dataclasses import dataclass
from decimal import Decimal

from trainingdash.domain.cda_estimation import get_default_cda, get_default_crr
from trainingdash.domain.course_segmentation import CourseSegment
from trainingdash.domain.pacing import generate_heuristic_pacing
from trainingdash.domain.pacing_optimizer import optimize_pacing
from trainingdash.domain.physics import EnvironmentParams, RiderParams
from trainingdash.domain.wbal import predict_wbal_for_plan
from trainingdash.repositories.postgres.models import RacePlan
from trainingdash.repositories.protocols import BikeRepo, CourseRepo, RacePlanRepo, UserRepo


@dataclass
class GeneratePlanRequest:
    """Request parameters for race plan generation."""

    course_id: int
    bike_id: int | None = None  # if None, use defaults
    rider_weight_kg: float | None = None  # if None, use user.weight_kg
    ftp_watts: int = 250
    cp_watts: int | None = None  # if None, estimate from FTP
    w_prime_joules: int | None = None  # if None, use default 20kJ
    target_intensity: float = 0.85
    use_optimizer: bool = False  # heuristic by default
    name: str | None = None


@dataclass
class GeneratePlanResult:
    """Result of race plan generation."""

    plan: RacePlan
    comparison: dict  # constant vs heuristic vs optimized times
    warnings: list[str]


class GenerateRacePlan:
    """
    Use case for generating race pacing plans.

    Orchestrates:
    1. Loading course and bike data
    2. Building rider/environment parameters
    3. Running pacing algorithm (heuristic or optimizer)
    4. Calculating comparison times
    5. Saving plan to database
    """

    def __init__(
        self,
        course_repo: CourseRepo,
        bike_repo: BikeRepo,
        user_repo: UserRepo,
        plan_repo: RacePlanRepo,
    ) -> None:
        self._course_repo = course_repo
        self._bike_repo = bike_repo
        self._user_repo = user_repo
        self._plan_repo = plan_repo

    async def execute(
        self,
        user_id: int,
        request: GeneratePlanRequest,
    ) -> GeneratePlanResult:
        """
        Generate a race pacing plan.

        Pipeline:
        1. Load course with segments
        2. Load bike (or use defaults)
        3. Get rider weight from request or user profile
        4. Build rider/environment params
        5. If use_optimizer: generate optimized plan
           Else: generate heuristic plan
        6. Calculate comparison times
        7. Save plan to database
        8. Return result
        """
        warnings: list[str] = []

        # 1. Load course
        course = await self._course_repo.get_by_id(request.course_id, user_id)
        if course is None:
            raise ValueError(f"Course {request.course_id} not found")

        # Parse segments from course JSONB
        segments = self._parse_segments(course.segments or [])
        if not segments:
            raise ValueError("Course has no segments")

        # 2. Load bike or use defaults
        cda: float
        crr: float
        bike_weight_kg: float | None = None
        bike_id: int | None = None

        if request.bike_id is not None:
            bike = await self._bike_repo.get_by_id(request.bike_id, user_id)
            if bike is None:
                warnings.append(f"Bike {request.bike_id} not found, using defaults")
                cda = get_default_cda("road")
                crr = get_default_crr("road")
            else:
                bike_id = bike.id
                cda = float(bike.cda) if bike.cda else get_default_cda(bike.bike_type)
                crr = float(bike.crr) if bike.crr else get_default_crr(bike.bike_type)
                bike_weight_kg = float(bike.weight_kg) if bike.weight_kg else None
        else:
            # No bike specified - use road defaults
            cda = get_default_cda("road")
            crr = get_default_crr("road")
            warnings.append("No bike specified, using road defaults")

        # 3. Get rider weight
        rider_weight_kg: float
        if request.rider_weight_kg is not None:
            rider_weight_kg = request.rider_weight_kg
        else:
            user = await self._user_repo.get_by_id(user_id)
            if user and user.weight_kg:
                rider_weight_kg = float(user.weight_kg)
            else:
                rider_weight_kg = 75.0  # Default
                warnings.append("No rider weight specified, using 75kg default")

        # Total mass includes bike
        total_mass_kg = rider_weight_kg + (bike_weight_kg or 8.0)

        # 4. Build parameters
        rider_params = RiderParams(mass_kg=total_mass_kg, cda=cda, crr=crr)
        env_params = EnvironmentParams()  # Sea level defaults

        # Estimate CP and W' if not provided
        ftp = request.ftp_watts
        cp = request.cp_watts if request.cp_watts else int(ftp * 0.95)
        w_prime = request.w_prime_joules if request.w_prime_joules else 20000

        if request.cp_watts is None:
            warnings.append(f"CP estimated as 95% of FTP: {cp}W")
        if request.w_prime_joules is None:
            warnings.append("W' using default: 20kJ")

        # 5. Generate pacing plan
        if request.use_optimizer:
            # Estimate energy budget from target intensity and estimated time
            estimated_time_s = sum(seg.length_m / 8.0 for seg in segments)
            target_avg_power = ftp * request.target_intensity
            target_energy_kj = (target_avg_power * estimated_time_s) / 1000

            optimized = optimize_pacing(
                segments=segments,
                rider_ftp=ftp,
                rider_cp=cp,
                rider_w_prime=w_prime,
                target_energy_kj=target_energy_kj,
                rider_params=rider_params,
                env_params=env_params,
            )

            total_time_s = optimized.total_time_s
            total_distance_m = optimized.total_distance_m
            avg_power_w = optimized.avg_power_w
            normalized_power_w = optimized.normalized_power_w
            intensity_factor = optimized.intensity_factor
            segment_targets = [
                {
                    "segment_idx": t.segment_idx,
                    "power_w": t.target_power_w,
                    "time_s": t.estimated_time_s,
                    "speed_mps": t.estimated_speed_mps,
                }
                for t in optimized.targets
            ]
            wbal_min = optimized.wbal_min
            optimization_method = "optimized"

            # Calculate comparison
            comparison = {
                "heuristic_time_s": optimized.total_time_s / (1 - optimized.improvement_vs_heuristic_pct / 100)
                if optimized.improvement_vs_heuristic_pct < 100
                else optimized.total_time_s,
                "optimized_time_s": optimized.total_time_s,
                "improvement_vs_heuristic_pct": optimized.improvement_vs_heuristic_pct,
                "improvement_vs_constant_pct": optimized.improvement_vs_constant_pct,
            }
        else:
            # Heuristic pacing
            heuristic = generate_heuristic_pacing(
                segments=segments,
                rider_ftp=ftp,
                target_intensity=request.target_intensity,
                rider_params=rider_params,
                env_params=env_params,
            )

            total_time_s = heuristic.total_time_s
            total_distance_m = heuristic.total_distance_m
            avg_power_w = heuristic.avg_power_w
            normalized_power_w = heuristic.normalized_power_w
            intensity_factor = heuristic.intensity_factor
            segment_targets = [
                {
                    "segment_idx": t.segment_idx,
                    "power_w": t.target_power_w,
                    "time_s": t.estimated_time_s,
                    "speed_mps": t.estimated_speed_mps,
                }
                for t in heuristic.targets
            ]
            optimization_method = "heuristic"

            # Calculate W'bal prediction
            import numpy as np

            powers = np.array([t.target_power_w for t in heuristic.targets])
            times = np.array([t.estimated_time_s for t in heuristic.targets])
            wbal_prediction = predict_wbal_for_plan(powers, times, cp, w_prime)
            wbal_min = wbal_prediction.min_wbal

            # Comparison: constant power baseline
            constant_power = ftp * request.target_intensity
            constant_time_s = sum(
                seg.length_m
                / max(0.1, self._speed_at_power(constant_power, seg.avg_grade_pct, rider_params, env_params))
                for seg in segments
            )
            improvement_vs_constant = (
                (constant_time_s - total_time_s) / constant_time_s * 100 if constant_time_s > 0 else 0
            )

            comparison = {
                "constant_time_s": constant_time_s,
                "heuristic_time_s": total_time_s,
                "improvement_vs_constant_pct": improvement_vs_constant,
            }

        # Find distance at min W'bal
        wbal_min_distance_m = self._find_wbal_min_distance(segment_targets, segments) if wbal_min is not None else None

        # 7. Save plan
        plan = RacePlan(
            user_id=user_id,
            course_id=request.course_id,
            bike_id=bike_id,
            name=request.name,
            rider_weight_kg=Decimal(str(rider_weight_kg)),
            ftp_watts=ftp,
            cp_watts=cp,
            w_prime_joules=w_prime,
            bike_weight_kg=Decimal(str(bike_weight_kg)) if bike_weight_kg else None,
            cda=Decimal(str(cda)),
            crr=Decimal(str(crr)),
            target_intensity=Decimal(str(request.target_intensity)),
            optimization_method=optimization_method,
            total_time_s=total_time_s,
            total_distance_m=total_distance_m,
            avg_power_w=avg_power_w,
            normalized_power_w=normalized_power_w,
            intensity_factor=Decimal(str(round(intensity_factor, 2))),
            segment_targets=segment_targets,
            wbal_min=wbal_min,
            wbal_min_distance_m=wbal_min_distance_m,
        )

        saved_plan = await self._plan_repo.save(plan)

        return GeneratePlanResult(
            plan=saved_plan,
            comparison=comparison,
            warnings=warnings,
        )

    def _parse_segments(self, segments_json: list[dict]) -> list[CourseSegment]:
        """Parse JSONB segments into CourseSegment objects."""
        segments = []
        for seg in segments_json:
            segments.append(
                CourseSegment(
                    start_distance_m=seg.get("start_m", 0),
                    end_distance_m=seg.get("end_m", 0),
                    length_m=seg.get("distance_m", seg.get("end_m", 0) - seg.get("start_m", 0)),
                    avg_grade_pct=seg.get("avg_grade_pct", 0),
                    elevation_gain_m=seg.get("elevation_gain_m", 0),
                    elevation_loss_m=seg.get("elevation_loss_m", 0),
                    terrain_type=seg.get("terrain_type", "flat"),
                )
            )
        return segments

    def _speed_at_power(
        self,
        power: float,
        grade_pct: float,
        rider_params: RiderParams,
        env_params: EnvironmentParams,
    ) -> float:
        """Calculate speed for given power and grade."""
        from trainingdash.domain.physics import speed_from_power

        return speed_from_power(power, grade_pct, rider_params, env_params)

    def _find_wbal_min_distance(
        self,
        segment_targets: list[dict],
        segments: list[CourseSegment],
    ) -> float | None:
        """Find approximate distance where W'bal minimum occurs."""
        if not segment_targets or not segments:
            return None

        # Find segment with longest time above threshold (proxy for max depletion)
        cumulative_distance = 0.0
        max_depletion_distance = 0.0
        max_time_above_threshold = 0.0

        for target in segment_targets:
            seg_idx = target.get("segment_idx", 0)
            if seg_idx < len(segments):
                seg = segments[seg_idx]
                time_s = target.get("time_s", 0)

                # Accumulate distance
                cumulative_distance += seg.length_m

                # Track segment with most time (proxy for W'bal minimum location)
                if time_s > max_time_above_threshold:
                    max_time_above_threshold = time_s
                    max_depletion_distance = cumulative_distance

        return max_depletion_distance if max_depletion_distance > 0 else None
