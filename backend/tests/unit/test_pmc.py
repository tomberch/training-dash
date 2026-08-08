"""Unit tests for PMC computation functions."""

from datetime import date, datetime


class TestPMCComputation:
    """Unit tests for PMC computation functions."""

    def test_compute_pmc_empty_tss(self):
        """PMC with no TSS data returns all zeros."""
        from trainingdash.pmc import compute_pmc

        start = date(2024, 1, 1)
        end = date(2024, 1, 7)

        result = compute_pmc({}, start, end)

        assert len(result) == 7
        for day in result:
            assert day["ctl"] == 0.0
            assert day["atl"] == 0.0
            assert day["tsb"] == 0.0

    def test_compute_pmc_single_activity(self):
        """PMC with single activity shows ATL spike."""
        from trainingdash.pmc import compute_pmc

        activity_date = date(2024, 1, 5)
        daily_tss = {activity_date: 100.0}  # 100 TSS

        start = date(2024, 1, 1)
        end = date(2024, 1, 14)

        result = compute_pmc(daily_tss, start, end)

        # Before activity, all zeros
        for day in result[:4]:  # Jan 1-4
            assert day["ctl"] == 0.0
            assert day["atl"] == 0.0

        # Day after activity, ATL should be higher than CTL
        # (ATL has 7-day constant, CTL has 42-day)
        day_after = next(d for d in result if d["date"] == "2024-01-06")
        assert day_after["atl"] > day_after["ctl"]
        assert day_after["tsb"] < 0  # Negative TSB = fatigued

    def test_compute_pmc_atl_decays_faster_than_ctl(self):
        """ATL decays faster than CTL after activity."""
        from trainingdash.pmc import compute_pmc

        activity_date = date(2024, 1, 1)
        daily_tss = {activity_date: 100.0}

        start = date(2024, 1, 1)
        end = date(2024, 1, 30)

        result = compute_pmc(daily_tss, start, end)

        # Get values at different points
        day_1 = next(d for d in result if d["date"] == "2024-01-02")
        day_7 = next(d for d in result if d["date"] == "2024-01-08")
        day_14 = next(d for d in result if d["date"] == "2024-01-15")

        # ATL should decay significantly by day 14
        assert day_14["atl"] < day_7["atl"] < day_1["atl"]

        # CTL decays slower
        ctl_decay_7_days = (day_1["ctl"] - day_7["ctl"]) / day_1["ctl"] if day_1["ctl"] > 0 else 0
        atl_decay_7_days = (day_1["atl"] - day_7["atl"]) / day_1["atl"] if day_1["atl"] > 0 else 0

        # ATL decays faster (higher percentage drop)
        assert atl_decay_7_days > ctl_decay_7_days

    def test_aggregate_daily_tss(self):
        """Aggregates multiple activities on same day."""
        from trainingdash.pmc import aggregate_daily_tss

        activities = [
            {"started_at": datetime(2024, 1, 5, 8, 0), "tss": 50.0},
            {"started_at": datetime(2024, 1, 5, 18, 0), "tss": 30.0},  # Same day
            {"started_at": datetime(2024, 1, 6, 8, 0), "tss": 80.0},
        ]

        result = aggregate_daily_tss(activities)

        assert result[date(2024, 1, 5)] == 80.0  # 50 + 30
        assert result[date(2024, 1, 6)] == 80.0

    def test_aggregate_daily_tss_skips_none(self):
        """Aggregation skips activities without TSS."""
        from trainingdash.pmc import aggregate_daily_tss

        activities = [
            {"started_at": datetime(2024, 1, 5, 8, 0), "tss": 50.0},
            {"started_at": datetime(2024, 1, 5, 18, 0), "tss": None},  # No TSS
            {"started_at": None, "tss": 100.0},  # No date
        ]

        result = aggregate_daily_tss(activities)

        assert result[date(2024, 1, 5)] == 50.0  # Only first activity
        assert len(result) == 1

    def test_ewma_factor(self):
        """EWMA factor is correct for time constants."""
        from trainingdash.pmc import compute_ewma_factor

        # 7-day: factor ≈ 0.857
        assert abs(compute_ewma_factor(7) - (1 - 1/7)) < 0.001

        # 42-day: factor ≈ 0.976
        assert abs(compute_ewma_factor(42) - (1 - 1/42)) < 0.001