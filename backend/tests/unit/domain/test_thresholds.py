"""Unit tests for trainingdash.domain.thresholds pure functions."""

from datetime import date

import pytest

from trainingdash.domain.thresholds import compute_default_thresholds


class TestComputeDefaultThresholds:
    """Tests for compute_default_thresholds function."""

    def test_tanaka_formula_for_hrmax(self):
        """HRmax follows Tanaka formula: 208 - 0.7 * age."""
        # Person born 36 years ago
        dob = date(1990, 1, 1)
        today = date.today()
        age = (today - dob).days // 365
        
        result = compute_default_thresholds(dob, weight_kg=None)
        
        expected_hrmax = int(208 - 0.7 * age)
        assert result["hrmax_bpm"] == expected_hrmax

    def test_lthr_is_93_percent_of_hrmax(self):
        """LTHR is calculated as 93% of HRmax."""
        dob = date(1990, 1, 1)
        
        result = compute_default_thresholds(dob, weight_kg=None)
        
        expected_lthr = int(result["hrmax_bpm"] * 0.93)
        assert result["lthr_bpm"] == expected_lthr

    def test_ftp_from_weight(self):
        """FTP is weight_kg * 2.5 when weight is provided."""
        dob = date(1990, 1, 1)
        weight_kg = 80.0
        
        result = compute_default_thresholds(dob, weight_kg=weight_kg)
        
        assert result["ftp_watts"] == 200  # 80 * 2.5 = 200

    def test_ftp_default_when_no_weight(self):
        """FTP defaults to 200W when weight is not provided."""
        dob = date(1990, 1, 1)
        
        result = compute_default_thresholds(dob, weight_kg=None)
        
        assert result["ftp_watts"] == 200

    def test_ftp_default_when_zero_weight(self):
        """FTP defaults to 200W when weight is zero."""
        dob = date(1990, 1, 1)
        
        result = compute_default_thresholds(dob, weight_kg=0)
        
        assert result["ftp_watts"] == 200

    def test_young_athlete_has_higher_hrmax(self):
        """Younger athletes have higher HRmax."""
        young_dob = date(2000, 1, 1)  # ~26 years old
        older_dob = date(1970, 1, 1)  # ~56 years old
        
        young_result = compute_default_thresholds(young_dob, weight_kg=None)
        older_result = compute_default_thresholds(older_dob, weight_kg=None)
        
        assert young_result["hrmax_bpm"] > older_result["hrmax_bpm"]

    def test_returns_all_required_keys(self):
        """Result contains ftp_watts, lthr_bpm, and hrmax_bpm."""
        dob = date(1990, 1, 1)
        
        result = compute_default_thresholds(dob, weight_kg=70.0)
        
        assert "ftp_watts" in result
        assert "lthr_bpm" in result
        assert "hrmax_bpm" in result
        assert len(result) == 3

    def test_all_values_are_integers(self):
        """All returned values are integers."""
        dob = date(1990, 1, 1)
        
        result = compute_default_thresholds(dob, weight_kg=73.5)
        
        assert isinstance(result["ftp_watts"], int)
        assert isinstance(result["lthr_bpm"], int)
        assert isinstance(result["hrmax_bpm"], int)
