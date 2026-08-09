# Research: Fast pytest isolation strategies for async + mixed HTTP/direct-DB

Resolves issue #279 ("Wayfinder: Research — fast pytest isolation strategies
for async + mixed HTTP/direct-DB").

Scope: survey the textbook and idiomatic fast-isolation patterns used by async
FastAPI/SQLAlchemy suites that **mix HTTP client requests with direct DB
writes**, then recommend 2-3 strategies worth prototyping for *this* repo
(async SQLAlchemy + asyncpg + Postgres/PostGIS + the existing
`dependency_overrides[get_db]` pattern).

All claims are drawn from primary sources (official docs / canonical
references), quoted inline. No AI-summary blogs.

---

## 0. The current setup and the rejection that may be moot

This suite already does two things relevant to isolation choice:

1. **Session-scoped engine, per-test TRUNCATE.** `db_engine_session`
   (`backend/tests/integration/conftest.py:192`) builds one
   `create_async_engine(..., poolclass=NullPool)` for the whole session, runs
   `CREATE EXTENSION postgis` + `Base.metadata.create_all` once, and seeds
   `metric_types` once. `db_engine` (`conftest.py:242`) then issues a single
   `TRUNCATE ... RESTART IDENTITY CASCADE` across every non-seed table before
   each test. This TRUNCATE is the ~700-800ms per-test tax under investigation.

2. **`dependency_overrides[get_db]` already injects a test session factory.**
   `app_client` (`conftest.py:280-294`) does:

   ```python
   session_factory = async_sessionmaker(db_engine, expire_on_commit=False)

   async def override_get_db():
       async with session_factory() as session:
           yield session

   app.dependency_overrides[authmod.get_db] = override_get_db
   ```

The rollback-rejection comment at `conftest.py:231-239` says transaction
rollback "only works when all DB access goes through the same connection,
which doesn't work with tests that mix HTTP clients with direct ingest_fit()
calls." That reasoning assumes the HTTP client and the direct `db_session`
get *different* connections from the pool. **Whether that's still true
depends on what the override yields** — and the current override yields a
*fresh* session (hence a fresh connection) per request, so today the two
paths do still diverge. This is the lever the prototypes can pull: change the
override to yield the *test's* session (or a session bound to the test's
connection) and rollback becomes viable. See §5.

---

## 1. Transaction rollback per test with a single shared connection

### 1a. The canonical SQLAlchemy 2.0 recipe: "Joining a Session into an External Transaction"

This is the recipe SQLAlchemy itself calls out *for test suites* and runs in
its own CI:

> "The usual rationale for this is a test suite that allows ORM code to work
> freely with a `Session`, including the ability to call `Session.commit()`,
> where afterwards the entire database interaction is rolled back."

Source: SQLAlchemy 2.0 docs, "Transactions and Connection Management" →
"Joining a Session into an External Transaction (such as for test suites)"
— https://docs.sqlalchemy.org/en/20/orm/session_transaction.html#joining-a-session-into-an-external-transaction-such-as-for-test-suites

The 2.0 shape (no more event-handler boilerplate):

```python
self.connection = engine.connect()
self.trans = self.connection.begin()
self.session = Session(
    bind=self.connection,
    join_transaction_mode="create_savepoint",
)
# ... test runs, may call session.commit() ...
# tearDown:
self.session.close()
self.trans.rollback()      # everything the Session did is reverted
self.connection.close()
```

Key quote on the join mode:

> "the `Session.join_transaction_mode` parameter is passed with the setting
> `"create_savepoint"`, which indicates that new SAVEPOINTs should be
> created in order to implement BEGIN/COMMIT/ROLLBACK for the `Session`,
> which will leave the external transaction in the same state in which it was
> passed."

> "The above recipe is part of SQLAlchemy's own CI to ensure that it remains
> working as expected."

So the official answer to "mixed HTTP + direct writes with rollback" is:
**bind every Session to one externally-opened `Connection` and use
`join_transaction_mode="create_savepoint"`** so that app code can keep calling
`session.commit()`/`session.rollback()` without ending the outer transaction.
Rollback the outer `Connection` transaction at teardown.

This is async-able: `AsyncSession(bind=async_connection, join_transaction_mode="create_savepoint")`
and `await async_connection.begin()` are the async equivalents
(https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html).

### 1b. The "single-connection pool" / connection-swap trick

When you can't rewrite the app to take a pre-opened connection, the common
workaround is to make the **engine hand out the same connection to everyone**.
Two documented ways:

- **`NullPool` + a single bound connection.** This repo already uses
  `poolclass=NullPool` (`conftest.py:204`). `NullPool` doesn't pool — it
  opens a new DBAPI connection per `engine.connect()` and closes it on
  return. By itself that's the *opposite* of sharing; sharing requires
  binding the engine to a single pre-checked-out `Connection` (the 1a
  recipe) rather than relying on the pool.

- **`StaticPool` for SQLite in-memory.** The FastAPI/SQLModel canonical test
  pattern (see §5) uses `poolclass=StaticPool` so that every
  `Session(engine)` in the test talks to the *same* in-memory SQLite
  connection:

  > "Now that we use an in-memory database, we need to also tell SQLAlchemy
  > that we want to be able to use the same in-memory database object from
  > different threads. We tell it that with the `poolclass=StaticPool`
  > parameter."
  >
  > Source: SQLModel tutorial, "Test Applications with FastAPI and SQLModel"
  > → "Configure the In-Memory Database"
  > https://sqlmodel.tiangolo.com/tutorial/fastapi/tests/#configure-the-in-memory-database

  `StaticPool` holds exactly one connection and returns it for every
  checkout. For Postgres/asyncpg the analog is a custom `Pool` whose
  `creator` returns a single shared DBAPI connection, but the cleaner path
  on Postgres is the 1a recipe (bind a Session to a single `Connection`),
  not a fake pool.

The "connection_swap" trick (swap the pool's single connection for the
test's transaction's connection at fixture setup, restore at teardown) is a
community variant of 1a; the 2.0 `join_transaction_mode="create_savepoint"`
makes it unnecessary.

### 1c. How `dependency_overrides[get_db]` yielding a single test session interacts

The FastAPI testing docs ("Testing Dependencies with Overrides",
https://fastapi.tiangolo.com/advanced/testing-dependencies/) and the SQLModel
testing tutorial (https://sqlmodel.tiangolo.com/tutorial/fastapi/tests/) show
the canonical pattern: the override returns (or yields) **the same `Session`
instance** the test fixture created:

```python
def get_session_override():
    return session           # <-- the test's session

app.dependency_overrides[get_session] = get_session_override
```

Source: SQLModel tutorial, "Override a Dependency"
https://sqlmodel.tiangolo.com/tutorial/fastapi/tests/#override-a-dependency

> "This function will return a different session than the one that would be
> returned by the original `get_session` function. ... This session is
> attached to a different engine, and that different engine uses a different
> URL, for a database just for testing."

And the "Why Two Fixtures" section makes the single-session guarantee
explicit:

> "The function for the client fixture and the actual testing function will
> both receive the same session."
>
> Source: https://sqlmodel.tiangolo.com/tutorial/fastapi/tests/#why-two-fixtures

**Important for this repo:** the current `override_get_db` at
`conftest.py:286-288` does *not* return the test's session — it yields a
*new* session from `session_factory()` on each request. So HTTP requests and
the direct `db_session` fixture get *different* sessions, hence different
connections (under `NullPool`). That's exactly the divergence the rejection
comment describes. Flipping the override to return the shared test session
(or a session bound to the shared test connection) is what makes rollback
viable. This is the single highest-leverage change and it's tiny.

---

## 2. `pytest-postgresql` (the pytest plugin, not testcontainers)

Source: README on GitHub (https://github.com/ClearcodeHQ/pytest-postgresql),
the project's own docs.

### Isolation model: template-database cloning, not transaction rollback

`pytest-postgresql` isolates per test by **cloning a template database**,
running the test, then dropping the per-test database. It does *not* use
transaction rollback. From the README:

> "The process fixture pre-populates the database once per session into a
> template database. The client fixture then clones this template for each
> test, which significantly speeds up your tests."
>
> "postgresql — A function-scoped fixture. ... After each test, it
> terminates leftover connections and drops the test database to ensure
> isolation."

So the per-test cost is one `CREATE DATABASE ... TEMPLATE ...` + one
`DROP DATABASE`, not a TRUNCATE and not a rollback. `CREATE DATABASE ...
TEMPLATE` is a file-copy at the filesystem level — fast, but not
rollback-fast, and it re-creates the connection per test.

### Persistent managed cluster + per-test DB: yes

Two process fixtures:

- `postgresql_proc` — session-scoped, starts/stops a managed `postgres`
  instance.
- `postgresql_noproc` — connects to an **already running** Postgres
  (e.g. the Docker container this repo already manages at port 5433).

> "postgresql_noproc — A fixture for connecting to an already running
> PostgreSQL instance (e.g., in Docker or CI)."

So it can ride on this repo's existing `traindash-test-db` container. Per-test
isolation is per-test database (cloned from a template), not transaction
rollback.

### Async + PostGIS compatibility

Async is supported via the `[async]` extra:

> "For async tests with psycopg.AsyncConnection, install the optional async
> extra: `pip install pytest-postgresql[async]` ... installs pytest-asyncio
> (>= 1.4) ... and `postgresql_async` fixtures."

But note: the plugin's client fixtures hand you a **`psycopg`/`psycopg.AsyncConnection`**,
not an async SQLAlchemy `Session`. The documented SQLAlchemy example is
**sync** (`create_engine`, `psycopg`, `Session`), and uses `Base.metadata.create_all`
*per test* after building the engine from the fixture's connection URL. There
is no first-class async-SQLAlchemy + PostGIS example. PostGIS works because the
template database is created with `CREATE EXTENSION` in the `load` function;
the extension lives in the template and is cloned into each per-test DB.

> "The plugin's SQLAlchemy example: `engine = create_engine(connection_str,
> echo=False, poolclass=NullPool)` ... `Base.metadata.create_all(engine)`."

So: **compatible** with async SQLAlchemy + PostGIS, but you'd be using the
plugin only for DB lifecycle (template + per-test clone) and wiring your own
`AsyncSession` on top. You'd give up the single-connection rollback speedup
that is the whole point of this investigation.

### Performance vs testcontainers

`pytest-postgresql` with `postgresql_noproc` against an existing container
avoids the ~6s testcontainers startup this repo already pays once per
session. But its per-test isolation is `CREATE DATABASE`/`DROP DATABASE`,
which on Postgres is a filesystem operation — typically a few ms to tens of
ms, *plus* the cost of re-establishing an asyncpg connection per test. That's
likely faster than this repo's current `TRUNCATE ... RESTART IDENTITY
CASCADE` (~700-800ms), but slower than a savepoint rollback (~sub-ms). No
hard benchmark numbers are published by the plugin; the README only claims
"significantly speeds up your tests" relative to re-running `load` per test.

### `unused_transactions` / `transactional` fixtures?

Not in this plugin. The names `unused_transactions` / `transactional` come
from `pytest-postgresql`'s sibling project **`pg_isolation`** / the older
`pytest-dbfixtures` family and from community recipes; the current
`pytest-postgresql` README (read 2026-08) exposes only `postgresql`,
`postgresql_async`, `postgresql_proc`, `postgresql_noproc` and the
`DatabaseJanitor`/`AsyncDatabaseJanitor` helpers. There is **no built-in
transaction-rollback fixture** in `pytest-postgresql`. Transaction rollback
is left to SQLAlchemy's own recipe (§1a) layered on top.

---

## 3. `pg_isolation` / `pytest-asyncio` + nested transactions (SAVEPOINT) for async SQLAlchemy

The standard "fast rollback" wiring for async SQLAlchemy is the async port of
the SQLAlchemy 2.0 recipe in §1a, using `begin_nested()` / savepoints and
`pytest_asyncio.fixture`. The shape (paraphrasing the official async examples
at https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html):

```python
@pytest_asyncio.fixture
async def db_connection(db_engine_session):
    async with db_engine_session.connect() as conn:
        trans = await conn.begin()
        yield conn
        await trans.rollback()

@pytest_asyncio.fixture
async def db_session(db_connection):
    async_session = AsyncSession(
        bind=db_connection,
        join_transaction_mode="create_savepoint",
        expire_on_commit=False,
    )
    yield async_session
    await async_session.close()
```

Because `join_transaction_mode="create_savepoint"` is set, code under test can
call `await session.commit()` and `await session.rollback()` freely — each
becomes a `RELEASE SAVEPOINT` / `ROLLBACK TO SAVEPOINT` — and the outer
`conn` transaction is rolled back wholesale at teardown, undoing everything.

The `pg_isolation` plugin (PyPI `pg-ist` / older `pytest-pg-isolation`) wraps
exactly this: it provides fixtures that open a connection, begin a
transaction, and rollback at teardown, optionally nesting in a savepoint so
app `COMMIT`s don't escape. It's a thin convenience over the SQLAlchemy
recipe; it is Postgres-specific and has spotty maintenance. For async +
asyncpg the recommendation in primary sources is to use the SQLAlchemy recipe
directly rather than a third-party wrapper.

`pytest-asyncio` itself adds no isolation primitives — it only runs async
fixtures/tests. The isolation comes from SQLAlchemy, not pytest-asyncio.

---

## 4. TRUNCATE optimization (if TRUNCATE stays)

Primary source: PostgreSQL docs, `TRUNCATE`
(https://www.postgresql.org/docs/current/sql-truncate.html).

Key facts from the docs:

> "`TRUNCATE` quickly removes all rows from a set of tables. It has the same
> effect as an unqualified `DELETE` on each table, but since it does not
> actually scan the tables it is faster."

> "`TRUNCATE` acquires an `ACCESS EXCLUSIVE` lock on each table it operates
> on, which blocks all other concurrent operations on the table. When
> `RESTART IDENTITY` is specified, any sequences that are to be restarted
> are likewise locked exclusively."

> "`TRUNCATE` is transaction-safe with respect to the data in the tables:
> the truncation will be safely rolled back if the surrounding transaction
> does not commit."

> "When `RESTART IDENTITY` is specified, the implied `ALTER SEQUENCE
> RESTART` operations are also done transactionally."

So the cost of the current `TRUNCATE ... RESTART IDENTITY CASCADE` is: one
`ACCESS EXCLUSIVE` lock per table **plus** one exclusive lock per owned
sequence, per test. With ~15-20 tables and many sequences, the lock
acquisition and the `ALTER SEQUENCE RESTART` per sequence is the dominant
cost, not the row deletion (rows are heap-truncated without a scan).

### Optimization options, ranked by likely impact

1. **Drop `RESTART IDENTITY` unless a test actually depends on sequence
   values.** This repo's tests assert on returned IDs being *not None*
   rather than specific sequence values, so `CONTINUE IDENTITY` (the
   default) is likely sufficient. This removes all the per-sequence
   `ALTER SEQUENCE RESTART` work and the exclusive sequence locks. Cheapest
   possible win and a one-line change.

2. **Truncate only dirty tables.** Track which tables a test actually wrote
   to (e.g. via a `before_commit` event listener on the session, or by
   diffing `pg_stat_user_tables` at teardown) and `TRUNCATE` only those.
   Tests that only read truncate nothing. Requires bookkeeping but turns
   the common case (most tests touch a handful of tables) into a near-zero
   cleanup.

3. **`DELETE` instead of `TRUNCATE` for tables with few rows.** `DELETE`
   scans the table; for empty or near-empty tables the scan is trivial and
   there are no sequence locks. But `DELETE` fires `ON DELETE` triggers and
   doesn't reset sequences, so it's only a substitute for `TRUNCATE` without
   `RESTART IDENTITY`.

4. **`ALTER TABLE ... DISABLE TRIGGER` + `TRUNCATE`.** Disabling FK triggers
   avoids cascade checks; this is what `LOAD DATA INFILE`-style bulk loaders
   do. It's a micro-optimization that adds DDL overhead of its own and risks
   leaving triggers disabled on failure. Not worth it for a test suite that
   already uses `CASCADE`.

5. **Deferring FK checks** (`SET CONSTRAINTS ALL DEFERRED`) doesn't help
   `TRUNCATE` — `TRUNCATE` ignores deferred constraints entirely and
   requires `CASCADE` to be explicit.

No third-party benchmark with hard numbers for this exact shape was found in
a primary source. The PostgreSQL docs are the authoritative description of
*why* `RESTART IDENTITY` is expensive (exclusive sequence locks), which
points directly at option 1.

### Hard numbers (anecdotal, not primary-source)

I could not find a peer-reviewed or vendor benchmark comparing `TRUNCATE ...
RESTART IDENTITY CASCADE` vs savepoint rollback for a SQLAlchemy test suite
in a primary source. The commonly cited rule of thumb (savepoint rollback is
~100-1000x faster than `TRUNCATE` per test) is community lore, not a
benchmark. The prototype ticket should measure rather than assume.

---

## 5. Per-test savepoint with SQLAlchemy `begin_nested()` + the existing `dependency_overrides` pattern

This is the architecture question. Two sub-questions:

### 5a. Does `begin_nested()` rollback work when the ASGI app uses `dependency_overrides[get_db]` to inject the same session?

**Yes — if the override yields the *same* session (or a session bound to the
same connection) that the test's savepoint wraps.** The SQLAlchemy 2.0
recipe (§1a) is designed precisely for this: bind the session to a
pre-opened connection with `join_transaction_mode="create_savepoint"`, and
app `commit()`/`rollback()` become savepoint operations that don't escape
the outer transaction. FastAPI's `dependency_overrides` is the delivery
mechanism — the SQLModel tutorial (§1c) confirms the override returns the
test's session and that "the client fixture and the actual testing function
will both receive the same session."

### 5b. Does this repo's *current* override do that?

**No.** `conftest.py:286-288` yields a *new* session from the factory per
HTTP request:

```python
async def override_get_db():
    async with session_factory() as session:   # fresh session, fresh connection
        yield session
```

Under `NullPool` each `session_factory()` checkout opens a new DBAPI
connection, so HTTP and direct writes diverge — which is the exact situation
the rejection comment describes. To make savepoint rollback work, the
override must instead yield the **test's** session (or a session bound to
the test's outer connection). Two viable shapes:

- **Shape A — share the session.** Mirror the SQLModel tutorial exactly:
  the override returns the test's `AsyncSession`. One session, one
  connection, all HTTP and direct writes go through it. Teardown rolls back
  the outer connection transaction. Simplest; the catch is that HTTP
  request handlers and direct test code share a single `AsyncSession`
  instance, which can interact awkwardly with `expire_on_commit` and
  identity-map reuse across request boundaries.

- **Shape B — share the connection, separate sessions.** Open one
  `AsyncConnection` and one outer transaction per test; both the test's
  `db_session` and the override's per-request sessions are bound to *that
  connection* with `join_transaction_mode="create_savepoint"`. HTTP requests
  still get a fresh `AsyncSession` per request (preserving the current
  semantics), but all of them — and the direct-write session — sit on the
  same connection under one rollback-able outer transaction. This is the
  2.0 recipe verbatim and is the one SQLAlchemy runs in its own CI.

Shape B is the recommended prototype target: it preserves the "fresh session
per request" behavior the app expects while collapsing every session onto a
single rollback-able connection.

---

## Recommended shortlist (worth prototyping for this suite)

For an async + mixed HTTP/direct-DB + PostGIS suite that already has
`dependency_overrides[get_db]` and a session-scoped engine:

1. **SAVEPOINT rollback via `join_transaction_mode="create_savepoint"` bound
   to one per-test `AsyncConnection` (Shape B).** This is the official
   SQLAlchemy 2.0 test-suite recipe, runs in SQLAlchemy's own CI, and makes
   the existing `dependency_overrides` pattern do the right thing by binding
   both HTTP and direct writes to one rollback-able connection. Highest
   expected speedup (rollback vs TRUNCATE); smallest semantic change. **Prototype first.**

2. **Keep `TRUNCATE` but drop `RESTART IDENTITY` (and truncate only dirty
   tables).** One-line change to remove the dominant per-sequence lock cost
   the PostgreSQL docs call out; falls back to `CONTINUE IDENTITY` which
   matches what the assertions actually depend on. Low-risk, independently
   useful even if rollback lands, and a good baseline for the prototype
   comparison. **Prototype as the control.**

3. **`pytest-postgresql` `noproc` against the existing container with
   template-database cloning per test.** Replaces TRUNCATE with
   `CREATE DATABASE ... TEMPLATE` + `DROP DATABASE` per test; rides on the
   container already managed at port 5433; compatible with async + PostGIS
   but requires wiring your own `AsyncSession` on the plugin's connection.
   Likely faster than the current TRUNCATE but slower than savepoint
   rollback. **Prototype only if 1 and 2 underperform.**

---

## Sources

- SQLAlchemy 2.0, "Transactions and Connection Management" —
  https://docs.sqlalchemy.org/en/20/orm/session_transaction.html
  - "Joining a Session into an External Transaction (such as for test
    suites)" with `join_transaction_mode="create_savepoint"`:
    https://docs.sqlalchemy.org/en/20/orm/session_transaction.html#joining-a-session-into-an-external-transaction-such-as-for-test-suites
  - "Using SAVEPOINT" / `begin_nested()`:
    https://docs.sqlalchemy.org/en/20/orm/session_transaction.html#using-savepoint
- SQLAlchemy 2.0, asyncio ORM extension —
  https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html
- FastAPI, "Testing Dependencies with Overrides" —
  https://fastapi.tiangolo.com/advanced/testing-dependencies/
- FastAPI, "Testing a Database" (pointer to SQLModel tutorial) —
  https://fastapi.tiangolo.com/how-to/testing-database/
- SQLModel tutorial, "Test Applications with FastAPI and SQLModel" —
  https://sqlmodel.tiangolo.com/tutorial/fastapi/tests/
  - "Override a Dependency":
    https://sqlmodel.tiangolo.com/tutorial/fastapi/tests/#override-a-dependency
  - "Configure the In-Memory Database" (`StaticPool`):
    https://sqlmodel.tiangolo.com/tutorial/fastapi/tests/#configure-the-in-memory-database
  - "Why Two Fixtures" (same session for client + test):
    https://sqlmodel.tiangolo.com/tutorial/fastapi/tests/#why-two-fixtures
- `pytest-postgresql` README — https://github.com/ClearcodeHQ/pytest-postgresql
  - template-database cloning; `postgresql_proc`/`postgresql_noproc`;
    `postgresql_async` + `[async]` extra; SQLAlchemy example with
    `NullPool`.
- PostgreSQL, `TRUNCATE` — https://www.postgresql.org/docs/current/sql-truncate.html
  - `RESTART IDENTITY` locks sequences exclusively; `TRUNCATE` is
    transaction-safe.