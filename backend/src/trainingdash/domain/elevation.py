"""Elevation data processing and smoothing.

This module provides utilities for:
1. Smoothing noisy GPS elevation data using Savitzky-Golay filter
2. Calculating air density from altitude using ISA model
3. Fetching DEM (Digital Elevation Model) data from Open-Topo-Data API
"""

import math
from typing import Sequence

import httpx
import numpy as np
from scipy.signal import savgol_filter

from trainingdash.config import settings


# DEM API batch size limit
DEM_BATCH_SIZE = 100


def smooth_elevation(
    elevations: np.ndarray | Sequence[float],
    window_length: int = 11,
    polyorder: int = 2,
) -> np.ndarray:
    """Apply Savitzky-Golay filter to smooth elevation profile.

    The Savitzky-Golay filter is ideal for elevation data because it
    preserves features like peaks and valleys while removing noise.

    Args:
        elevations: Raw elevation values in meters.
        window_length: Filter window size (must be odd). Larger values
            give smoother results. Typically 5-21.
        polyorder: Polynomial order for fitting. Typically 2 (quadratic).
            Must be less than window_length.

    Returns:
        Smoothed elevation array of same length as input.

    Raises:
        ValueError: If window_length is even, less than polyorder+1,
            or larger than the data length.
    """
    elevations = np.asarray(elevations, dtype=np.float64)

    # Handle edge cases
    if len(elevations) == 0:
        return elevations

    if len(elevations) < window_length:
        # Not enough points for the window - use smaller window or return as-is
        if len(elevations) < 3:
            return elevations
        # Use largest odd window that fits
        window_length = len(elevations) if len(elevations) % 2 == 1 else len(elevations) - 1
        if window_length <= polyorder:
            return elevations

    return savgol_filter(elevations, window_length, polyorder)


def air_density_from_altitude(altitude_m: float) -> float:
    """Calculate air density using ISA (International Standard Atmosphere).

    Uses altitude-only model without temperature/pressure inputs.
    This is the standard approach for cycling physics calculations
    when local weather data is not available.

    The ISA model assumes:
    - Sea level temperature: 288.15 K (15°C)
    - Sea level pressure: 101325 Pa
    - Temperature lapse rate: -6.5 K/km in troposphere

    Args:
        altitude_m: Altitude above sea level in meters.
            Valid for troposphere (0 to ~11000m).

    Returns:
        Air density in kg/m³.
        Sea level returns ~1.225 kg/m³.
    """
    # ISA constants
    T0 = 288.15  # Sea level temperature (K)
    P0 = 101325  # Sea level pressure (Pa)
    L = 0.0065  # Temperature lapse rate (K/m)
    R = 287.05  # Specific gas constant for dry air (J/(kg·K))
    g = 9.80665  # Gravitational acceleration (m/s²)

    # Clamp altitude to reasonable range (below stratosphere)
    altitude_m = max(0, min(altitude_m, 11000))

    # Temperature at altitude
    T = T0 - L * altitude_m

    # Pressure at altitude (barometric formula)
    P = P0 * (T / T0) ** (g / (R * L))

    # Density from ideal gas law
    rho = P / (R * T)

    return rho


async def fetch_dem_elevation(
    points: list[tuple[float, float]],  # (lat, lon)
    dataset: str | None = None,
    timeout: float = 30.0,
) -> list[float | None]:
    """Fetch elevation from Open-Topo-Data API.

    Uses DEM (Digital Elevation Model) data which is typically more
    accurate than GPS-recorded elevation, especially for course planning.

    Args:
        points: List of (latitude, longitude) tuples.
        dataset: DEM dataset to use. Defaults to settings.open_topo_data_dataset.
            Options include "mapzen" (global), "ned10m" (US high-res),
            "srtm90m" (global 90m), etc.
        timeout: Request timeout in seconds.

    Returns:
        List of elevation values in meters, same length as input.
        Returns None for points that failed to fetch.

    Note:
        - Batches requests to respect API limits (100 points max)
        - Uses bilinear interpolation for accuracy
        - Gracefully handles API errors by returning None for failed points
    """
    if not points:
        return []

    dataset = dataset or settings.open_topo_data_dataset
    url = f"{settings.open_topo_data_url}/{dataset}"

    results: list[float | None] = []

    async with httpx.AsyncClient(timeout=timeout) as client:
        # Process in batches
        for i in range(0, len(points), DEM_BATCH_SIZE):
            batch = points[i : i + DEM_BATCH_SIZE]

            # Format locations as "lat,lon|lat,lon|..."
            locations = "|".join(f"{lat},{lon}" for lat, lon in batch)

            try:
                response = await client.get(
                    url,
                    params={
                        "locations": locations,
                        "interpolation": "bilinear",
                    },
                )
                response.raise_for_status()

                data = response.json()

                if data.get("status") == "OK":
                    for result in data.get("results", []):
                        elevation = result.get("elevation")
                        results.append(elevation)
                else:
                    # API returned error status - fill with None
                    results.extend([None] * len(batch))

            except (httpx.HTTPError, ValueError, KeyError):
                # Network error or invalid response - fill with None
                results.extend([None] * len(batch))

    return results


def calculate_grade(
    distances: np.ndarray | Sequence[float],
    elevations: np.ndarray | Sequence[float],
    min_distance: float = 10.0,
) -> np.ndarray:
    """Calculate grade (slope) from distance and elevation arrays.

    Args:
        distances: Cumulative distance values in meters.
        elevations: Elevation values in meters (should be smoothed first).
        min_distance: Minimum distance between points for grade calculation.
            Points closer than this will use forward-looking grade.

    Returns:
        Array of grade values as decimals (0.05 = 5% grade).
        Same length as input arrays.
    """
    distances = np.asarray(distances, dtype=np.float64)
    elevations = np.asarray(elevations, dtype=np.float64)

    if len(distances) < 2:
        return np.zeros_like(distances)

    grades = np.zeros(len(distances))

    for i in range(len(distances)):
        if i == 0:
            # First point: use grade to next point
            if len(distances) > 1:
                d_dist = distances[1] - distances[0]
                d_elev = elevations[1] - elevations[0]
                grades[0] = d_elev / d_dist if d_dist >= min_distance else 0.0
        else:
            d_dist = distances[i] - distances[i - 1]
            d_elev = elevations[i] - elevations[i - 1]
            grades[i] = d_elev / d_dist if d_dist >= min_distance else grades[i - 1]

    return grades
