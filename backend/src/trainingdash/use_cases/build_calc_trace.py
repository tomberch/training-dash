"""
BuildCalcTrace use case — builds calculation transparency data for an activity.

This use case assembles all the calculation trace data needed by Calc Lab:
- Power and HR zone boundaries from effective thresholds
- W'bal trajectory sampled at regular intervals
- Peak power windows with start/end indices
- Zone time distribution

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
from trainingdash.domain.zones import compute_hr_zones, compute_power_zones, compute_zone_times
from trainingdash.repositories.protocols import RecordRepo


@dataclass(frozen=True, slots=True)
class PeakInfo:
    """Peak power info for peak window computation."""

    duration_seconds: int
    watts: int


@dataclass(frozen=True, slots=True)
class WhatIfParams:
    """Parameters for what-if recalculation.
    
    All fields are optional - None means use the effective threshold value.
    """

    ftp: int | None = None
    lthr: int | None = None
    cp: int | None = None
    w_prime: int | None = None


@dataclass(frozen=True, slots=True)
class CalcTraceResult:
    """Result of building calculation trace.

    Attributes:
        power_zones: List of power zone boundaries, or None if no FTP.
        hr_zones: List of HR zone boundaries, or None if no LTHR.
        power_zone_times: Time in seconds spent in each power zone, or None.
        hr_zone_times: Time in seconds spent in each HR zone, or None.
        wbal_curve: Sampled W'bal trajectory, or None if no FTP/power data.
        w_prime_joules: W' in joules, or None.
        cp_watts: CP in watts, or None.
        peak_windows: List of peak windows with start/end indices.
    """

    power_zones: list[dict[str, Any]] | None
    hr_zones: list[dict[str, Any]] | None
    power_zone_times: dict[int, int] | None
    hr_zone_times: dict[int, int] | None
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
    - Computing zone time distribution

    Example usage:
        use_case = BuildCalcTrace(record_repo)
        result = await use_case.execute(
            activity_id=activity.id,
            thresholds=thresholds,
            peaks=[PeakInfo(60, 350), PeakInfo(300, 280)],
        )
        
        # For what-if:
        result = await use_case.execute(
            activity_id=activity.id,
            thresholds=thresholds,
            peaks=[...],
            what_if=WhatIfParams(ftp=290, cp=270, w_prime=22000),
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
        what_if: WhatIfParams | None = None,
    ) -> CalcTraceResult:
        """
        Build calculation trace for an activity.

        Args:
            activity_id: Activity UUID.
            thresholds: Effective thresholds at activity time.
            peaks: List of peak powers for this activity.
            what_if: Optional what-if parameters to override thresholds.

        Returns:
            CalcTraceResult with zone boundaries, W'bal curve, zone times, and peak windows.
        """
        # Resolve effective values (what-if overrides thresholds)
        ftp = (what_if.ftp if what_if and what_if.ftp else None) or thresholds.ftp_watts
        lthr = (what_if.lthr if what_if and what_if.lthr else None) or thresholds.lthr_bpm
        
        # For W'bal, use what-if CP/W' if provided, else default from FTP
        if what_if and what_if.cp:
            cp = what_if.cp
        else:
            cp = ftp  # Default: CP ≈ FTP
            
        if what_if and what_if.w_prime:
            w_prime = what_if.w_prime
        elif ftp:
            w_prime = ftp * 60  # Default: W' ≈ FTP × 60 joules
        else:
            w_prime = None

        # Compute zone boundaries
        power_zones = compute_power_zones(ftp) if ftp else None
        hr_zones = compute_hr_zones(lthr) if lthr else None

        # Load records for W'bal, zone times, and peak window computation
        records = await self._record_repo.list_for_activity(activity_id)
        power_values = [r.power_w for r in records]
        hr_values = [r.hr_bpm for r in records]

        # Compute zone times
        power_zone_times, hr_zone_times = compute_zone_times(
            power_data=power_values,
            ftp=ftp,
            hr_data=hr_values,
            lthr=lthr,
        )

        # Compute W'bal curve
        wbal_curve: list[dict[str, Any]] | None = None
        w_prime_out: int | None = None
        cp_out: int | None = None

        if cp and w_prime and power_values:
            wbal_result = compute_wbal_series(power_values, cp, w_prime)

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

            w_prime_out = w_prime
            cp_out = cp

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
            power_zone_times=power_zone_times,
            hr_zone_times=hr_zone_times,
            wbal_curve=wbal_curve,
            w_prime_joules=w_prime_out,
            cp_watts=cp_out,
            peak_windows=peak_windows,
        )
