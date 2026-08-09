"""Unit tests for trainingdash.domain.thresholds pure functions."""

from datetime import date

from trainingdash.domain.thresholds import (
    ThresholdHistoryEntry,
    ThresholdValues,
    compute_default_thresholds,
    pick_effective_threshold,
)


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


class TestPickEffectiveThreshold:
    """Tests for pick_effective_threshold — pure date-effectiveness rule."""

    def test_returns_all_none_when_no_entries(self):
        """No entries → all-None ThresholdValues."""
        result = pick_effective_threshold([], date(2024, 6, 1))
        assert result.ftp_watts is None
        assert result.lthr_bpm is None
        assert result.hrmax_bpm is None
        assert result.effective_date == date(2024, 6, 1)

    def test_returns_all_none_when_no_entries_effective(self):
        """Entries exist but all are after target_date → all-None."""
        entries = [
            ThresholdHistoryEntry(
                effective_date=date(2024, 7, 1), ftp_watts=250
            )
        ]
        result = pick_effective_threshold(entries, date(2024, 6, 1))
        assert result.ftp_watts is None

    def test_picks_most_recent_entry_on_or_before_target(self):
        """Most recent entry <= target_date wins."""
        entries = [
            ThresholdHistoryEntry(effective_date=date(2024, 1, 1), ftp_watts=200),
            ThresholdHistoryEntry(effective_date=date(2024, 3, 1), ftp_watts=220),
            ThresholdHistoryEntry(effective_date=date(2024, 6, 1), ftp_watts=250),
        ]
        result = pick_effective_threshold(entries, date(2024, 5, 1))
        assert result.ftp_watts == 220

    def test_picks_exact_date_match(self):
        """Entry with effective_date == target_date is included."""
        entries = [
            ThresholdHistoryEntry(effective_date=date(2024, 6, 1), ftp_watts=250),
        ]
        result = pick_effective_threshold(entries, date(2024, 6, 1))
        assert result.ftp_watts == 250

    def test_metrics_resolved_independently(self):
        """Each metric (FTP, LTHR, HRmax) comes from its own most-recent entry."""
        entries = [
            ThresholdHistoryEntry(
                effective_date=date(2024, 1, 1), ftp_watts=200, lthr_bpm=None, hrmax_bpm=None
            ),
            ThresholdHistoryEntry(
                effective_date=date(2024, 3, 1), ftp_watts=None, lthr_bpm=165, hrmax_bpm=None
            ),
            ThresholdHistoryEntry(
                effective_date=date(2024, 5, 1), ftp_watts=None, lthr_bpm=None, hrmax_bpm=185
            ),
        ]
        result = pick_effective_threshold(entries, date(2024, 6, 1))
        assert result.ftp_watts == 200
        assert result.lthr_bpm == 165
        assert result.hrmax_bpm == 185

    def test_skips_none_values(self):
        """None values in a recent entry don't shadow older non-None values."""
        entries = [
            ThresholdHistoryEntry(
                effective_date=date(2024, 1, 1), ftp_watts=200
            ),
            ThresholdHistoryEntry(
                effective_date=date(2024, 3, 1), ftp_watts=None
            ),
        ]
        result = pick_effective_threshold(entries, date(2024, 6, 1))
        # Most recent (3/1) has None for ftp, so fall back to 1/1's 200
        assert result.ftp_watts == 200


class TestThresholdHistoryEntry:
    """Tests for ThresholdHistoryEntry dataclass."""

    def test_default_source_is_manual(self):
        """Default source is 'manual'."""
        entry = ThresholdHistoryEntry(effective_date=date(2024, 1, 1))
        assert entry.source == "manual"

    def test_defaults_are_none(self):
        """Threshold values default to None."""
        entry = ThresholdHistoryEntry(effective_date=date(2024, 1, 1))
        assert entry.ftp_watts is None
        assert entry.lthr_bpm is None
        assert entry.hrmax_bpm is None
        assert entry.created_at is None


class TestThresholdValues:
    """Tests for ThresholdValues dataclass."""

    def test_defaults_are_none(self):
        """All fields default to None."""
        tv = ThresholdValues()
        assert tv.ftp_watts is None
        assert tv.lthr_bpm is None
        assert tv.hrmax_bpm is None
        assert tv.effective_date is None
