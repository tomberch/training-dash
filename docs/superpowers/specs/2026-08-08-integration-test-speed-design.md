# Speed Up Backend Integration Test Suite — Design

## Status

Proposed

## Context

The backend integration test suite (`backend/tests/integration/`, pytest) takes **5–10 minutes** for ~250 tests across 19 files. This is the dominant cost in local development feedback loops and CI (`uv run pytest --tb=short -q`).

A thorough analysis of the suite identified one dominant hidden cost and several secondary costs.

## Root Cause Analysis

### Primary: unmocked reverse geocoding with rate-limit sleeps

Every GPS upload (the default for `make_test_fit`) runs the full ingest pipeline, which calls `trainingdash.title_generator.generate_activity_title` → `trainingdash.geocoding.GeocodingService.reverse_geocode` against the real `photon.komoot.io` endpoint. The geocoding service enforces a **1-second `RATE_LIMIT_DELAY` sleep between each HTTP call** (`geocoding.py:29,135-136`).

A single upload fires 3–12 reverse-geocode calls (start point, end point, furthest point for roundtrips, and a batch of sampled settlements along the route). That is **3–12+ seconds of pure sleep per upload**, before network latency. Geocoding is **never mocked in the integration suite** (only in `tests/unit/test_activity_pipeline.py`). There are ~94 `make_test_fit` uploads across the suite, most with GPS.

This is the single biggest cause of slowness, and it is hidden — no test code references geocoding.

### Secondary costs

- **Per-test TRUNCATE of all tables** fires before every test via the `db_engine` fixture (`conftest.py:224-235`). Every test uses `db_engine` directly or transitively (`db_session` / `app_client` / `auth_client`).
- **Per-test bcrypt login** on every `auth_client` test (~200 tests). `CACHED_HASH_TESTPASS` avoids per-test *hashing* but `bcrypt.checkpw` still runs on every login.
- **Repeated identical uploads.** `test_hr_power.py` uploads 5×N=300 rides in 4 separate tests to build the same EF model. `test_batch_import.py` has two `@slow` tests each doing 15×N=300. `test_power_curve.py` re-uploads N=120 in 9 tests.
- **N=300 everywhere** when tests only assert on counts/status, not record-level data (`test_batch_import.py`, `test_hr_power.py`).
- **Misplaced unit tests.** `test_fitness.py::TestFitnessModelUnit` (7 tests) and `test_pmc.py::TestPMCComputation` (6 tests) are pure functions with no DB access, yet pay TRUNCATE + bcrypt login.
- **Double TRUNCATE in `test_arq.py`.** `arq_engine` (`test_arq.py:32`) TRUNCATEs on setup (line 55) and teardown (line 64) on top of conftest's per-test TRUNCATE.
- **`test_tiles.py`** (13 tests) depends on `db_engine` → 13 unnecessary TRUNCATEs. These are pure HTTP-mock tests that never touch the DB.
- **`make_test_fit` called per-test** in files that always use the same N. The `FitFileBuilder` runs once per test instead of once per module.

## Decision

Adopt **Approach A: mock geocoding + targeted cleanup**. This is the highest bang-for-buck, lowest-risk option. It eliminates the geocoding sleep tax (estimated 50–70% reduction) and removes several sources of per-test overhead, without changing test semantics.

Approaches B (shared session-scoped activity fixtures) and C (parallel execution via per-worker databases) are deferred — they are more invasive and only worthwhile after A lands and the suite is re-measured.

## Work Items

### 1. Mock geocoding in the integration conftest

Add an autouse fixture in `backend/tests/integration/conftest.py` that patches `trainingdash.title_generator.generate_activity_title` to return a fixed title string instantly, without network or sleeps.

**Why this seam:** It is one mock covering all geocode calls (start, end, furthest point, settlements). It is the same seam the unit suite already mocks (`test_activity_pipeline.py:374`), so it is the established pattern. Patching lower (the `GeocodingService` itself) would leave the batch/loop orchestration in `title_generator` running — more mocks, same outcome.

**Scope:** A single autouse fixture in `conftest.py`, ~10 lines. No test files change.

**Acceptance criteria:**
- All integration tests pass.
- No HTTP call to `photon.komoot.io` is made during the integration suite (verified by confirming no `httpx` geocoding client is constructed, or by asserting the mock is invoked).
- A single GPS upload completes in well under 1 second of wall-clock time for the geocoding step.
- The unit test `test_non_batch_mode_attempts_geocoding` (`test_activity_pipeline.py:359`) still passes — it is unaffected since it lives in `tests/unit/`.

### 2. Move misplaced unit tests to `tests/unit/`

Move `test_fitness.py::TestFitnessModelUnit` (7 tests) and `test_pmc.py::TestPMCComputation` (6 tests) to `tests/unit/`. These are pure functions with no DB access.

**Scope:** Move two test classes, adjust imports. No behavior change.

**Acceptance criteria:**
- The 13 moved tests pass in their new location.
- `test_fitness.py` and `test_pmc.py` still pass with the classes removed.
- The moved tests no longer trigger TRUNCATE or bcrypt login (no `db_engine`/`auth_client` dependency).

### 3. Decouple `test_tiles.py` from `db_engine`

Add a lightweight `http_client` fixture in `conftest.py` that builds the app + `AsyncClient` with `ASGITransport` but **no `db_engine` dependency** and no TRUNCATE. Switch `test_tiles.py` (13 tests) to use it.

**Acceptance criteria:**
- All 13 `test_tiles.py` tests pass with the new fixture.
- No TRUNCATE fires for `test_tiles.py` tests (verifiable by adding a temporary `print` or by timing).
- `test_tiles.py` no longer imports or depends on `db_engine`, `db_session`, `app_client`, or `auth_client`.

### 4. Remove double TRUNCATE in `test_arq.py`

`arq_engine` (`test_arq.py:32`) currently depends on `db_engine_session` (session-scoped, no TRUNCATE) and TRUNCATEs on setup (line 55) and teardown (line 64). Conftest's `db_engine` already TRUNCATEs per test.

**Change:** Make `arq_engine` depend on `db_engine` (function-scoped) instead of `db_engine_session`, and drop its setup TRUNCATE. Keep the teardown TRUNCATE only if worker-spawned rows would otherwise leak across tests.

**Acceptance criteria:**
- All 3 `test_arq.py` tests pass.
- No more than one TRUNCATE fires per `test_arq.py` test before the test body runs.
- Worker job results are still correctly observed (no cross-test row leakage).

### 5. Pre-generate FIT bytes at module level

In files that always use the same N, hoist `make_test_fit(num_records=N)` to a module-level constant so the `FitFileBuilder` runs once per module, not once per test.

**Target files (initial):**
- `test_power_curve.py` (always N=120)
- `test_hr_power.py` (always N=300)

**Scope:** Add a module-level constant (e.g. `FIT_120 = make_test_fit(num_records=120)`) and reference it in tests. Other files with varied N are left unchanged.

**Acceptance criteria:**
- All tests in the modified files pass.
- `make_test_fit` is called once per module at import time, not once per test.

## Out of Scope

- Shared session-scoped activity fixtures (Approach B) — deferred.
- Parallel execution via per-worker databases (Approach C) — deferred.
- Reducing N=300 to smaller values in `test_batch_import.py` / `test_hr_power.py` — deferred to a follow-up; it changes test data and needs careful per-test review.
- Frontend E2E suite (`frontend/e2e/`) — separate effort.

## Verification

After all five items land, re-measure the full suite runtime and record it in the closing PR. Target: **under 3 minutes** (from 5–10 min). If the target is not met, investigate the next tier (Approach B) before claiming done.