"""Threshold domain logic (pure — no I/O, no SQLAlchemy, no ORM imports).

The I/O (load-by-date, create entries, cache) lives in ``ThresholdRepo``
(``repositories/threshold_repo.py``). This module holds the pure data
shapes and the date-effectiveness rule.
"""

from dataclasses import dataclass
from datetime import date


@dataclass
class ThresholdValues:
    """Threshold values effective at a given date (FTP, LTHR, HRmax)."""

    ftp_watts: int | None = None
    lthr_bpm: int | None = None
    hrmax_bpm: int | None = None
    effective_date: date | None = None


@dataclass
class ThresholdHistoryEntry:
    """One dated threshold entry (a row in the threshold history)."""

    effective_date: date
    ftp_watts: int | None = None
    lthr_bpm: int | None = None
    hrmax_bpm: int | None = None
    source: str = "manual"
    created_at: object | None = None  # datetime, typed as object to avoid datetime import in pure domain


def pick_effective_threshold(
    entries: list[ThresholdHistoryEntry], target_date: date
) -> ThresholdValues:
    """Pick the most recent threshold values effective on ``target_date``.

    For each metric (FTP, LTHR, HRmax), returns the value from the most
    recent entry with ``effective_date <= target_date``. Each metric is
    resolved independently — they may come from different entries.

    Returns ``ThresholdValues`` with all-None fields if no entries are
    effective on or before ``target_date``.
    """
    eligible = [e for e in entries if e.effective_date <= target_date]
    if not eligible:
        return ThresholdValues(effective_date=target_date)

    # Most recent first
    eligible.sort(key=lambda e: e.effective_date, reverse=True)

    ftp = next((e.ftp_watts for e in eligible if e.ftp_watts is not None), None)
    lthr = next((e.lthr_bpm for e in eligible if e.lthr_bpm is not None), None)
    hrmax = next((e.hrmax_bpm for e in eligible if e.hrmax_bpm is not None), None)

    return ThresholdValues(
        ftp_watts=ftp,
        lthr_bpm=lthr,
        hrmax_bpm=hrmax,
        effective_date=target_date,
    )


def compute_default_thresholds(dob: date, weight_kg: float | None) -> dict:
    """
    Compute default threshold values based on age and weight.

    - HRmax: Tanaka formula (208 - 0.7 x age)
    - LTHR: 93% of HRmax
    - FTP: weight x 2.5 (or 200W if no weight)
    """
    today = date.today()
    age = (today - dob).days // 365

    hrmax = int(208 - 0.7 * age)
    lthr = int(hrmax * 0.93)

    if weight_kg is not None and weight_kg > 0:
        ftp = int(float(weight_kg) * 2.5)
    else:
        ftp = 200

    return {"ftp_watts": ftp, "lthr_bpm": lthr, "hrmax_bpm": hrmax}
