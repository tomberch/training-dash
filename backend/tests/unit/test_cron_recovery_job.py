"""Tests for cron job settings in worker.settings() (ADR 0006, decisions 1+2).

- Strand-recovery cron (recover_strands_job) is registered hourly, unique
- Cron jobs carry flat retry budgets (retries=2, retry_delay=60, no backoff)
  so all attempts finish inside the hourly tick
"""

from unittest.mock import patch

import pytest

from trainingdash.worker import (
    recover_strands_job,
    settings,
)


@pytest.fixture
def settings_dict(monkeypatch):
    """settings() with a DATABASE_URL set so queue construction succeeds (no real connection)."""
    monkeypatch.setenv("DATABASE_URL", "postgresql://test:test@localhost:5433/test")
    d = settings()
    return d


def _cron_by_function(settings_dict):
    return {cj.function.__name__: cj for cj in settings_dict["cron_jobs"]}


def test_recover_strands_cron_registered(settings_dict):
    crons = _cron_by_function(settings_dict)
    assert "recover_strands_job" in crons
    cron = crons["recover_strands_job"]
    assert cron.unique is True


def test_recover_strands_cron_hourly(settings_dict):
    cron = _cron_by_function(settings_dict)["recover_strands_job"]
    assert cron.cron == "10 * * * *"


def test_recover_strands_job_registered_in_functions(settings_dict):
    assert recover_strands_job in settings_dict["functions"]


def test_cron_jobs_have_flat_retry_budget(settings_dict):
    crons = _cron_by_function(settings_dict)
    for name in (
        "hourly_import_scheduler",
        "hourly_backup_scheduler",
        "flush_cache_stats",
        "prune_old_data",
        "recover_strands_job",
    ):
        assert name in crons, f"{name} not registered"
        cj = crons[name]
        assert cj.retries == 2, f"{name}: retries"
        assert cj.retry_delay == 60, f"{name}: retry_delay"
        assert not cj.retry_backoff, f"{name}: must have flat delay (no backoff)"


def test_recover_strands_job_is_tracked():
    """recover_strands_job is wrapped by tracked_job (event instrumentation)."""

    assert getattr(recover_strands_job, "__name__", "") == "recover_strands_job"
    # The wrapper closes over job_name; check via attribute set by functools.wraps chain
    assert recover_strands_job.__wrapped__ is not None


async def test_recover_strands_job_wires_repos():
    """The job function constructs the use case with both repos and an event repo."""
    from unittest.mock import AsyncMock, MagicMock

    from trainingdash.worker import recover_strands_job as job

    mock_db = MagicMock()
    mock_db.execute = AsyncMock()
    mock_db.commit = AsyncMock()

    with patch("trainingdash.worker.worker_db_session") as fake_session:
        fake_session.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        fake_session.return_value.__aexit__ = AsyncMock()
        with patch("trainingdash.repositories.postgres.recalculation_job_repo.PostgresRecalculationJobRepo") as rrepo:
            with patch("trainingdash.repositories.postgres.backup_repo.PostgresBackupRepo") as brepo:
                with patch("trainingdash.repositories.postgres.event_repo.PostgresEventRepo") as erepo:
                    rrepo.return_value.recover_stranded_running = AsyncMock(return_value=[])
                    brepo.return_value.recover_stranded_running = AsyncMock(return_value=[])
                    result = await job({})

    assert result == {"recalculation_recovered": 0, "backup_recovered": 0}
