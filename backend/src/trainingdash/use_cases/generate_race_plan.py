"""
GenerateRacePlan use case.

Orchestrates race plan generation by combining course data, rider/bike
parameters, and pacing algorithms (heuristic or optimized).
"""

from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal

from trainingdash.domain.aero_selection import AeroSource, BikeAeroData, select_aero_params
from trainingdash.domain.course_segmentation import CourseSegment
from trainingdash.domain.pacing import (
    PacingCoefficients,
    RideTypeParams,
    RideTypePreset,
    generate_terrain_adapted_pacing,
    resolve_ride_type_params,
)
from trainingdash.domain.pacing_optimizer import optimize_pacing, optimize_pacing_for_time
from trainingdash.domain.physics import EnvironmentParams, RiderParams, calculate_headwind
from trainingdash.domain.wbal import predict_wbal_for_plan
from trainingdash.integrations.weather import (
    ForecastConditions,
    fetch_race_day_forecast,
    get_calm_conditions,
)
from trainingdash.repositories.postgres.models import RacePlan
from trainingdash.repositories.protocols import (
    BikeRepo,
    CourseRepo,
    PacingCoefficientsRepo,
    RacePlanRepo,
    UserRepo,
)


@dataclass
class GeneratePlanRequest:
    """Request parameters for race plan generation.

    Two targeting modes are supported:
    1. Intensity mode (default): Set target_intensity as % of FTP
    2. Time mode: Set target_time_s to specify desired finish time

    If target_time_s is provided, it takes precedence and the optimizer
    will calculate the power distribution needed to achieve that time.

    CdA/Crr selection:
    - If override_cda and override_crr are both set, use those values
    - Otherwise, use smart selection from bike data (estimated > manual > defaults)

    Weather conditions:
    - If target_date is set and within 16 days, fetch forecast
    - If target_date is beyond 16 days or not set, use calm conditions
    - Wind overrides can be set for specific scenarios

    Ride type:
    - Controls descent aggressiveness and expected stop time
    - Presets: race, gran_fondo (default), training, touring
    - Use "custom" with ride_type_params for full control
    """

    course_id: int
    bike_id: int | None = None  # if None, use defaults
    rider_weight_kg: float | None = None  # if None, use user.weight_kg
    gear_weight_kg: float | None = None  # clothing, shoes, bottles, etc. (default 3.0 kg)
    ftp_watts: int = 250
    cp_watts: int | None = None  # if None, estimate from FTP
    w_prime_joules: int | None = None  # if None, use default 20kJ
    target_intensity: float = 0.85
    target_time_s: float | None = None  # if set, optimizer calculates watts to hit this time
    use_optimizer: bool = False  # heuristic by default
    name: str | None = None
    # CdA/Crr overrides - if both set, use these instead of bike data
    override_cda: float | None = None
    override_crr: float | None = None
    # Weather/conditions for race day
    target_date: date | None = None  # Event date for forecast
    target_hour: int = 10  # Hour of day for forecast (0-23)
    wind_override_speed_mps: float | None = None  # Manual wind speed override
    wind_override_direction_deg: float | None = None  # Manual wind direction override
    max_descent_speed_mps: float | None = None  # Cap descent speed (e.g., 18 m/s = 65 km/h)
    # Ride type - controls descent aggressiveness and stop time estimation
    ride_type: RideTypePreset = "gran_fondo"
    ride_type_params: RideTypeParams | None = None  # Required if ride_type="custom"


@dataclass
class GeneratePlanResult:
    """Result of race plan generation."""

    plan: RacePlan
    comparison: dict  # constant vs heuristic vs optimized times
    warnings: list[str]
    aero_selection: dict | None = None  # CdA/Crr selection metadata
    weather_conditions: dict | None = None  # Forecast conditions used
    forecast_stale: bool = False  # True if no forecast available (calm conditions used)


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
        pacing_coefficients_repo: PacingCoefficientsRepo | None = None,
    ) -> None:
        self._course_repo = course_repo
        self._bike_repo = bike_repo
        self._user_repo = user_repo
        self._plan_repo = plan_repo
        self._pacing_coefficients_repo = pacing_coefficients_repo

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

        # Resolve ride type parameters
        ride_type_params = resolve_ride_type_params(
            request.ride_type,
            request.ride_type_params,
        )

        # 2. Load bike and select CdA/Crr using smart selection
        bike_weight_kg: float | None = None
        bike_id: int | None = None
        bike_aero_data: BikeAeroData | None = None

        if request.bike_id is not None:
            bike = await self._bike_repo.get_by_id(request.bike_id, user_id)
            if bike is None:
                warnings.append(f"Bike {request.bike_id} not found, using defaults")
            else:
                bike_id = bike.id
                bike_weight_kg = float(bike.weight_kg) if bike.weight_kg else None
                bike_aero_data = BikeAeroData(
                    bike_type=bike.bike_type,
                    cda=float(bike.cda) if bike.cda else None,
                    crr=float(bike.crr) if bike.crr else None,
                    cda_source=bike.cda_source,
                    crr_source=bike.crr_source,
                    estimated_cda_avg=float(bike.estimated_cda_avg) if bike.estimated_cda_avg else None,
                    estimated_crr_avg=float(bike.estimated_crr_avg) if bike.estimated_crr_avg else None,
                    estimated_cda_stddev=float(bike.estimated_cda_stddev) if bike.estimated_cda_stddev else None,
                    estimated_crr_stddev=float(bike.estimated_crr_stddev) if bike.estimated_crr_stddev else None,
                    aero_sample_count=bike.aero_sample_count,
                )

        # Select CdA/Crr using priority: user override > calibrated > estimated > manual > defaults
        aero_selection = select_aero_params(
            bike=bike_aero_data,
            user_cda=request.override_cda,
            user_crr=request.override_crr,
            bike_type_fallback="road",
        )

        cda = aero_selection.cda
        crr = aero_selection.crr

        # Add warning/note about aero source
        if aero_selection.source == AeroSource.DEFAULT:
            warnings.append(aero_selection.confidence_note or "Using default CdA/Crr values")
        elif aero_selection.confidence_note:
            warnings.append(f"CdA/Crr: {aero_selection.confidence_note}")

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

        # Total mass includes bike + gear (bottles, clothes, shoes, etc.)
        # Gear weight is typically 2-4 kg for road cycling
        gear_weight_kg = request.gear_weight_kg if request.gear_weight_kg is not None else 3.0
        total_mass_kg = rider_weight_kg + (bike_weight_kg or 8.0) + gear_weight_kg

        # 4. Fetch weather conditions if target_date is set
        forecast_conditions: ForecastConditions
        conditions_fetched_at: datetime | None = None
        weather_conditions_dict: dict | None = None
        forecast_stale = False  # True if calm conditions used (no real forecast)

        if request.target_date is not None:
            # Get course location for weather fetch
            course_lat = course.start_lat
            course_lon = course.start_lon

            if course_lat is not None and course_lon is not None:
                forecast_result = await fetch_race_day_forecast(
                    lat=course_lat,
                    lon=course_lon,
                    target_date=request.target_date,
                    target_hour=request.target_hour,
                )
                forecast_conditions = forecast_result.conditions or get_calm_conditions()
                conditions_fetched_at = datetime.now(UTC)
                forecast_stale = not forecast_result.forecast_available

                if forecast_result.error_message:
                    warnings.append(f"Weather: {forecast_result.error_message}")
                elif forecast_result.forecast_available:
                    warnings.append(
                        f"Forecast for {request.target_date}: {forecast_conditions.temperature_c:.0f}°C, "
                        f"wind {forecast_conditions.wind_speed_mps:.1f} m/s"
                    )
            else:
                forecast_conditions = get_calm_conditions()
                forecast_stale = True
                warnings.append("Course has no location data, using calm conditions")
        else:
            forecast_conditions = get_calm_conditions()
            # No target_date means no staleness concept applies

        # Apply wind overrides if provided
        if request.wind_override_speed_mps is not None and request.wind_override_direction_deg is not None:
            forecast_conditions = ForecastConditions(
                temperature_c=forecast_conditions.temperature_c,
                wind_speed_mps=request.wind_override_speed_mps,
                wind_direction_deg=request.wind_override_direction_deg,
                pressure_hpa=forecast_conditions.pressure_hpa,
                humidity_pct=forecast_conditions.humidity_pct,
                air_density=forecast_conditions.air_density,
            )
            warnings.append(
                f"Using wind override: {request.wind_override_speed_mps:.1f} m/s "
                f"from {request.wind_override_direction_deg:.0f}°"
            )

        weather_conditions_dict = forecast_conditions.to_dict()

        # 5. Build parameters
        rider_params = RiderParams(mass_kg=total_mass_kg, cda=cda, crr=crr)
        # Use forecast air density instead of default
        env_params = EnvironmentParams(air_density=forecast_conditions.air_density)

        # 5b. Build per-segment environment params for wind-adjusted pacing
        # Only calculate headwind if we have meaningful wind speed
        segment_env_params: list[EnvironmentParams] | None = None
        if forecast_conditions.wind_speed_mps > 0.1:  # Ignore negligible wind
            segment_env_params = []
            for seg in segments:
                if seg.bearing_deg is not None:
                    headwind = calculate_headwind(
                        wind_speed_mps=forecast_conditions.wind_speed_mps,
                        wind_direction_deg=forecast_conditions.wind_direction_deg,
                        course_bearing_deg=seg.bearing_deg,
                    )
                else:
                    # No bearing data, assume no wind effect
                    headwind = 0.0
                segment_env_params.append(
                    EnvironmentParams(
                        air_density=forecast_conditions.air_density,
                        wind_speed_mps=headwind,
                    )
                )

        # Estimate CP and W' if not provided
        ftp = request.ftp_watts
        cp = request.cp_watts if request.cp_watts else int(ftp * 0.95)
        w_prime = request.w_prime_joules if request.w_prime_joules else 20000

        if request.cp_watts is None:
            warnings.append(f"CP estimated as 95% of FTP: {cp}W")
        if request.w_prime_joules is None:
            warnings.append("W' using default: 20kJ")

        # Load personalized pacing coefficients (if available)
        pacing_coefficients: PacingCoefficients | None = None
        if self._pacing_coefficients_repo is not None:
            pacing_coefficients = await self._pacing_coefficients_repo.get_for_user_bike(user_id, bike_id=bike_id)

        # 6. Generate pacing plan
        # Three modes:
        # A) Target time mode: optimize power to hit specific finish time
        # B) Optimizer mode: optimize power to minimize time given energy budget
        # C) Heuristic mode: grade-based power targets

        if request.target_time_s is not None:
            # Mode A: Target time - find power to achieve specific finish time
            # If stop_pct > 0, the target_time includes stops.
            # Physics calculation should target: net_riding_time = target_time / stop_factor
            net_target_time_s = request.target_time_s / ride_type_params.stop_factor

            optimized = optimize_pacing_for_time(
                segments=segments,
                rider_ftp=ftp,
                rider_cp=cp,
                rider_w_prime=w_prime,
                target_time_s=net_target_time_s,
                rider_params=rider_params,
                env_params=env_params,
                segment_env_params=segment_env_params,
                max_descent_speed_mps=request.max_descent_speed_mps,
            )

            # Apply stop factor to get total time including stops
            riding_time_s = optimized.total_time_s
            total_time_s = riding_time_s * ride_type_params.stop_factor
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
            optimization_method = "time_targeted"

            # Comparison: show energy savings vs constant power
            comparison = {
                "target_time_s": request.target_time_s,
                "achieved_time_s": total_time_s,
                "riding_time_s": riding_time_s,
                "stop_pct": ride_type_params.stop_pct,
                "energy_saving_vs_constant_pct": optimized.improvement_vs_constant_pct,
            }

            if not optimized.converged:
                warnings.append("Optimizer did not fully converge - results may be approximate")

        elif request.use_optimizer:
            # Mode B: Energy budget optimization
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
                segment_env_params=segment_env_params,
                max_descent_speed_mps=request.max_descent_speed_mps,
            )

            # Apply stop factor to get total time including stops
            riding_time_s = optimized.total_time_s
            total_time_s = riding_time_s * ride_type_params.stop_factor
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

            # Calculate comparison (times include stop factor)
            heuristic_riding_time = (
                riding_time_s / (1 - optimized.improvement_vs_heuristic_pct / 100)
                if optimized.improvement_vs_heuristic_pct < 100
                else riding_time_s
            )
            comparison = {
                "heuristic_time_s": heuristic_riding_time * ride_type_params.stop_factor,
                "optimized_time_s": total_time_s,
                "riding_time_s": riding_time_s,
                "stop_pct": ride_type_params.stop_pct,
                "improvement_vs_heuristic_pct": optimized.improvement_vs_heuristic_pct,
                "improvement_vs_constant_pct": optimized.improvement_vs_constant_pct,
            }
        else:
            # Mode C: Terrain-adapted pacing with continuous grade-based power targets
            # Uses personalized coefficients if available, otherwise global defaults
            # When elevation_profile is available, uses fine-grained (~25m) pacing
            # for accurate speed predictions — with per-point wind decomposition
            # and altitude-scaled air density (ADR 0004 Phase B)
            heuristic = generate_terrain_adapted_pacing(
                segments=segments,
                rider_ftp=ftp,
                target_intensity=request.target_intensity,
                rider_params=rider_params,
                env_params=env_params,
                segment_env_params=segment_env_params,
                max_descent_speed_mps=request.max_descent_speed_mps,
                coefficients=pacing_coefficients,
                elevation_profile=course.elevation_profile,
                ride_type=ride_type_params.ride_type_for_curvature,
                descent_aggressiveness=ride_type_params.descent_aggressiveness,
                wind_speed_mps=forecast_conditions.wind_speed_mps,
                wind_direction_deg=forecast_conditions.wind_direction_deg,
            )

            # Apply stop factor to get total time including stops
            riding_time_s = heuristic.total_time_s
            total_time_s = riding_time_s * ride_type_params.stop_factor
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

            # Comparison: constant power baseline (times include stop factor)
            constant_power = ftp * request.target_intensity
            constant_riding_time_s = sum(
                seg.length_m
                / max(0.1, self._speed_at_power(constant_power, seg.avg_grade_pct, rider_params, env_params))
                for seg in segments
            )
            constant_time_s = constant_riding_time_s * ride_type_params.stop_factor
            improvement_vs_constant = (
                (constant_time_s - total_time_s) / constant_time_s * 100 if constant_time_s > 0 else 0
            )

            comparison = {
                "constant_time_s": constant_time_s,
                "heuristic_time_s": total_time_s,
                "riding_time_s": riding_time_s,
                "stop_pct": ride_type_params.stop_pct,
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
            max_descent_speed_mps=request.max_descent_speed_mps,
            # Ride type configuration
            ride_type=request.ride_type,
            descent_aggressiveness=ride_type_params.descent_aggressiveness,
            stop_pct=ride_type_params.stop_pct,
            # Results
            total_time_s=total_time_s,
            total_distance_m=total_distance_m,
            avg_power_w=avg_power_w,
            normalized_power_w=normalized_power_w,
            intensity_factor=Decimal(str(round(intensity_factor, 2))),
            segment_targets=segment_targets,
            wbal_min=wbal_min,
            wbal_min_distance_m=wbal_min_distance_m,
            # Weather/conditions
            target_date=request.target_date,
            target_conditions=weather_conditions_dict,
            conditions_fetched_at=conditions_fetched_at,
            wind_override_speed_mps=request.wind_override_speed_mps,
            wind_override_direction_deg=request.wind_override_direction_deg,
        )

        saved_plan = await self._plan_repo.save(plan)

        # Build aero selection metadata for response
        aero_selection_dict = {
            "cda": aero_selection.cda,
            "crr": aero_selection.crr,
            "source": aero_selection.source.value,
            "confidence_note": aero_selection.confidence_note,
        }
        if aero_selection.cda_stddev is not None:
            aero_selection_dict["cda_stddev"] = aero_selection.cda_stddev
        if aero_selection.crr_stddev is not None:
            aero_selection_dict["crr_stddev"] = aero_selection.crr_stddev
        if aero_selection.sample_count is not None:
            aero_selection_dict["sample_count"] = aero_selection.sample_count

        return GeneratePlanResult(
            plan=saved_plan,
            comparison=comparison,
            warnings=warnings,
            aero_selection=aero_selection_dict,
            weather_conditions=weather_conditions_dict,
            forecast_stale=forecast_stale,
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
                    bearing_deg=seg.get("bearing_deg"),
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
