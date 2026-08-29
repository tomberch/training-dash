"""Sustainability assessment tests (ADR 0005 #638).

Every plan carries a Sustainability level: green (sustainable), yellow
(very hard, near the rider's limit), red (beyond capability for the
duration). Red plans are still generated and flagged — only the
physically impossible is a hard error (the scale-to-time solver's job).
"""

import pytest

from trainingdash.domain.sustainability import (
    assess_sustainability,
)


class TestSustainabilityBoundaries:
    """Green/yellow/red thresholds: IF and W'bal-depth based, duration
    adjusted. Boundaries pinned exactly."""

    # --- Intensity factor axis (moderate duration, healthy W'bal) ---------

    def test_easy_plan_is_green(self):
        s = assess_sustainability(intensity_factor=0.75, wbal_min_j=15000.0, w_prime_j=20000.0, ride_duration_s=3600.0)
        assert s.level == "green"

    def test_steady_tempo_is_green(self):
        s = assess_sustainability(intensity_factor=0.85, wbal_min_j=12000.0, w_prime_j=20000.0, ride_duration_s=3600.0)
        assert s.level == "green"

    def test_if_above_yellow_threshold_is_yellow(self):
        # IF 0.95 for a 1h ride: very hard but achievable
        s = assess_sustainability(intensity_factor=0.95, wbal_min_j=10000.0, w_prime_j=20000.0, ride_duration_s=3600.0)
        assert s.level == "yellow"

    def test_if_above_ftp_is_red(self):
        # Sustained IF above 1.0: beyond capability for the duration
        s = assess_sustainability(intensity_factor=1.05, wbal_min_j=8000.0, w_prime_j=20000.0, ride_duration_s=3600.0)
        assert s.level == "red"

    # --- W'bal depth axis ----------------------------------------------------

    def test_deep_wbal_depletion_is_yellow(self):
        # W'bal driven to 25% of W' (5000 of 20000): near-limit
        s = assess_sustainability(intensity_factor=0.85, wbal_min_j=5000.0, w_prime_j=20000.0, ride_duration_s=3600.0)
        assert s.level == "yellow"

    def test_full_wbal_depletion_is_red(self):
        # W'bal driven to <= 10% of W': beyond capability
        s = assess_sustainability(intensity_factor=0.85, wbal_min_j=1500.0, w_prime_j=20000.0, ride_duration_s=3600.0)
        assert s.level == "red"

    def test_zero_wbal_is_red(self):
        s = assess_sustainability(intensity_factor=0.80, wbal_min_j=0.0, w_prime_j=20000.0, ride_duration_s=3600.0)
        assert s.level == "red"

    # --- Duration adjustment -------------------------------------------------

    def test_same_if_harder_when_longer(self):
        """IF 0.90 for 40 minutes is green; the same IF for 5 hours is
        yellow or worse — endurance tolerance shrinks with duration."""
        short = assess_sustainability(intensity_factor=0.90, wbal_min_j=15000.0, w_prime_j=20000.0, ride_duration_s=2400.0)
        long_ = assess_sustainability(intensity_factor=0.90, wbal_min_j=15000.0, w_prime_j=20000.0, ride_duration_s=18000.0)
        assert short.level == "green"
        assert long_.level in ("yellow", "red")

    def test_long_ride_at_high_if_is_red(self):
        """5 hours at IF 0.95: beyond capability (long-ride tolerance)."""
        s = assess_sustainability(intensity_factor=0.95, wbal_min_j=8000.0, w_prime_j=20000.0, ride_duration_s=18000.0)
        assert s.level == "red"

    # --- Red still assessable, message present ------------------------------

    def test_every_level_has_a_message(self):
        for if_, wbal in ((0.75, 15000.0), (0.95, 5000.0), (1.10, 0.0)):
            s = assess_sustainability(intensity_factor=if_, wbal_min_j=wbal, w_prime_j=20000.0, ride_duration_s=3600.0)
            assert s.message, f"level {s.level} needs a message"

    def test_result_carries_level_and_reasons(self):
        s = assess_sustainability(intensity_factor=1.05, wbal_min_j=500.0, w_prime_j=20000.0, ride_duration_s=7200.0)
        assert s.level == "red"
        assert "IF" in s.message or "W'" in s.message or "intensity" in s.message.lower()