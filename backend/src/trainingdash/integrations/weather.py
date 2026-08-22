"""Open-Meteo weather API integration for historical weather data.

Fetches hourly weather data (temperature, wind, pressure, humidity) for
activity locations to enable wind-corrected CdA/Crr estimation.

API: https://open-meteo.com/en/docs/historical-weather-api
Rate limit: 10,000 requests/day (no API key required)

Rate limiting strategy:
- Each activity makes at most one weather request (stored in activity_weather)
- Background job processes activities sequentially (natural throttling)
- Weather data is never re-fetched for activities that already have it
- At typical usage (<100 activities/day), we're well under the limit
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import TYPE_CHECKING

import httpx

from trainingdash.domain.aero_estimation import calculate_air_density

if TYPE_CHECKING:
    from uuid import UUID

logger = logging.getLogger(__name__)

# Open-Meteo Historical Weather API
ARCHIVE_API_URL = "https://archive-api.open-meteo.com/v1/archive"

# Hourly variables we need for aero estimation
HOURLY_VARIABLES = [
    "temperature_2m",
    "windspeed_10m",
    "winddirection_10m",
    "surface_pressure",
    "relativehumidity_2m",
]


@dataclass(frozen=True, slots=True)
class HourlyWeather:
    """Weather data for a single hour.

    Attributes:
        hour_offset: Hours from activity start (0 = first hour)
        temperature_c: Temperature in Celsius
        wind_speed_mps: Wind speed in m/s
        wind_direction_deg: Meteorological direction (where wind comes FROM)
        pressure_hpa: Surface pressure in hPa
        humidity_pct: Relative humidity as percentage (0-100)
        air_density: Pre-calculated air density in kg/m³
    """

    hour_offset: int
    temperature_c: float
    wind_speed_mps: float
    wind_direction_deg: float
    pressure_hpa: float
    humidity_pct: float
    air_density: float


@dataclass(frozen=True, slots=True)
class WeatherFetchResult:
    """Result of weather data fetch.

    Attributes:
        success: Whether fetch succeeded
        hourly_data: List of hourly weather snapshots
        error_message: Error message if fetch failed
        lat: Latitude used for fetch
        lon: Longitude used for fetch
    """

    success: bool
    hourly_data: list[HourlyWeather]
    error_message: str | None = None
    lat: float | None = None
    lon: float | None = None


async def fetch_activity_weather(
    lat: float,
    lon: float,
    start_time: datetime,
    duration_hours: int = 1,
    timeout: float = 15.0,
) -> WeatherFetchResult:
    """Fetch historical weather data for an activity location and time.

    Uses Open-Meteo's historical archive API to get hourly weather data
    covering the activity duration.

    Args:
        lat: Activity start latitude
        lon: Activity start longitude
        start_time: Activity start time (UTC or with timezone)
        duration_hours: Number of hours to fetch (minimum 1)
        timeout: HTTP request timeout in seconds

    Returns:
        WeatherFetchResult with hourly weather data or error message

    Note:
        - Open-Meteo uses UTC internally; timestamps are converted automatically
        - Wind direction is meteorological (direction wind comes FROM)
        - Air density is pre-calculated using temperature, pressure, humidity
    """
    # Ensure we have at least 1 hour
    duration_hours = max(1, duration_hours)

    # Convert to UTC if needed
    if start_time.tzinfo is None:
        start_time = start_time.replace(tzinfo=timezone.utc)
    start_utc = start_time.astimezone(timezone.utc)

    # Open-Meteo needs date range (same day for short activities)
    start_date = start_utc.date()
    # For multi-day activities, extend end date
    end_date = date(
        start_utc.year,
        start_utc.month,
        min(start_utc.day + (duration_hours // 24), 28),  # Crude, but safe
    )
    if end_date.month != start_date.month:
        end_date = start_date  # Stay within month for simplicity

    params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "hourly": ",".join(HOURLY_VARIABLES),
        "timezone": "auto",  # Let API determine timezone from coordinates
    }

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(ARCHIVE_API_URL, params=params)
            response.raise_for_status()
            data = response.json()

    except httpx.TimeoutException:
        logger.warning(f"Weather API timeout for ({lat}, {lon})")
        return WeatherFetchResult(
            success=False,
            hourly_data=[],
            error_message="API timeout",
            lat=lat,
            lon=lon,
        )
    except httpx.HTTPStatusError as e:
        logger.warning(f"Weather API HTTP error for ({lat}, {lon}): {e.response.status_code}")
        return WeatherFetchResult(
            success=False,
            hourly_data=[],
            error_message=f"HTTP {e.response.status_code}",
            lat=lat,
            lon=lon,
        )
    except httpx.HTTPError as e:
        logger.warning(f"Weather API error for ({lat}, {lon}): {e}")
        return WeatherFetchResult(
            success=False,
            hourly_data=[],
            error_message=str(e),
            lat=lat,
            lon=lon,
        )

    # Parse response
    try:
        hourly_data = _parse_hourly_response(data, start_utc, duration_hours)
    except (KeyError, ValueError, TypeError) as e:
        logger.warning(f"Weather API parse error: {e}")
        return WeatherFetchResult(
            success=False,
            hourly_data=[],
            error_message=f"Parse error: {e}",
            lat=lat,
            lon=lon,
        )

    if not hourly_data:
        return WeatherFetchResult(
            success=False,
            hourly_data=[],
            error_message="No data for requested time range",
            lat=lat,
            lon=lon,
        )

    return WeatherFetchResult(
        success=True,
        hourly_data=hourly_data,
        lat=lat,
        lon=lon,
    )


def _parse_hourly_response(
    data: dict,
    start_utc: datetime,
    duration_hours: int,
) -> list[HourlyWeather]:
    """Parse Open-Meteo hourly response into HourlyWeather objects.

    Args:
        data: Raw API response JSON
        start_utc: Activity start time in UTC
        duration_hours: How many hours to extract

    Returns:
        List of HourlyWeather objects for the activity duration
    """
    hourly = data.get("hourly", {})

    times = hourly.get("time", [])
    temps = hourly.get("temperature_2m", [])
    winds = hourly.get("windspeed_10m", [])
    wind_dirs = hourly.get("winddirection_10m", [])
    pressures = hourly.get("surface_pressure", [])
    humidities = hourly.get("relativehumidity_2m", [])

    if not times:
        return []

    # Find the starting hour index
    start_hour_str = start_utc.strftime("%Y-%m-%dT%H:00")
    try:
        start_idx = times.index(start_hour_str)
    except ValueError:
        # Try to find closest hour
        start_idx = _find_closest_hour_index(times, start_utc)
        if start_idx is None:
            return []

    results: list[HourlyWeather] = []

    for hour_offset in range(duration_hours + 1):  # +1 to include end hour
        idx = start_idx + hour_offset
        if idx >= len(times):
            break

        # Get values, with fallbacks for missing data
        temp = temps[idx] if idx < len(temps) and temps[idx] is not None else 15.0
        wind = winds[idx] if idx < len(winds) and winds[idx] is not None else 0.0
        wind_dir = wind_dirs[idx] if idx < len(wind_dirs) and wind_dirs[idx] is not None else 0.0
        pressure = pressures[idx] if idx < len(pressures) and pressures[idx] is not None else 1013.25
        humidity = humidities[idx] if idx < len(humidities) and humidities[idx] is not None else 50.0

        # Convert wind speed from km/h to m/s (Open-Meteo default is km/h)
        wind_mps = wind / 3.6

        # Pre-calculate air density
        air_density = calculate_air_density(temp, pressure, humidity)

        results.append(
            HourlyWeather(
                hour_offset=hour_offset,
                temperature_c=temp,
                wind_speed_mps=wind_mps,
                wind_direction_deg=wind_dir,
                pressure_hpa=pressure,
                humidity_pct=humidity,
                air_density=air_density,
            )
        )

    return results


def _find_closest_hour_index(times: list[str], target: datetime) -> int | None:
    """Find the index of the closest hour to target time."""
    target_ts = target.timestamp()

    closest_idx = None
    closest_diff = float("inf")

    for i, time_str in enumerate(times):
        try:
            hour_dt = datetime.fromisoformat(time_str).replace(tzinfo=timezone.utc)
            diff = abs(hour_dt.timestamp() - target_ts)
            if diff < closest_diff:
                closest_diff = diff
                closest_idx = i
        except ValueError:
            continue

    # Only return if within 2 hours
    if closest_diff > 7200:
        return None

    return closest_idx
