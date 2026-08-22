"""
BuildCalcTrace use case — builds calculation transparency data for an activity.

This use case assembles all the calculation trace data needed by Calc Lab:
- Power and HR zone boundaries from effective thresholds
- W'bal trajectory sampled at regular intervals
- Peak power windows with start/end indices

The trace data enables users to see exactly how metrics were computed
and allows what-if editing in the Calc Lab UI.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from trainingdash.domain.peaks import extract_peak_power_with_index
from trainingdash.domain.thresholds import ThresholdValues
from trainingdash.domain.wbal import compute_wbal_series
from trainingdash.domain.zones import compute_hr_zones, compute_power_zones
from trainingdash.repositories.protocols import RecordRepo


@dataclass(frozen=True, slots=True)
class PeakInfo:
    """Peak power info for peak window computation."""

    duration_seconds: int
    watts: int


@dataclass(frozen=True, slots=True)
class CalcTraceResult:
    """Result of building calculation trace.

    Attributes:
        power_zones: List of power zone boundaries, or None if no FTP.
        hr_zones: List of HR zone boundaries, or None if no LTHR.
        wbal_curve: Sampled W'bal trajectory, or None if no FTP/power data.
        w_prime_joules: W' estimate in joules, or None.
        cp_watts: CP estimate (using FTP) in watts, or None.
        peak_windows: List of peak windows with start/end indices.
    """

    power_zones: list[dict[str, Any]] | None
    hr_zones: list[dict[str, Any]] | None
    wbal_curve: list[dict[str, Any]] | None
    w_prime_joules: int | None
    cp_watts: int | None
    peak_windows: list[dict[str, Any]]


class BuildCalcTrace:
    """
    Use case for building calculation trace data for Calc Lab.

    This use case coordinates:
    - Computing zone boundaries from thresholds
    - Loading activity records for power data
    - Computing W'bal trajectory
    - Finding peak window indices

    Example usage:
        use_case = BuildCalcTrace(record_repo)
        result = await use_case.execute(
            activity_id=activity.id,
            thresholds=thresholds,
            peaks=[PeakInfo(60, 350), PeakInfo(300, 280)],
        )
    """

    # Sample W'bal every N seconds to keep response size reasonable
    WBAL_SAMPLE_INTERVAL_S = 30

    def __init__(self, record_repo: RecordRepo) -> None:
        """Initialize the use case with repository dependencies."""
        self._record_repo = record_repo

    async def execute(
        self,
        activity_id: UUID,
        thresholds: ThresholdValues,
        peaks: list[PeakInfo],
    ) -> CalcTraceResult:
        """
        Build calculation trace for an activity.

        Args:
            activity_id: Activity UUID.
            thresholds: Effective thresholds at activity time.
            peaks: List of peak powers for this activity.

        Returns:
            CalcTraceResult with zone boundaries, W'bal curve, and peak windows.
        """
        # Compute zone boundaries from thresholds
        power_zones = compute_power_zones(thresholds.ftp_watts) if thresholds.ftp_watts else None
        hr_zones = compute_hr_zones(thresholds.lthr_bpm) if thresholds.lthr_bpm else None

        # Load records for W'bal and peak window computation
        records = await self._record_repo.list_for_activity(activity_id)
        power_values = [r.power_w for r in records]

        # Compute W'bal curve
        wbal_curve: list[dict[str, Any]] | None = None
        w_prime_joules: int | None = None
        cp_watts: int | None = None

        if thresholds.ftp_watts and power_values:
            ftp = thresholds.ftp_watts
            w_prime = ftp * 60  # Estimate W' as FTP * 60 joules
            wbal_result = compute_wbal_series(power_values, ftp, w_prime)

            # Sample at regular intervals
            series = wbal_result.get("series", [])
            wbal_curve = []
            for i in range(0, len(series), self.WBAL_SAMPLE_INTERVAL_S):
                wbal_curve.append(
                    {
                        "elapsed_s": i,  # 1Hz data, so index = seconds
                        "wbal_joules": series[i],
                        "wbal_pct": round(series[i] / w_prime * 100, 1) if w_prime > 0 else 0,
                    }
                )

            w_prime_joules = w_prime
            cp_watts = ftp  # Using FTP as CP estimate

        # Compute peak windows
        peak_windows: list[dict[str, Any]] = []
        if power_values:
            for peak in peaks:
                _, start_idx = extract_peak_power_with_index(
                    power_values, peak.duration_seconds, sample_rate_hz=1.0
                )
                if start_idx is not None:
                    peak_windows.append(
                        {
                            "duration_seconds": peak.duration_seconds,
                            "watts": peak.watts,
                            "start_index": start_idx,
                            "end_index": start_idx + peak.duration_seconds - 1,
                        }
                    )

        return CalcTraceResult(
            power_zones=power_zones,
            hr_zones=hr_zones,
            wbal_curve=wbal_curve,
            w_prime_joules=w_prime_joules,
            cp_watts=cp_watts,
            peak_windows=peak_windows,
        )
