"""Tests for pending_suggestions count in user responses.

The sidebar badge reads user.pending_suggestions; the backend never set
it, so the badge never showed. /api/me, login, and register now include
the count of VISIBLE suggestions (>= threshold, not dismissed).
"""

from unittest.mock import MagicMock

from trainingdash.routers.serializers import user_response


def make_user():
    user = MagicMock()
    user.id = 3
    user.email = "t@example.com"
    user.display_name = "T"
    user.avatar_path = None
    user.is_admin = False
    user.is_approved = True
    user.unit_system = "metric"
    user.sync_hour = 2
    user.date_of_birth = None
    user.weight_kg = None
    user.height_cm = None
    user.gender = None
    user.power_zone_percentages = None
    user.hr_zone_percentages = None
    user.hr_derived_power_enabled = False
    user.map_tile_style = "osm"
    return user


class TestUserResponse:
    def test_includes_pending_suggestions(self):

        response = user_response(make_user(), pending_suggestions=4)
        assert response["pending_suggestions"] == 4

    def test_defaults_to_zero_when_not_provided(self):

        response = user_response(make_user())
        assert response["pending_suggestions"] == 0
