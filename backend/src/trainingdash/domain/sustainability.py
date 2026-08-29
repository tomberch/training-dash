"""Sustainability assessment for pacing plans (ADR 0005 #638).

Every plan carries a Sustainability level:

- green: sustainable for the ride duration.
- yellow: very hard, near the rider's demonstrated limit — achievable,
  but nothing left for mistakes.
- red: beyond capability for the duration. Red plans are STILL generated
  and saved, prominently flagged; only physically impossible requests
  are hard errors (the scale-to-time solver draws that line).

Assessment axes (both must be green for green; the worst wins):

1. Intensity factor (NP/FTP), duration-adjusted: endurance tolerance
   shrinks with duration. Thresholds follow common physiological
   practice for trained riders:
     - < ~2.5h rides: yellow at IF 0.92, red at IF 1.05
     - long rides (>= 5h): yellow at IF 0.80, red at IF 0.90
   interpolated between by duration (log-scale on hours).
2. W'bal depth: how deep the W'bal tank is driven:
     - red at <= 10% of W' remaining (fully spent — beyond capability)
     - yellow at <= 30% of W' remaining (near-limit)
"""

from dataclasses import dataclass

# W'bal depth thresholds (fraction of W' remaining at the plan's minimum)
WBAL_RED_FRACTION = 0.10  # <= 10% of W' left: beyond capability
WBAL_YELLOW_FRACTION = 0.30  # <= 30% left: very hard

# IF thresholds at the anchor durations (hours → (yellow IF, red IF))
_IF_ANCHORS = (
    (2.5, 0.92, 1.05),  # short/half-distance: threshold-ish efforts
    (5.0, 0.80, 0.90),  # long rides: endurance tolerance shrinks
)


@dataclass
class SustainabilityAssessment:
    """A plan's sustainability verdict."""

    level: str  # "green" | "yellow" | "red"
    message: str  # human-readable reason(s)
    intensity_factor: float
    wbal_min_fraction: float  # min W'bal as a fraction of W' [0, 1]
    ride_duration_s: float


def _if_thresholds(ride_duration_s: float) -> tuple[float, float]:
    """Yellow/red IF thresholds for the ride duration.

    Anchored at 2.5h (0.92 / 1.05) and 5h (0.80 / 0.90), interpolated
    log-linearly in hours between anchors; shorter than 2.5h uses the
    first anchor, longer than 5h the second.
    """
    hours = max(ride_duration_s, 1.0) / 3600.0
    import math

    if hours <= _IF_ANCHORS[0][0]:
        return _IF_ANCHORS[0][1], _IF_ANCHORS[0][2]
    if hours >= _IF_ANCHORS[-1][0]:
        return _IF_ANCHORS[-1][1], _IF_ANCHORS[-1][2]

    # log-linear interpolation between the anchors
    (h0, yellow0, red0), (h1, yellow1, red1) = _IF_ANCHORS
    t = (math.log(hours) - math.log(h0)) / (math.log(h1) - math.log(h0))
    yellow = yellow0 + t * (yellow1 - yellow0)
    red = red0 + t * (red1 - red0)
    return yellow, red


def assess_sustainability(
    intensity_factor: float,
    wbal_min_j: float,
    w_prime_j: float,
    ride_duration_s: float,
) -> SustainabilityAssessment:
    """
    Assess a plan's sustainability from its required effort.

    Args:
        intensity_factor: The plan's IF (NP / FTP).
        wbal_min_j: The plan's minimum predicted W'bal (joules).
        w_prime_j: The rider's W' (joules).
        ride_duration_s: The plan's riding time (seconds).

    Returns:
        SustainabilityAssessment with level (green/yellow/red) and a
        message explaining the verdict. Red is still a *plan* — it gets
        generated, saved, and flagged.
    """
    reasons: list[str] = []
    level = "green"

    if_yellow, if_red = _if_thresholds(ride_duration_s)
    hours = ride_duration_s / 3600.0

    if intensity_factor >= if_red:
        level = "red"
        reasons.append(
            f"Sustained IF {intensity_factor:.2f} is above the {hours:.1f}h-ride limit ({if_red:.2f})"
        )
    elif intensity_factor >= if_yellow:
        if level != "red":
            level = "yellow"
        reasons.append(
            f"Sustained IF {intensity_factor:.2f} is very hard for a {hours:.1f}h ride (limit {if_yellow:.2f})"
        )

    # W'bal depth (only when the rider's W' is known and the plan ran it)
    if w_prime_j and w_prime_j > 0 and wbal_min_j is not None and wbal_min_j >= 0:
        fraction = min(wbal_min_j / w_prime_j, 1.0)
        if fraction <= WBAL_RED_FRACTION:
            level = "red"
            reasons.append(f"W'bal driven to {fraction:.0%} of W' (fully spent)")
        elif fraction <= WBAL_YELLOW_FRACTION:
            if level != "red":
                level = "yellow"
            reasons.append(f"W'bal driven deep ({fraction:.0%} of W' remaining)")
    else:
        fraction = 1.0

    message = "; ".join(reasons) if reasons else f"Sustainable: IF {intensity_factor:.2f} over {hours:.1f}h"

    return SustainabilityAssessment(
        level=level,
        message=message,
        intensity_factor=intensity_factor,
        wbal_min_fraction=fraction,
        ride_duration_s=ride_duration_s,
    )