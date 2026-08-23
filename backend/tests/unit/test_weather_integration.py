"""Unit tests for Open-Meteo weather integration.

Tests cover:
- Successful weather fetch and parsing
- Error handling (timeout, HTTP errors, parse errors)
- Wind speed conversion (km/h to m/s)
- Air density calculation
- Hour index finding
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, Mock, patch

import httpx
import pytest

from trainingdash.integrations.weather import (
    ARCHIVE_API_URL,
    HourlyWeather,
    _find_closest_hour_index,
    _parse_hourly_response,
    fetch_activity_weather,
)


class TestFetchActivityWeather:
    """Tests for fetch_activity_weather()."""

    @pytest.mark.asyncio
    async def test_fetch_success_returns_hourly_data(self):
        """Successful API response should return parsed hourly weather."""
        mock_response = {
            "hourly": {
                "time": ["2024-06-15T10:00", "2024-06-15T11:00", "2024-06-15T12:00"],
                "temperature_2m": [22.5, 23.0, 24.0],
                "windspeed_10m": [18.0, 14.4, 10.8],  # km/h
                "winddirection_10m": [270, 280, 290],
                "surface_pressure": [1015.0, 1014.5, 1014.0],
                "relativehumidity_2m": [65, 60, 55],
            }
        }

        with patch("trainingdash.integrations.weather.httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_instance

            mock_response_obj = Mock()
            mock_response_obj.json.return_value = mock_response
            mock_response_obj.raise_for_status = Mock()
            mock_instance.get.return_value = mock_response_obj

            result = await fetch_activity_weather(
                lat=47.5,
                lon=8.5,
                start_time=datetime(2024, 6, 15, 10, 30, tzinfo=UTC),
                duration_hours=2,
            )

        assert result.success is True
        assert len(result.hourly_data) == 3
        assert result.lat == 47.5
        assert result.lon == 8.5

        # Check first hour
        first = result.hourly_data[0]
        assert first.hour_offset == 0
        assert first.temperature_c == 22.5
        assert first.wind_speed_mps == pytest.approx(5.0, rel=0.01)  # 18 km/h = 5 m/s
        assert first.wind_direction_deg == 270
        assert first.pressure_hpa == 1015.0
        assert first.humidity_pct == 65

    @pytest.mark.asyncio
    async def test_fetch_timeout_returns_error(self):
        """Timeout should return error result without crashing."""
        with patch("trainingdash.integrations.weather.httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_instance
            mock_instance.get.side_effect = httpx.TimeoutException("Connection timed out")

            result = await fetch_activity_weather(
                lat=47.5,
                lon=8.5,
                start_time=datetime(2024, 6, 15, 10, 0, tzinfo=UTC),
                duration_hours=1,
            )

        assert result.success is False
        assert result.error_message == "API timeout"
        assert result.hourly_data == []

    @pytest.mark.asyncio
    async def test_fetch_http_error_returns_error(self):
        """HTTP error should return error result."""
        with patch("trainingdash.integrations.weather.httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_instance

            mock_response_obj = Mock()
            mock_response_obj.raise_for_status.side_effect = httpx.HTTPStatusError(
                "Server error",
                request=Mock(),
                response=Mock(status_code=500),
            )
            mock_instance.get.return_value = mock_response_obj

            result = await fetch_activity_weather(
                lat=47.5,
                lon=8.5,
                start_time=datetime(2024, 6, 15, 10, 0, tzinfo=UTC),
                duration_hours=1,
            )

        assert result.success is False
        assert "HTTP 500" in result.error_message

    @pytest.mark.asyncio
    async def test_fetch_parse_error_returns_error(self):
        """Invalid JSON structure should return error result."""
        mock_response = {"invalid": "structure"}

        with patch("trainingdash.integrations.weather.httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_instance

            mock_response_obj = Mock()
            mock_response_obj.json.return_value = mock_response
            mock_response_obj.raise_for_status = Mock()
            mock_instance.get.return_value = mock_response_obj

            result = await fetch_activity_weather(
                lat=47.5,
                lon=8.5,
                start_time=datetime(2024, 6, 15, 10, 0, tzinfo=UTC),
                duration_hours=1,
            )

        # Should handle gracefully - no hourly data means no data for time range
        assert result.success is False
        assert "No data" in result.error_message

    @pytest.mark.asyncio
    async def test_fetch_naive_datetime_treated_as_utc(self):
        """Naive datetime should be treated as UTC."""
        mock_response = {
            "hourly": {
                "time": ["2024-06-15T10:00"],
                "temperature_2m": [20.0],
                "windspeed_10m": [10.0],
                "winddirection_10m": [180],
                "surface_pressure": [1013.0],
                "relativehumidity_2m": [50],
            }
        }

        with patch("trainingdash.integrations.weather.httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_instance

            mock_response_obj = Mock()
            mock_response_obj.json.return_value = mock_response
            mock_response_obj.raise_for_status = Mock()
            mock_instance.get.return_value = mock_response_obj

            # Pass naive datetime
            result = await fetch_activity_weather(
                lat=47.5,
                lon=8.5,
                start_time=datetime(2024, 6, 15, 10, 0),  # No timezone
                duration_hours=1,
            )

        assert result.success is True


class TestParseHourlyResponse:
    """Tests for _parse_hourly_response()."""

    def test_parse_valid_response(self):
        """Valid response should be parsed correctly."""
        data = {
            "hourly": {
                "time": ["2024-06-15T08:00", "2024-06-15T09:00", "2024-06-15T10:00"],
                "temperature_2m": [18.0, 19.0, 20.0],
                "windspeed_10m": [7.2, 10.8, 14.4],  # km/h
                "winddirection_10m": [90, 100, 110],
                "surface_pressure": [1020.0, 1019.0, 1018.0],
                "relativehumidity_2m": [70, 65, 60],
            }
        }

        start_utc = datetime(2024, 6, 15, 9, 0, tzinfo=UTC)
        result = _parse_hourly_response(data, start_utc, duration_hours=1)

        assert len(result) == 2  # 09:00 and 10:00
        assert result[0].hour_offset == 0
        assert result[0].temperature_c == 19.0
        assert result[0].wind_speed_mps == pytest.approx(3.0, rel=0.01)  # 10.8 km/h
        assert result[1].hour_offset == 1
        assert result[1].temperature_c == 20.0

    def test_parse_handles_missing_values_with_defaults(self):
        """Missing values should use sensible defaults."""
        data = {
            "hourly": {
                "time": ["2024-06-15T10:00"],
                "temperature_2m": [None],
                "windspeed_10m": [None],
                "winddirection_10m": [None],
                "surface_pressure": [None],
                "relativehumidity_2m": [None],
            }
        }

        start_utc = datetime(2024, 6, 15, 10, 0, tzinfo=UTC)
        result = _parse_hourly_response(data, start_utc, duration_hours=0)

        assert len(result) == 1
        # Check defaults
        assert result[0].temperature_c == 15.0  # Default temp
        assert result[0].wind_speed_mps == 0.0  # Default wind
        assert result[0].wind_direction_deg == 0.0
        assert result[0].pressure_hpa == 1013.25  # Sea level pressure
        assert result[0].humidity_pct == 50.0

    def test_parse_empty_response_returns_empty(self):
        """Empty hourly data should return empty list."""
        data = {"hourly": {"time": []}}
        start_utc = datetime(2024, 6, 15, 10, 0, tzinfo=UTC)
        result = _parse_hourly_response(data, start_utc, duration_hours=1)
        assert result == []

    def test_parse_calculates_air_density(self):
        """Air density should be pre-calculated from temp/pressure/humidity."""
        data = {
            "hourly": {
                "time": ["2024-06-15T10:00"],
                "temperature_2m": [25.0],  # 25°C
                "windspeed_10m": [0.0],
                "winddirection_10m": [0],
                "surface_pressure": [1010.0],
                "relativehumidity_2m": [50],
            }
        }

        start_utc = datetime(2024, 6, 15, 10, 0, tzinfo=UTC)
        result = _parse_hourly_response(data, start_utc, duration_hours=0)

        # At 25°C, 1010 hPa, 50% humidity, air density should be ~1.17 kg/m³
        assert 1.15 < result[0].air_density < 1.20


class TestFindClosestHourIndex:
    """Tests for _find_closest_hour_index()."""

    def test_find_exact_match(self):
        """Should find exact hour match."""
        times = ["2024-06-15T08:00", "2024-06-15T09:00", "2024-06-15T10:00"]
        target = datetime(2024, 6, 15, 9, 0, tzinfo=UTC)
        result = _find_closest_hour_index(times, target)
        assert result == 1

    def test_find_closest_when_between_hours(self):
        """Should find closest hour when target is between hours."""
        times = ["2024-06-15T08:00", "2024-06-15T09:00", "2024-06-15T10:00"]
        # 09:20 should match 09:00
        target = datetime(2024, 6, 15, 9, 20, tzinfo=UTC)
        result = _find_closest_hour_index(times, target)
        assert result == 1

    def test_returns_none_when_too_far(self):
        """Should return None if closest hour is > 2 hours away."""
        times = ["2024-06-15T08:00", "2024-06-15T09:00"]
        # 14:00 is 5 hours from 09:00
        target = datetime(2024, 6, 15, 14, 0, tzinfo=UTC)
        result = _find_closest_hour_index(times, target)
        assert result is None

    def test_handles_empty_list(self):
        """Should return None for empty times list."""
        result = _find_closest_hour_index([], datetime(2024, 6, 15, 10, 0, tzinfo=UTC))
        assert result is None


class TestWindSpeedConversion:
    """Tests for wind speed km/h to m/s conversion."""

    @pytest.mark.asyncio
    async def test_wind_speed_converted_correctly(self):
        """Wind speed should be converted from km/h to m/s."""
        # 36 km/h = 10 m/s exactly
        mock_response = {
            "hourly": {
                "time": ["2024-06-15T10:00"],
                "temperature_2m": [20.0],
                "windspeed_10m": [36.0],  # 36 km/h
                "winddirection_10m": [180],
                "surface_pressure": [1013.0],
                "relativehumidity_2m": [50],
            }
        }

        with patch("trainingdash.integrations.weather.httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_instance

            mock_response_obj = Mock()
            mock_response_obj.json.return_value = mock_response
            mock_response_obj.raise_for_status = Mock()
            mock_instance.get.return_value = mock_response_obj

            result = await fetch_activity_weather(
                lat=47.5,
                lon=8.5,
                start_time=datetime(2024, 6, 15, 10, 0, tzinfo=UTC),
                duration_hours=0,
            )

        assert result.success is True
        # 36 km/h / 3.6 = 10 m/s
        assert result.hourly_data[0].wind_speed_mps == pytest.approx(10.0, rel=0.001)


class TestHourlyWeatherDataclass:
    """Tests for HourlyWeather dataclass."""

    def test_hourly_weather_is_immutable(self):
        """HourlyWeather should be frozen (immutable)."""
        weather = HourlyWeather(
            hour_offset=0,
            temperature_c=20.0,
            wind_speed_mps=5.0,
            wind_direction_deg=180,
            pressure_hpa=1013.0,
            humidity_pct=50.0,
            air_density=1.2,
        )

        with pytest.raises(AttributeError):
            weather.temperature_c = 25.0


# =============================================================================
# Forecast API Tests
# =============================================================================

from datetime import date, timedelta

from trainingdash.integrations.weather import (
    FORECAST_API_URL,
    MAX_FORECAST_DAYS,
    ForecastConditions,
    _parse_forecast_response,
    fetch_race_day_forecast,
    get_calm_conditions,
)


class TestGetCalmConditions:
    """Tests for get_calm_conditions()."""

    def test_returns_calm_conditions(self):
        """Should return conditions with zero wind."""
        calm = get_calm_conditions()

        assert calm.wind_speed_mps == 0.0
        assert calm.wind_direction_deg == 0.0
        assert calm.temperature_c == 20.0
        assert calm.pressure_hpa == 1013.25
        assert calm.humidity_pct == 50.0
        assert 1.15 < calm.air_density < 1.25  # Reasonable air density

    def test_calm_conditions_are_immutable(self):
        """ForecastConditions should be frozen."""
        calm = get_calm_conditions()
        with pytest.raises(AttributeError):
            calm.wind_speed_mps = 5.0


class TestForecastConditions:
    """Tests for ForecastConditions dataclass."""

    def test_to_dict(self):
        """to_dict should create dictionary with all fields."""
        conditions = ForecastConditions(
            temperature_c=25.0,
            wind_speed_mps=5.0,
            wind_direction_deg=180.0,
            pressure_hpa=1010.0,
            humidity_pct=60.0,
            air_density=1.18,
        )
        d = conditions.to_dict()

        assert d["temperature_c"] == 25.0
        assert d["wind_speed_mps"] == 5.0
        assert d["wind_direction_deg"] == 180.0
        assert d["pressure_hpa"] == 1010.0
        assert d["humidity_pct"] == 60.0
        assert d["air_density"] == 1.18

    def test_from_dict(self):
        """from_dict should recreate ForecastConditions."""
        d = {
            "temperature_c": 25.0,
            "wind_speed_mps": 5.0,
            "wind_direction_deg": 180.0,
            "pressure_hpa": 1010.0,
            "humidity_pct": 60.0,
            "air_density": 1.18,
        }
        conditions = ForecastConditions.from_dict(d)

        assert conditions.temperature_c == 25.0
        assert conditions.wind_speed_mps == 5.0
        assert conditions.wind_direction_deg == 180.0

    def test_roundtrip(self):
        """to_dict -> from_dict should preserve all values."""
        original = ForecastConditions(
            temperature_c=18.5,
            wind_speed_mps=3.2,
            wind_direction_deg=270.0,
            pressure_hpa=1020.0,
            humidity_pct=45.0,
            air_density=1.22,
        )
        restored = ForecastConditions.from_dict(original.to_dict())

        assert restored == original


class TestParseForecastResponse:
    """Tests for _parse_forecast_response()."""

    def test_parse_valid_response(self):
        """Should parse valid API response for target hour."""
        data = {
            "hourly": {
                "time": [
                    "2024-09-15T08:00",
                    "2024-09-15T09:00",
                    "2024-09-15T10:00",
                    "2024-09-15T11:00",
                ],
                "temperature_2m": [18.0, 19.0, 20.0, 21.0],
                "windspeed_10m": [10.8, 14.4, 18.0, 21.6],  # km/h
                "winddirection_10m": [90, 100, 110, 120],
                "surface_pressure": [1012.0, 1011.5, 1011.0, 1010.5],
                "relativehumidity_2m": [70, 65, 60, 55],
            }
        }

        result = _parse_forecast_response(data, target_hour=10)

        assert result.temperature_c == 20.0
        assert result.wind_speed_mps == pytest.approx(5.0, rel=0.01)  # 18 km/h -> 5 m/s
        assert result.wind_direction_deg == 110
        assert result.pressure_hpa == 1011.0
        assert result.humidity_pct == 60

    def test_parse_with_missing_hour_falls_back_to_midday(self):
        """Should fall back to midday if target hour not found."""
        data = {
            "hourly": {
                "time": [f"2024-09-15T{h:02d}:00" for h in range(24)],
                "temperature_2m": [15.0 + h * 0.5 for h in range(24)],
                "windspeed_10m": [10.0] * 24,
                "winddirection_10m": [180] * 24,
                "surface_pressure": [1013.0] * 24,
                "relativehumidity_2m": [50] * 24,
            }
        }

        # Request hour 25 (invalid) - should fall back to index 12
        result = _parse_forecast_response(data, target_hour=25)

        # Index 12 = 15.0 + 12 * 0.5 = 21.0
        assert result.temperature_c == 21.0

    def test_parse_raises_on_empty_response(self):
        """Should raise ValueError on empty hourly data."""
        data = {"hourly": {"time": []}}

        with pytest.raises(ValueError, match="No hourly data"):
            _parse_forecast_response(data, target_hour=10)

    def test_wind_speed_converted_from_kmh_to_mps(self):
        """Wind speed should be converted from km/h to m/s."""
        data = {
            "hourly": {
                "time": ["2024-09-15T10:00"],
                "temperature_2m": [20.0],
                "windspeed_10m": [36.0],  # 36 km/h = 10 m/s
                "winddirection_10m": [180],
                "surface_pressure": [1013.0],
                "relativehumidity_2m": [50],
            }
        }

        result = _parse_forecast_response(data, target_hour=10)

        assert result.wind_speed_mps == pytest.approx(10.0, rel=0.001)


class TestFetchRaceDayForecast:
    """Tests for fetch_race_day_forecast()."""

    @pytest.mark.asyncio
    async def test_past_date_returns_calm_conditions(self):
        """Target date in the past should return calm conditions."""
        past_date = date.today() - timedelta(days=5)

        result = await fetch_race_day_forecast(lat=47.5, lon=8.5, target_date=past_date)

        assert result.success is True
        assert result.forecast_available is False
        assert result.conditions.wind_speed_mps == 0.0
        assert "past" in result.error_message.lower()

    @pytest.mark.asyncio
    async def test_far_future_date_returns_calm_conditions(self):
        """Target date beyond forecast range should return calm conditions."""
        far_future = date.today() + timedelta(days=MAX_FORECAST_DAYS + 10)

        result = await fetch_race_day_forecast(lat=47.5, lon=8.5, target_date=far_future)

        assert result.success is True
        assert result.forecast_available is False
        assert result.conditions.wind_speed_mps == 0.0
        assert str(MAX_FORECAST_DAYS) in result.error_message

    @pytest.mark.asyncio
    async def test_fetch_success_returns_forecast(self):
        """Successful API response should return parsed forecast."""
        mock_response = {
            "hourly": {
                "time": ["2024-09-20T10:00"],
                "temperature_2m": [22.0],
                "windspeed_10m": [14.4],  # km/h
                "winddirection_10m": [270],
                "surface_pressure": [1015.0],
                "relativehumidity_2m": [55],
            }
        }

        with patch("trainingdash.integrations.weather.httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_instance

            mock_response_obj = Mock()
            mock_response_obj.json.return_value = mock_response
            mock_response_obj.raise_for_status = Mock()
            mock_instance.get.return_value = mock_response_obj

            target = date.today() + timedelta(days=5)
            result = await fetch_race_day_forecast(lat=47.5, lon=8.5, target_date=target, target_hour=10)

        assert result.success is True
        assert result.forecast_available is True
        assert result.conditions.temperature_c == 22.0
        assert result.conditions.wind_speed_mps == pytest.approx(4.0, rel=0.01)
        assert result.conditions.wind_direction_deg == 270

    @pytest.mark.asyncio
    async def test_timeout_returns_calm_conditions(self):
        """API timeout should return calm conditions with error message."""
        with patch("trainingdash.integrations.weather.httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_instance
            mock_instance.get.side_effect = httpx.TimeoutException("Timeout")

            target = date.today() + timedelta(days=3)
            result = await fetch_race_day_forecast(lat=47.5, lon=8.5, target_date=target)

        assert result.success is False
        assert result.conditions.wind_speed_mps == 0.0
        assert "timeout" in result.error_message.lower()

    @pytest.mark.asyncio
    async def test_http_error_returns_calm_conditions(self):
        """HTTP error should return calm conditions with error message."""
        with patch("trainingdash.integrations.weather.httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_instance

            mock_response = Mock()
            mock_response.status_code = 500
            mock_instance.get.side_effect = httpx.HTTPStatusError(
                "Server Error", request=Mock(), response=mock_response
            )

            target = date.today() + timedelta(days=3)
            result = await fetch_race_day_forecast(lat=47.5, lon=8.5, target_date=target)

        assert result.success is False
        assert result.conditions.wind_speed_mps == 0.0
        assert "500" in result.error_message

    @pytest.mark.asyncio
    async def test_uses_forecast_api_url(self):
        """Should call forecast API, not archive API."""
        mock_response = {
            "hourly": {
                "time": ["2024-09-20T10:00"],
                "temperature_2m": [20.0],
                "windspeed_10m": [10.0],
                "winddirection_10m": [180],
                "surface_pressure": [1013.0],
                "relativehumidity_2m": [50],
            }
        }

        with patch("trainingdash.integrations.weather.httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_instance

            mock_response_obj = Mock()
            mock_response_obj.json.return_value = mock_response
            mock_response_obj.raise_for_status = Mock()
            mock_instance.get.return_value = mock_response_obj

            target = date.today() + timedelta(days=5)
            await fetch_race_day_forecast(lat=47.5, lon=8.5, target_date=target)

            # Verify forecast API was called (not archive)
            call_args = mock_instance.get.call_args
            assert FORECAST_API_URL in str(call_args)
            assert ARCHIVE_API_URL not in str(call_args)
