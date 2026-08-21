"""Open-Topo-Data integration for DEM elevation data.

Uses the Open-Topo-Data API to fetch Digital Elevation Model (DEM) data
which is typically more accurate than GPS-recorded elevation.
"""

import httpx

from trainingdash.config import settings


# DEM API batch size limit
DEM_BATCH_SIZE = 100


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
