"""Verify geocoding is mocked out in the integration suite (#254)."""
import sys
from pathlib import Path
from unittest import mock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "tests" / "fixtures"))
from generate_fit import make_test_fit  # noqa: E402

from trainingdash.geocoding import GeocodingService  # noqa: E402


@pytest.mark.asyncio
async def test_gps_upload_does_not_call_reverse_geocode(auth_client):
    """A GPS upload must not trigger real reverse geocoding.

    The autouse fixture in conftest patches generate_activity_title so the
    geocoding service is never reached. If the mock is missing, this test
    fails because reverse_geocode (real HTTP + 1s sleeps) gets called.
    """
    with mock.patch.object(GeocodingService, "reverse_geocode") as spy:
        fit_data = make_test_fit(num_records=10)
        response = await auth_client.post(
            "/api/upload",
            files={"file": ("test.fit", fit_data, "application/octet-stream")},
        )
        assert response.status_code in (200, 202)

    spy.assert_not_called()