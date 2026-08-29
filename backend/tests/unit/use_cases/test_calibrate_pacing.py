"""Unit tests for the CalibratePacing use case (ADR 0005, ticket #633)."""

from types import SimpleNamespace

import pytest

import trainingdash.use_cases.calibrate_pacing as uc_mod
from tests.fakes.pacing_coefficients_repo import FakePacingCoefficientsRepo
from trainingdash.domain.pacing_calibration import (
    MIN_CLIMB_SAMPLES,
    DescentSample,
    GradePowerSample,
)
from trainingdash.use_cases.calibrate_pacing import CalibratePacing


def _noisy_climb_samples(n):
    """Samples uncorrelated with grade → R² ≈ 0 → gate must reject."""
    import random

    rng = random.Random(3)
    return [
        GradePowerSample(grade_pct=rng.uniform(1, 15), power_mult=rng.uniform(0.5, 2.5), time_weight=5.0)
        for _ in range(n)
    ]


def _decent_samples(n):
    """Clean linear relationship: mult = 1.0 + 0.04 × grade + tiny noise."""
    import random

    rng = random.Random(3)
    return [
        GradePowerSample(grade_pct=g, power_mult=1.0 + 0.04 * g + rng.uniform(-0.05, 0.05), time_weight=5.0)
        for _ in range(n // 4)
        for g in (2.0, 5.0, 8.0, 12.0)
    ]


class _FakeDB:
    """Minimal AsyncSession stand-in: raises if the use case queries it."""

    class _Result:
        def scalars(self):
            return self

        def all(self):
            return []

    def execute(self, *_a, **_k):
        raise AssertionError("use case should not query the DB in unit scope here")

    async def execute_async(self, *_a, **_k):
        raise AssertionError


@pytest.fixture
def fake_repo():
    return FakePacingCoefficientsRepo()


_DUMMY_RECORD = SimpleNamespace(power_w=200, altitude_m=100.0, distance_m=10.0, timestamp=None)


def _stubbed_use_case(monkeypatch, repo, n_activities):
    """CalibratePacing with DB reads stubbed (activities exist, no records)."""

    uc = CalibratePacing(_FakeDB(), repo)
    activities = [SimpleNamespace(id=f"act-{i}", avg_power_w=200) for i in range(n_activities)]

    async def _activities(user_id, bike_id=None):
        return activities

    async def _records(activity_id):
        # One dummy record: lets the loop pass the "not records" guard;
        # the extractors themselves are patched out in each test.
        return [_DUMMY_RECORD]

    monkeypatch.setattr(uc, "_get_qualifying_activities", _activities)
    monkeypatch.setattr(uc, "_get_records", _records)
    return uc


@pytest.mark.asyncio
async def test_quality_gate_rejection_keeps_coefficients_and_reports(monkeypatch, fake_repo):
    """Garbage fit (R²≈0) with plenty of samples → not stored, message set."""

    uc = _stubbed_use_case(monkeypatch, fake_repo, n_activities=5)
    monkeypatch.setattr(uc_mod, "pedaling_average_power", lambda records: 200.0)

    # Bypass record extraction: inject known-bad samples
    monkeypatch.setattr(
        uc_mod, "extract_climb_samples", lambda records, avg_power: _noisy_climb_samples(MIN_CLIMB_SAMPLES + 50)
    )
    monkeypatch.setattr(
        uc_mod,
        "extract_descent_samples",
        lambda records, avg_power: [
            DescentSample(grade_pct=-5.0, speed_mps=12.0, power_mult=0.4, curvature=0.008, time_weight=5.0)
            for _ in range(400)
        ],
    )

    stats = await uc.execute(user_id=3)

    assert stats.coefficients_updated is False
    assert stats.message is not None
    assert "quality" in stats.message.lower()
    assert await fake_repo.list_for_user(3) == []  # nothing stored


@pytest.mark.asyncio
async def test_good_fit_still_stored(monkeypatch, fake_repo):
    """Clean samples above the gate → stored, as before."""
    uc = _stubbed_use_case(monkeypatch, fake_repo, n_activities=5)
    monkeypatch.setattr(uc_mod, "pedaling_average_power", lambda records: 200.0)
    monkeypatch.setattr(
        uc_mod, "extract_climb_samples", lambda records, avg_power: _decent_samples(MIN_CLIMB_SAMPLES * 4)
    )
    monkeypatch.setattr(
        uc_mod,
        "extract_descent_samples",
        lambda records, avg_power: [
            DescentSample(grade_pct=-5.0, speed_mps=11.0, power_mult=0.4, curvature=0.008, time_weight=5.0)
            for _ in range(400)
        ],
    )

    stats = await uc.execute(user_id=3)

    assert stats.coefficients_updated is True
    stored = await fake_repo.get_user_default(3)
    assert stored is not None
    assert float(stored.grade_power_intercept) == pytest.approx(1.0, abs=0.2)
    assert float(stored.grade_power_slope) == pytest.approx(0.04, rel=0.3)
