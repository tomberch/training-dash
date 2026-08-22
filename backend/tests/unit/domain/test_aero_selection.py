"""Unit tests for CdA/Crr selection strategy.

Tests the priority order:
1. User override (highest)
2. Bike estimated aggregates
3. Bike manual values
4. Bike type defaults (fallback)
"""

import pytest

from trainingdash.domain.aero_selection import (
    AeroSelection,
    AeroSource,
    BikeAeroData,
    select_aero_params,
)


class TestUserOverride:
    """Tests for user-provided CdA/Crr override."""

    def test_user_override_takes_priority(self):
        """User override should be used when both cda and crr provided."""
        bike = BikeAeroData(
            bike_type="road",
            cda=0.30,
            crr=0.004,
            estimated_cda_avg=0.32,
            estimated_crr_avg=0.005,
            aero_sample_count=10,
        )

        result = select_aero_params(
            bike=bike,
            user_cda=0.28,
            user_crr=0.003,
        )

        assert result.cda == 0.28
        assert result.crr == 0.003
        assert result.source == AeroSource.USER_OVERRIDE
        assert "user-provided" in result.confidence_note.lower()

    def test_partial_override_ignored(self):
        """Partial override (only cda or only crr) should fall through."""
        bike = BikeAeroData(
            bike_type="road",
            cda=0.30,
            crr=0.004,
        )

        # Only cda provided - should use manual values instead
        result = select_aero_params(bike=bike, user_cda=0.28)
        assert result.source == AeroSource.MANUAL
        assert result.cda == 0.30

        # Only crr provided - should use manual values instead
        result = select_aero_params(bike=bike, user_crr=0.003)
        assert result.source == AeroSource.MANUAL
        assert result.crr == 0.004


class TestCalibratedValues:
    """Tests for calibrated values from wind tunnel/velodrome."""

    def test_calibrated_takes_priority_over_estimated(self):
        """Calibrated values should take priority over estimated."""
        bike = BikeAeroData(
            bike_type="road",
            cda=0.25,  # Calibrated value
            crr=0.003,
            cda_source="calibrated",
            crr_source="calibrated",
            estimated_cda_avg=0.32,  # Would normally be used
            estimated_crr_avg=0.005,
            aero_sample_count=10,
        )

        result = select_aero_params(bike=bike)

        assert result.cda == 0.25
        assert result.crr == 0.003
        assert result.source == AeroSource.CALIBRATED
        assert "calibrated" in result.confidence_note.lower()

    def test_calibrated_requires_both_sources(self):
        """Both cda_source and crr_source must be calibrated."""
        # Only CdA is calibrated
        bike = BikeAeroData(
            bike_type="road",
            cda=0.25,
            crr=0.003,
            cda_source="calibrated",
            crr_source="manual",
            estimated_cda_avg=0.32,
            estimated_crr_avg=0.005,
            aero_sample_count=10,
        )

        result = select_aero_params(bike=bike)

        # Should fall through to estimated since not both calibrated
        assert result.source == AeroSource.ESTIMATED

    def test_user_override_still_beats_calibrated(self):
        """User override should still take priority over calibrated."""
        bike = BikeAeroData(
            bike_type="road",
            cda=0.25,
            crr=0.003,
            cda_source="calibrated",
            crr_source="calibrated",
        )

        result = select_aero_params(bike=bike, user_cda=0.28, user_crr=0.004)

        assert result.source == AeroSource.USER_OVERRIDE
        assert result.cda == 0.28
        assert result.crr == 0.004


class TestEstimatedAggregates:
    """Tests for bike estimated aggregates from activity data."""

    def test_estimated_used_when_available(self):
        """Estimated values should be used when sample_count > 0."""
        bike = BikeAeroData(
            bike_type="road",
            cda=0.30,  # Manual value
            crr=0.004,
            estimated_cda_avg=0.32,
            estimated_crr_avg=0.005,
            estimated_cda_stddev=0.01,
            estimated_crr_stddev=0.0005,
            aero_sample_count=10,
        )

        result = select_aero_params(bike=bike)

        assert result.cda == 0.32
        assert result.crr == 0.005
        assert result.source == AeroSource.ESTIMATED
        assert result.cda_stddev == 0.01
        assert result.crr_stddev == 0.0005
        assert result.sample_count == 10

    def test_estimated_skipped_with_zero_samples(self):
        """Should fall through to manual if sample_count is 0."""
        bike = BikeAeroData(
            bike_type="road",
            cda=0.30,
            crr=0.004,
            estimated_cda_avg=0.32,
            estimated_crr_avg=0.005,
            aero_sample_count=0,
        )

        result = select_aero_params(bike=bike)

        assert result.source == AeroSource.MANUAL
        assert result.cda == 0.30

    def test_estimated_skipped_with_none_sample_count(self):
        """Should fall through to manual if sample_count is None."""
        bike = BikeAeroData(
            bike_type="road",
            cda=0.30,
            crr=0.004,
            estimated_cda_avg=0.32,
            estimated_crr_avg=0.005,
            aero_sample_count=None,
        )

        result = select_aero_params(bike=bike)

        assert result.source == AeroSource.MANUAL

    def test_estimated_skipped_with_partial_values(self):
        """Should fall through if estimated values are incomplete."""
        bike = BikeAeroData(
            bike_type="road",
            cda=0.30,
            crr=0.004,
            estimated_cda_avg=0.32,
            estimated_crr_avg=None,  # Missing
            aero_sample_count=10,
        )

        result = select_aero_params(bike=bike)

        assert result.source == AeroSource.MANUAL


class TestManualValues:
    """Tests for bike's manually configured values."""

    def test_manual_used_when_no_estimates(self):
        """Manual values should be used when no estimates available."""
        bike = BikeAeroData(
            bike_type="road",
            cda=0.30,
            crr=0.004,
        )

        result = select_aero_params(bike=bike)

        assert result.cda == 0.30
        assert result.crr == 0.004
        assert result.source == AeroSource.MANUAL
        assert "manually" in result.confidence_note.lower()

    def test_manual_skipped_with_partial_values(self):
        """Should fall through to defaults if manual values incomplete."""
        bike = BikeAeroData(
            bike_type="road",
            cda=0.30,
            crr=None,  # Missing
        )

        result = select_aero_params(bike=bike)

        assert result.source == AeroSource.DEFAULT


class TestDefaults:
    """Tests for bike type defaults."""

    def test_defaults_used_when_no_bike(self):
        """Should use defaults when no bike provided."""
        result = select_aero_params(bike=None)

        assert result.source == AeroSource.DEFAULT
        # Road defaults
        assert result.cda == pytest.approx(0.32, rel=0.1)
        assert result.crr == pytest.approx(0.004, rel=0.1)

    def test_defaults_use_bike_type(self):
        """Should use bike-type-specific defaults."""
        bike = BikeAeroData(bike_type="tt")  # No values set

        result = select_aero_params(bike=bike)

        assert result.source == AeroSource.DEFAULT
        # TT bike has lower CdA
        assert result.cda < 0.30

    def test_fallback_bike_type_used(self):
        """Should use fallback bike type when no bike provided."""
        result = select_aero_params(bike=None, bike_type_fallback="gravel")

        assert result.source == AeroSource.DEFAULT
        assert "gravel" in result.confidence_note.lower()


class TestConfidenceNotes:
    """Tests for confidence note generation."""

    def test_good_sample_count_consistent(self):
        """High sample count with low stddev should show positive note."""
        bike = BikeAeroData(
            bike_type="road",
            estimated_cda_avg=0.32,
            estimated_crr_avg=0.005,
            estimated_cda_stddev=0.01,  # ~3% CV, consistent
            aero_sample_count=15,
        )

        result = select_aero_params(bike=bike)

        assert "15 activities" in result.confidence_note
        assert "consistent" in result.confidence_note.lower()

    def test_limited_sample_count_note(self):
        """Low sample count should recommend more data."""
        bike = BikeAeroData(
            bike_type="road",
            estimated_cda_avg=0.32,
            estimated_crr_avg=0.005,
            estimated_cda_stddev=0.01,
            aero_sample_count=3,
        )

        result = select_aero_params(bike=bike)

        assert "3 activities" in result.confidence_note
        assert "more data" in result.confidence_note.lower()


class TestAeroSelectionDataclass:
    """Tests for AeroSelection dataclass."""

    def test_selection_is_immutable(self):
        """AeroSelection should be frozen."""
        selection = AeroSelection(
            cda=0.32,
            crr=0.005,
            source=AeroSource.ESTIMATED,
        )

        with pytest.raises(AttributeError):
            selection.cda = 0.30

    def test_optional_fields_default_to_none(self):
        """Optional fields should default to None."""
        selection = AeroSelection(
            cda=0.32,
            crr=0.005,
            source=AeroSource.DEFAULT,
        )

        assert selection.cda_stddev is None
        assert selection.crr_stddev is None
        assert selection.sample_count is None
        assert selection.confidence_note is None
