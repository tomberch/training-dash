# ADR-0003: SAVEPOINT rollback + xdist schema-per-worker for integration tests

## Status

Accepted

## Context

The integration test suite was slow and serial: per-test setup was ~700-800ms
(96% of every test's wall time) under `TRUNCATE ... RESTART IDENTITY CASCADE`,
and pytest-xdist was disabled on the belief (documented at
`backend/tests/integration/conftest.py:198-201`) that PostGIS `geography` only
works in the `public` schema. The per-change dev loop inherited that tax; the
full suite did not finish within 5 minutes and often hung.

Two prior rejections were re-examined and found to rest on false premises:
- "Transaction rollback can't work — HTTP and direct DB writes use different
  connections" (`conftest.py:231-239`) is false in the current code:
  `ingest_fit(db, ...)` takes the session as an argument, and the `get_db`
  override already routes HTTP through the test's session factory.
- "PostGIS `geography` only works in `public`" is false for PostGIS 3.4 —
  `geography` and `ST_*` resolve from `public` via `search_path` regardless of
  where tables live (see `docs/research/xdist-postgis-patterns.md`).

## Decision

Replace TRUNCATE with per-test SAVEPOINT rollback (the SQLAlchemy 2.0
test-suite recipe) and re-enable xdist via schema-per-worker isolation:

- Per test: `engine.connect()` + `begin()` + sessions bound to that connection
  with `join_transaction_mode="create_savepoint"`, rolled back at teardown.
  Session-scoped engine per worker (normal pool, not `StaticPool` — that hit
  asyncpg's single-connection concurrency limit in the #280 prototype).
- Per worker (xdist): `test_<worker_id>` schema in the shared DB, with
  `search_path = <worker_schema>,public` set via `connect_args.server_settings`.
  The `postgis` extension is installed once in `public`; concurrent
  `CREATE EXTENSION IF NOT EXISTS` raises `UniqueViolation` under asyncpg, so
  coordination uses a `pg_advisory_xact_lock` + existence check (an in-DB
  variant of the FileLock pattern the decision originally named — FileLock
  was avoided because no `filelock` package is available and the advisory lock
  is simpler and in-DB).
- `asyncio_default_fixture_loop_scope = "session"` and
  `asyncio_default_test_loop_scope = "session"` are required — without both,
  asyncpg connections bind to per-test event loops ("attached to a different
  loop").

## Consequences

- Tests that hardcoded `user_id=1` (relying on `TRUNCATE`'s `RESTART IDENTITY`
  resetting the sequence) were fixed to use `seed_user.id`. One-time migration
  cost any rollback-based suite pays.
- `test_arq.py` is module-skipped pending #285 (ARQ/Redis isolation under
  xdist is a separate decision; Redis isn't isolated by schema-per-worker).
- 11 pre-existing `test_user_settings.py` failures (stale expectations from
  the Clean Architecture refactor) are `xfail(strict=True)` pending #286 —
  surfaced only because this work unblocked collection.
- The `async with conn.begin():` context manager did **not** roll back
  reliably with asyncpg + the default pool; teardown uses explicit
  `trans.rollback()`. A SQLAlchemy-async edge case worth knowing.
- Race-free: workers share nothing writable (the `postgis` extension is
  read-only after install; tables live in per-worker schemas). See #281 for
  the race-condition analysis.
- Result: 103s serial, 41-45s with `-n 4` (was >5min, often hung).

## Considered Options (rejected)

- **Keep TRUNCATE, drop `RESTART IDENTITY`** — removes per-sequence exclusive
  locks but keeps `TRUNCATE`'s per-test table locks. Dominated by rollback on
  the measured numbers.
- **`pytest-postgresql` template-DB cloning** — `CREATE DATABASE ... TEMPLATE`
  per test. Gives up the single-connection rollback speedup; only worth it if
  rollback underperforms (it doesn't).
- **Per-worker database (not schema)** — `CREATE DATABASE` can't run in a
  transaction (~0.6s/worker, more friction). Rejected for schema-per-worker.
- **`StaticPool` single connection + `begin_nested()`** — rejected in #280:
  asyncpg's single-connection concurrency limit blocks the `get_db` override
  from opening a second session on the shared connection.

## References

- #281 — the decision (isolation model + parallelism, weighed together)
- #282 — parallelism decision (xdist schema-per-worker)
- #278 — research: PostGIS 3.4 `geography` works in non-`public` schemas
- #279 — research: SQLAlchemy 2.0 `join_transaction_mode="create_savepoint"` recipe
- #280 — prototype: rollback viable on `test_upload.py` (-48% wall-clock)
- #284 — this build
- `docs/research/xdist-postgis-patterns.md`, `docs/research/pytest-isolation-strategies.md`