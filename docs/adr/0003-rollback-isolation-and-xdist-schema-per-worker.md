# ADR 0003: SAVEPOINT rollback + xdist schema-per-worker for integration tests

The integration test suite is slow and serial: per-test setup was ~700-800ms
(96% of every test's wall time) under `TRUNCATE ... RESTART IDENTITY CASCADE`,
and pytest-xdist was disabled on the belief that PostGIS `geography` only
works in the `public` schema. We decided to replace TRUNCATE with per-test
SAVEPOINT rollback (the SQLAlchemy 2.0 test-suite recipe) and re-enable xdist
via schema-per-worker isolation, because both beliefs turned out to be wrong:
`ingest_fit(db, ...)` takes the session as an argument (so HTTP and direct
writes share one connection), and PostGIS 3.4 supports `geography` via
`search_path` regardless of where the extension is installed.

## Considered Options

- **SAVEPOINT rollback + xdist schema-per-worker** (accepted) — per-test
  `engine.connect()` + `begin()` + `join_transaction_mode="create_savepoint"`,
  rolled back at teardown; per-worker `test_<worker_id>` schema with
  `search_path = <worker_schema>,public`; `postgis` installed once in `public`
  under `pg_advisory_xact_lock` (asyncpg raises `UniqueViolation` when
  `CREATE EXTENSION IF NOT EXISTS` is raced). Result: 103s serial, 41-45s with
  `-n 4`.
- **Keep TRUNCATE, drop `RESTART IDENTITY`** — removes per-sequence exclusive
  locks (the dominant cost per the PG docs) but keeps `TRUNCATE`'s per-test
  table locks. Rejected: dominated by rollback on the measured numbers.
- **`pytest-postgresql` template-DB cloning** — `CREATE DATABASE ... TEMPLATE`
  per test. Rejected: gives up the single-connection rollback speedup; only
  worth it if rollback underperforms (it doesn't).
- **Per-worker database (not schema)** — `CREATE DATABASE` can't run in a
  transaction (~0.6s/worker, more friction). Rejected for schema-per-worker
  (~0.1s/worker, in-transaction).
- **StaticPool single connection + `begin_nested()`** — rejected during the
  #280 prototype: asyncpg's single-connection concurrency limit blocks the
  `get_db` override from opening a second session on the shared connection.
  The accepted design uses a normal pool so each test checks out its own
  connection.

## Consequences

- Tests that hardcoded `user_id=1` (relying on `TRUNCATE`'s `RESTART IDENTITY`
  resetting the sequence) were fixed to use `seed_user.id`. This is a
  one-time migration cost any rollback-based suite pays.
- `asyncio_default_fixture_loop_scope = "session"` and
  `asyncio_default_test_loop_scope = "session"` are required in
  `pyproject.toml` — without both, asyncpg connections bind to per-test event
  loops and fail with "attached to a different loop."
- `test_arq.py` is module-skipped pending #285 (ARQ/Redis isolation under
  xdist is a separate decision; Redis isn't isolated by schema-per-worker).
- 11 pre-existing `test_user_settings.py` failures (stale expectations from
  the Clean Architecture refactor) are `xfail(strict=True)` pending #286 —
  surfaced only because #284 unblocked collection.
- The `async with conn.begin():` context manager did **not** roll back
  reliably with asyncpg + the default pool; teardown uses explicit
  `trans.rollback()`. This is a SQLAlchemy-async edge case worth knowing.
- Race-free: workers share nothing writable (the `postgis` extension is
  read-only after install; tables live in per-worker schemas). See #281 for
  the full race-condition analysis.

## References

- #281 — the decision (isolation model + parallelism, weighed together)
- #282 — parallelism decision (xdist schema-per-worker)
- #278 — research: PostGIS 3.4 `geography` works in non-`public` schemas
- #279 — research: SQLAlchemy 2.0 `join_transaction_mode="create_savepoint"` recipe
- #280 — prototype: rollback viable on `test_upload.py` (-48% wall-clock)
- #284 — this build
- `docs/research/xdist-postgis-patterns.md`, `docs/research/pytest-isolation-strategies.md`