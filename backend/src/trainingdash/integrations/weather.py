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

import contextlib
import logging
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import TYPE_CHECKING

import httpx

from trainingdash.domain.aero_estimation import calculate_air_density

if TYPE_CHECKING:
    pass

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
        start_time = start_time.replace(tzinfo=UTC)
    start_utc = start_time.astimezone(UTC)

    # Open-Meteo needs date range (same day for short activities)
    start_date = start_utc.date()
    # For multi-day activities, extend end date
    days_to_add = duration_hours // 24
    end_date = start_date
    if days_to_add > 0:
        try:
            end_date = date(start_utc.year, start_utc.month, start_utc.day + days_to_add)
        except ValueError:
            # Day overflow - just use start_date (weather won't change much)
            end_date = start_date

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
        error_detail = ""
        with contextlib.suppress(TypeError, AttributeError):
            error_detail = f" - {e.response.text[:200]}"
        logger.warning(f"Weather API HTTP error for ({lat}, {lon}): {e.response.status_code}{error_detail}")
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
            hour_dt = datetime.fromisoformat(time_str).replace(tzinfo=UTC)
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


# =============================================================================
# Weather Forecast API (for race planning)
# =============================================================================

# Open-Meteo Forecast API (up to 16 days ahead)
FORECAST_API_URL = "https://api.open-meteo.com/v1/forecast"

# Maximum days ahead that forecast is available
MAX_FORECAST_DAYS = 16


@dataclass(frozen=True, slots=True)
class ForecastConditions:
    """Weather conditions for a specific date/time.

    Used for race day predictions. Includes pre-calculated air density.

    Attributes:
        temperature_c: Temperature in Celsius
        wind_speed_mps: Wind speed in m/s
        wind_direction_deg: Meteorological direction (where wind comes FROM)
        pressure_hpa: Surface pressure in hPa
        humidity_pct: Relative humidity as percentage (0-100)
        air_density: Pre-calculated air density in kg/m³
    """

    temperature_c: float
    wind_speed_mps: float
    wind_direction_deg: float
    pressure_hpa: float
    humidity_pct: float
    air_density: float

    def to_dict(self) -> dict:
        """Convert to dictionary for JSONB storage."""
        return {
            "temperature_c": self.temperature_c,
            "wind_speed_mps": self.wind_speed_mps,
            "wind_direction_deg": self.wind_direction_deg,
            "pressure_hpa": self.pressure_hpa,
            "humidity_pct": self.humidity_pct,
            "air_density": self.air_density,
        }

    @classmethod
    def from_dict(cls, data: dict) -> ForecastConditions:
        """Create from dictionary (JSONB storage)."""
        return cls(
            temperature_c=data["temperature_c"],
            wind_speed_mps=data["wind_speed_mps"],
            wind_direction_deg=data["wind_direction_deg"],
            pressure_hpa=data["pressure_hpa"],
            humidity_pct=data["humidity_pct"],
            air_density=data["air_density"],
        )


@dataclass(frozen=True, slots=True)
class ForecastResult:
    """Result of weather forecast fetch.

    Attributes:
        success: Whether fetch succeeded
        conditions: Forecast conditions for the target date
        error_message: Error message if fetch failed
        forecast_available: Whether forecast data is available for the date
    """

    success: bool
    conditions: ForecastConditions | None
    error_message: str | None = None
    forecast_available: bool = True


def get_calm_conditions() -> ForecastConditions:
    """Return calm/default conditions for conservative race planning.

    Used when:
    - No target date is set
    - Target date is beyond forecast range
    - Forecast fetch fails

    Returns conditions with zero wind for conservative power estimates.
    """
    return ForecastConditions(
        temperature_c=20.0,  # Mild temperature
        wind_speed_mps=0.0,  # No wind (conservative)
        wind_direction_deg=0.0,
        pressure_hpa=1013.25,  # Sea level pressure
        humidity_pct=50.0,  # Moderate humidity
        air_density=calculate_air_density(20.0, 1013.25, 50.0),
    )


async def fetch_race_day_forecast(
    lat: float,
    lon: float,
    target_date: date,
    target_hour: int = 10,  # Default to mid-morning start
    timeout: float = 15.0,
) -> ForecastResult:
    """Fetch weather forecast for a race day.

    Uses Open-Meteo forecast API for dates within 16 days,
    returns calm conditions for dates further out.

    Args:
        lat: Course location latitude
        lon: Course location longitude
        target_date: Date of the race/event
        target_hour: Hour of day for forecast (0-23, local time)
        timeout: HTTP request timeout in seconds

    Returns:
        ForecastResult with conditions or error message
    """
    today = date.today()
    days_ahead = (target_date - today).days

    # Check if date is in the past
    if days_ahead < 0:
        return ForecastResult(
            success=True,
            conditions=get_calm_conditions(),
            error_message="Target date is in the past, using calm conditions",
            forecast_available=False,
        )

    # Check if date is beyond forecast range
    if days_ahead > MAX_FORECAST_DAYS:
        return ForecastResult(
            success=True,
            conditions=get_calm_conditions(),
            error_message=f"Target date is {days_ahead} days ahead (max {MAX_FORECAST_DAYS}), using calm conditions",
            forecast_available=False,
        )

    # Fetch forecast from Open-Meteo
    params = {
        "latitude": lat,
        "longitude": lon,
        "hourly": ",".join(HOURLY_VARIABLES),
        "start_date": target_date.isoformat(),
        "end_date": target_date.isoformat(),
        "timezone": "auto",
    }

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(FORECAST_API_URL, params=params)
            response.raise_for_status()
            data = response.json()

    except httpx.TimeoutException:
        logger.warning(f"Forecast API timeout for ({lat}, {lon})")
        return ForecastResult(
            success=False,
            conditions=get_calm_conditions(),
            error_message="API timeout, using calm conditions",
        )
    except httpx.HTTPStatusError as e:
        logger.warning(f"Forecast API HTTP error: {e.response.status_code}")
        return ForecastResult(
            success=False,
            conditions=get_calm_conditions(),
            error_message=f"HTTP {e.response.status_code}, using calm conditions",
        )
    except httpx.HTTPError as e:
        logger.warning(f"Forecast API error: {e}")
        return ForecastResult(
            success=False,
            conditions=get_calm_conditions(),
            error_message=str(e),
        )

    # Parse response
    try:
        conditions = _parse_forecast_response(data, target_hour)
        return ForecastResult(
            success=True,
            conditions=conditions,
        )
    except (KeyError, ValueError, IndexError) as e:
        logger.warning(f"Forecast parse error: {e}")
        return ForecastResult(
            success=False,
            conditions=get_calm_conditions(),
            error_message=f"Parse error: {e}",
        )


def _parse_forecast_response(data: dict, target_hour: int) -> ForecastConditions:
    """Parse Open-Meteo forecast response for a specific hour.

    Args:
        data: Raw API response JSON
        target_hour: Hour of day to extract (0-23)

    Returns:
        ForecastConditions for the target hour

    Raises:
        ValueError: If data is missing or invalid
    """
    hourly = data.get("hourly", {})

    times = hourly.get("time", [])
    temps = hourly.get("temperature_2m", [])
    winds = hourly.get("windspeed_10m", [])
    wind_dirs = hourly.get("winddirection_10m", [])
    pressures = hourly.get("surface_pressure", [])
    humidities = hourly.get("relativehumidity_2m", [])

    if not times:
        raise ValueError("No hourly data in response")

    # Find the target hour index
    # Times are in format "2024-06-15T10:00"
    target_idx = None
    for i, time_str in enumerate(times):
        if f"T{target_hour:02d}:00" in time_str:
            target_idx = i
            break

    if target_idx is None:
        # Fall back to midday if target hour not found
        target_idx = min(12, len(times) - 1)

    # Extract values with defaults
    temp = temps[target_idx] if target_idx < len(temps) and temps[target_idx] is not None else 20.0
    wind = winds[target_idx] if target_idx < len(winds) and winds[target_idx] is not None else 0.0
    wind_dir = wind_dirs[target_idx] if target_idx < len(wind_dirs) and wind_dirs[target_idx] is not None else 0.0
    pressure = pressures[target_idx] if target_idx < len(pressures) and pressures[target_idx] is not None else 1013.25
    humidity = humidities[target_idx] if target_idx < len(humidities) and humidities[target_idx] is not None else 50.0

    # Convert wind speed from km/h to m/s
    wind_mps = wind / 3.6

    # Calculate air density
    air_density = calculate_air_density(temp, pressure, humidity)

    return ForecastConditions(
        temperature_c=temp,
        wind_speed_mps=wind_mps,
        wind_direction_deg=wind_dir,
        pressure_hpa=pressure,
        humidity_pct=humidity,
        air_density=air_density,
    )
