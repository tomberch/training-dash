"""Unit tests for the CalibratePacing use case (ADR 0005, ticket #633)."""

from types import SimpleNamespace

import pytest

import trainingdash.use_cases.calibrate_pacing as uc_mod
from tests.fakes.pacing_coefficients_repo import FakePacingCoefficientsRepo
from trainingdash.domain.pacing_calibration import (
    MIN_CLIMB_SAMPLES,
    MIN_DESCENT_SAMPLES,
    DescentSample,
    GradePowerSample,
)
from trainingdash.domain.pacing_model import PacingCoefficients
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
    # Descent volume below MIN_DESCENT_SAMPLES so the partial-store path
    # (#634) doesn't kick in — this test pins "nothing at all is learnable".
    monkeypatch.setattr(
        uc_mod,
        "extract_descent_samples",
        lambda records, avg_power: [
            DescentSample(grade_pct=-5.0, speed_mps=12.0, power_mult=0.4, curvature=0.008, time_weight=5.0)
            for _ in range(50)
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


@pytest.mark.asyncio
async def test_descent_fit_survives_climb_gate_rejection(monkeypatch, fake_repo):
    """#634: noisy climb fit (gate rejects) + clean descent data → descent
    coefficients stored; climb coefficients unchanged (prior row or defaults)."""
    uc = _stubbed_use_case(monkeypatch, fake_repo, n_activities=5)
    monkeypatch.setattr(uc_mod, "pedaling_average_power", lambda records: 200.0)

    # Climb: garbage (R² ≈ 0) → gate must reject
    monkeypatch.setattr(
        uc_mod, "extract_climb_samples", lambda records, avg_power: _noisy_climb_samples(MIN_CLIMB_SAMPLES + 50)
    )
    # Descent: consistent coaster → fitted mult ≈ 0.1
    monkeypatch.setattr(
        uc_mod,
        "extract_descent_samples",
        lambda records, avg_power: [
            DescentSample(grade_pct=-6.0, speed_mps=13.0, power_mult=0.1, curvature=0.005, time_weight=5.0)
            for _ in range(MIN_DESCENT_SAMPLES + 100)
        ],
    )

    stats = await uc.execute(user_id=3)

    # The row IS stored (descent knowledge), but flagged as partial
    assert stats.coefficients_updated is True
    assert stats.message is not None and "climb" in stats.message.lower()
    stored = await fake_repo.get_user_default(3)
    assert stored is not None
    assert float(stored.descent_power_multiplier) == pytest.approx(0.1, abs=0.05)
    # Climb coefficients: not poisoned by the garbage fit — defaults kept
    assert float(stored.grade_power_intercept) == pytest.approx(1.10, abs=0.01)
    assert float(stored.grade_power_slope) == pytest.approx(0.035, abs=0.001)
    # Stored row is not treated as climb-calibrated (engine falls back
    # for climb formula; descent multiplier IS live)
    assert stored.climb_sample_count == 0
    assert stored.descent_sample_count == 5 * (MIN_DESCENT_SAMPLES + 100)


@pytest.mark.asyncio
async def test_descent_insufficient_data_no_partial_store(monkeypatch, fake_repo):
    """#634: climb gate fails AND descent below sample floor → nothing stored."""
    uc = _stubbed_use_case(monkeypatch, fake_repo, n_activities=5)
    monkeypatch.setattr(uc_mod, "pedaling_average_power", lambda records: 200.0)
    monkeypatch.setattr(
        uc_mod, "extract_climb_samples", lambda records, avg_power: _noisy_climb_samples(MIN_CLIMB_SAMPLES + 50)
    )
    monkeypatch.setattr(
        uc_mod,
        "extract_descent_samples",
        lambda records, avg_power: [
            DescentSample(grade_pct=-6.0, speed_mps=13.0, power_mult=0.1, curvature=0.005, time_weight=5.0)
            for _ in range(50)  # below MIN_DESCENT_SAMPLES
        ],
    )

    stats = await uc.execute(user_id=3)
    assert stats.coefficients_updated is False
    assert await fake_repo.list_for_user(3) == []


@pytest.mark.asyncio
async def test_bike_calibration_writes_bike_row(monkeypatch, fake_repo):
    """#634 (pre-existing bug): execute(bike_id=N) must write the bike-N
    row, not the user-default row."""
    uc = _stubbed_use_case(monkeypatch, fake_repo, n_activities=5)
    monkeypatch.setattr(uc_mod, "pedaling_average_power", lambda records: 200.0)
    monkeypatch.setattr(
        uc_mod, "extract_climb_samples", lambda records, avg_power: _decent_samples(MIN_CLIMB_SAMPLES * 4)
    )
    monkeypatch.setattr(
        uc_mod,
        "extract_descent_samples",
        lambda records, avg_power: [
            DescentSample(grade_pct=-6.0, speed_mps=13.0, power_mult=0.2, curvature=0.005, time_weight=5.0)
            for _ in range(MIN_DESCENT_SAMPLES + 50)
        ],
    )

    stats = await uc.execute(user_id=3, bike_id=7)

    assert stats.coefficients_updated is True
    bike_row = await fake_repo.get_for_bike(3, 7)
    user_row = await fake_repo.get_user_default(3)
    assert bike_row is not None, "bike fit must land on the bike row"
    assert float(bike_row.descent_power_multiplier) == pytest.approx(0.2, abs=0.05)
    assert user_row is None, "user-default row must not be touched by a bike calibration"


@pytest.mark.asyncio
async def test_behavior_baseline_learned_and_stored(monkeypatch, fake_repo):
    """#635: calibration extracts per-ride behavior, aggregates per terrain
    with the gate, and stores terrain_behavior on the coefficients row."""
    from trainingdash.domain.rider_behavior import RideBehaviorSample

    uc = _stubbed_use_case(monkeypatch, fake_repo, n_activities=5)
    monkeypatch.setattr(uc_mod, "pedaling_average_power", lambda records: 200.0)
    monkeypatch.setattr(
        uc_mod, "extract_climb_samples", lambda records, avg_power: _decent_samples(MIN_CLIMB_SAMPLES * 4)
    )
    monkeypatch.setattr(
        uc_mod,
        "extract_descent_samples",
        lambda records, avg_power: [
            DescentSample(grade_pct=-6.0, speed_mps=13.0, power_mult=0.2, curvature=0.005, time_weight=5.0)
            for _ in range(MIN_DESCENT_SAMPLES + 50)
        ],
    )
    # Behavior extraction: 3+ hilly rides clear the per-bucket gate
    behavior_samples = [
        RideBehaviorSample(
            terrain_type="hilly", non_pedaling_pct=16.0, coasting_pct=16.0, stopped_pct=0.0, ride_time_s=3600.0
        )
        for _ in range(5)
    ]
    monkeypatch.setattr(uc_mod, "extract_ride_behavior", lambda records, grades: behavior_samples[0])
    monkeypatch.setattr(
        uc_mod,
        "aggregate_behavior_baseline",
        lambda samples: (
            None
            if False
            else __import__(
                "trainingdash.domain.rider_behavior", fromlist=["aggregate_behavior_baseline"]
            ).aggregate_behavior_baseline(samples)
        ),
    )

    stats = await uc.execute(user_id=3)

    assert stats.coefficients_updated is True
    stored = await fake_repo.get_user_default(3)
    assert stored is not None
    assert stored.terrain_behavior is not None
    assert "hilly" in stored.terrain_behavior
    assert stored.terrain_behavior["hilly"]["non_pedaling_pct"] == pytest.approx(16.0, abs=0.5)
    assert stored.terrain_behavior["hilly"]["activity_count"] == 5


class TestCoefficientsAPIBehaviorExposure:
    """#635: the coefficients API response carries the learned baseline."""

    def test_response_includes_terrain_behavior(self):
        from trainingdash.routers.pacing_coefficients import _build_coefficients_response

        coef = PacingCoefficients(
            user_id=3,
            activity_count=10,
            terrain_behavior={
                "hilly": {"non_pedaling_pct": 16.2, "coasting_pct": 15.1, "stopped_pct": 1.1, "activity_count": 9},
            },
        )
        response = _build_coefficients_response(coef, bike_names={})
        assert response.terrain_behavior == coef.terrain_behavior

    def test_response_terrain_behavior_none_when_unlearned(self):
        from trainingdash.routers.pacing_coefficients import _build_coefficients_response

        coef = PacingCoefficients(user_id=3, activity_count=0)
        response = _build_coefficients_response(coef, bike_names={})
        assert response.terrain_behavior is None
