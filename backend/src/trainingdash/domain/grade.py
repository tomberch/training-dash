"""Grade calculation from elevation profiles.

This module provides utilities for calculating road grade from
smoothed elevation data using distance-based windowing for stability.
"""

from typing import Sequence

import numpy as np


def calculate_grade(
    distances: np.ndarray | Sequence[float],
    elevations: np.ndarray | Sequence[float],
    window_m: float = 50.0,
) -> np.ndarray:
    """Calculate grade at each point using distance-based window.

    Uses forward/backward window expansion to ensure minimum distance
    coverage, avoiding noisy point-to-point grades that result from
    GPS jitter.

    Args:
        distances: Cumulative distance in meters (must be monotonic increasing).
        elevations: Smoothed elevation in meters (same length as distances).
        window_m: Window size in meters for grade calculation. Larger values
            produce smoother grades. Default 50m is good for cycling.

    Returns:
        Grade as decimal at each point (0.05 = 5% grade).
        Same length as input arrays.

    Example:
        >>> distances = np.array([0, 100, 200, 300, 400])
        >>> elevations = np.array([100, 105, 110, 115, 120])
        >>> grades = calculate_grade(distances, elevations, window_m=100)
        >>> # All points have ~5% grade
    """
    distances = np.asarray(distances, dtype=np.float64)
    elevations = np.asarray(elevations, dtype=np.float64)

    n = len(distances)
    if n < 2:
        return np.zeros(n)

    grades = np.zeros(n)
    half_window = window_m / 2

    for i in range(n):
        current_dist = distances[i]

        # Find backward extent (points within half_window behind)
        back_idx = i
        while back_idx > 0 and (current_dist - distances[back_idx - 1]) < half_window:
            back_idx -= 1

        # Find forward extent (points within half_window ahead)
        fwd_idx = i
        while fwd_idx < n - 1 and (distances[fwd_idx + 1] - current_dist) < half_window:
            fwd_idx += 1

        # Ensure we have at least some distance coverage
        # If window is too small, expand to nearest neighbors
        if back_idx == fwd_idx:
            if i > 0:
                back_idx = i - 1
            if i < n - 1:
                fwd_idx = i + 1

        # Calculate grade over the window
        d_dist = distances[fwd_idx] - distances[back_idx]
        d_elev = elevations[fwd_idx] - elevations[back_idx]

        if d_dist > 0:
            grades[i] = d_elev / d_dist
        else:
            grades[i] = 0.0

    return grades


def classify_terrain(grade_pct: float) -> str:
    """Classify terrain type by grade percentage.

    Uses standard cycling terrain classifications.

    Args:
        grade_pct: Grade as percentage (5.0 = 5% grade).

    Returns:
        Terrain classification string:
        - 'steep_descent': < -6%
        - 'descent': -6% to -2%
        - 'flat': -2% to 2%
        - 'false_flat': 2% to 4%
        - 'climb': 4% to 8%
        - 'steep_climb': > 8%
    """
    if grade_pct < -6.0:
        return "steep_descent"
    elif grade_pct < -2.0:
        return "descent"
    elif grade_pct < 2.0:
        return "flat"
    elif grade_pct < 4.0:
        return "false_flat"
    elif grade_pct < 8.0:
        return "climb"
    else:
        return "steep_climb"


def classify_terrain_array(grades: np.ndarray | Sequence[float]) -> list[str]:
    """Classify terrain for an array of grade values.

    Args:
        grades: Array of grade values as decimals (0.05 = 5%).

    Returns:
        List of terrain classification strings, same length as input.
    """
    grades = np.asarray(grades)
    # Convert from decimal to percentage for classification
    return [classify_terrain(g * 100) for g in grades]
