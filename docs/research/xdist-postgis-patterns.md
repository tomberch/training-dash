# Research: pytest-xdist + PostGIS parallel patterns

Resolves: tomberch/training-dash#278
Suite: `backend/tests/integration/` — serial-only today; rationale documented at
`backend/tests/integration/conftest.py:198-201`. Image in use:
`postgis/postgis:16-3.4` (Postgres 16, PostGIS 3.4.3). `pytest-xdist>=3.8.0`
is installed but unused.

## TL;DR verdict

The "geography only works in the `public` schema" claim in `conftest.py:198-201`
is **false for PostGIS 3.4**. PostGIS can be installed into any schema with
`CREATE EXTENSION postgis SCHEMA <schema>`, and the `geography` type then lives
in that schema and works there. **Both** viable parallel strategies are open:

- **Preferred (lowest setup cost, fits the existing persistent container):
  schema-per-worker isolation** — one shared DB, each xdist worker gets its
  own schema, installs `postgis` into it, sets `search_path` to it. This is the
  standard pytest-xdist Postgres pattern and it works for PostGIS.
- **Per-worker database isolation** — each worker gets its own logical DB with
  `CREATE EXTENSION postgis`. Also works, but ~0.6s extra per worker for
  `CREATE DATABASE` vs ~0.1s per worker for `CREATE SCHEMA`, and `CREATE
  DATABASE` cannot run inside a transaction so it complicates fixture teardown.

Recommendation: **schema-per-worker with `postgis` installed per-schema** is
the right pattern for this suite. The serial-only rationale is outdated and
the existing comment should be corrected.

---

## Question 1: Per-worker *database* (not schema) isolation

### Does it work?

Yes. Each xdist worker creates its own logical database (`CREATE DATABASE
gw<n>`) and runs `CREATE EXTENSION postgis` in it. The `postgis/postgis:16-3.4`
image installs the `postgis` extension's control/script files into the image
shared dir, so any new database created in the cluster can `CREATE EXTENSION
postgis` independently — the extension is per-database, not per-cluster.

The `postgis/postgis` image's `initdb-postgis.sh` only pre-installs the
extension into the default database (the one named after `POSTGRES_USER`/`POSTGRES_DB`).
Databases you create afterward are plain Postgres databases until you run
`CREATE EXTENSION postgis` in them. Confirmed empirically:

```
CREATE DATABASE w0;          # ~0.3s
\c w0
CREATE EXTENSION postgis;    # ~0.3s
```

### Startup cost

Measured against a warm `postgis/postgis:16-3.4` container on the dev machine:

| Operation                                   | Time     |
|---------------------------------------------|----------|
| `CREATE DATABASE` + `CREATE EXTENSION postgis` | ~0.6 s/worker |
| `CREATE SCHEMA` + `CREATE EXTENSION postgis SCHEMA x` (×4 workers, one txn) | ~0.4 s total (~0.1 s/worker) |

The dominant cost is the PostGIS container boot itself (~3-5 s), which happens
once per session and is already amortized by the suite's persistent
`traindash-test-db` container (`conftest.py:96-154`).

### With testcontainers-python

`testcontainers-python` has **no first-class xdist integration** and no
documented per-worker-DB pattern. Searching the repo's issues for "xdist" turns
up only generic concurrency bugs (e.g. #567 "concurrency causes Premature
destruction of containers and networks (e.g. w/pytest-xdist)"), not a
supported workflow. The `PostgresContainer` class spins one container per
instance; you would have to write the per-worker-DB logic yourself against a
single shared container using `psycopg`/`sqlalchemy`.

The current `conftest.py` already manages its own persistent container
(`traindash-test-db` on port 5433) and only falls back to `PostgresContainer`
when that container is unavailable (`conftest.py:96-189`). For parallelism the
testcontainers fallback path is not the interesting one; the persistent
container is.

### Practical notes

- `CREATE DATABASE` cannot run inside a transaction block. Any fixture using
  `CREATE DATABASE` must run on an autocommit connection (the `pytest-postgresql`
  plugin calls this out explicitly with its `load_autocommit` option — see
  https://github.com/dbfixtures/pytest-postgresql README, "Pre-populating the
  database for tests").
- Workers need distinct DB names. The xdist `worker_id` fixture ("gw0",
  "gw1", ...) or the `PYTEST_XDIST_WORKER` env var is the standard way to derive
  a unique name (pytest-xdist how-to, "Identifying the worker process during a
  test": https://pytest-xdist.readthedocs.io/en/latest/how-to.html).
- pytest-postgresql's `postgresql_noproc` `dbname` argument row in its config
  table is literally annotated "handles xdist" — the plugin does have xdist
  awareness for the noproc (external-server) path, deriving per-worker dbnames.
  (https://github.com/dbfixtures/pytest-postgresql — Configuration table.)

### Verdict for this suite

Viable but more setup than schema-per-worker, and the `CREATE DATABASE`
outside-transaction constraint adds friction. Not the recommended path.

---

## Question 2: `CREATE EXTENSION postgis` inside a non-`public` schema

### Is the "geography only in public" claim current?

**No.** It is incorrect for PostGIS 3.4 (and has been incorrect for as long as
the extension has supported relocation at install time). The claim in
`conftest.py:198-201` reads:

> The geography type is only available in the public schema where postgis
> extension is installed. Schema-per-worker isolation doesn't work.

This conflates two things that are both wrong:

1. **"only available in the public schema"** — false. The `geography` type is
   created in whatever schema `CREATE EXTENSION postgis SCHEMA <s>` targets.
2. **"where postgis extension is installed"** (implying it's pinned to public)
   — false. The extension is not pinned to `public`; it installs into the
   schema named in the `SCHEMA` clause (or the default creation schema).

### Evidence from primary sources

**PostGIS control file** (`postgis/postgis:16-3.4` image,
`/usr/share/postgresql/16/extension/postgis.control`):

```
# postgis extension
comment = 'PostGIS geometry and geography spatial types and functions'
default_version = '3.4.3'
module_pathname = '$libdir/postgis-3'
relocatable = false
```

`relocatable = false` means you cannot `ALTER EXTENSION postgis SET SCHEMA`
*after* install — but it does **not** pin the install schema. The install-time
`SCHEMA` clause is honored. (PostgreSQL docs, `CREATE EXTENSION`:
https://www.postgresql.org/docs/current/sql-createextension.html — "The name
of the schema in which to install the extension's objects, given that the
extension allows its contents to be relocated.")

**PostGIS administration docs** show other PostGIS extensions installed in
non-`public` schemas as a matter of course
(https://postgis.net/docs/postgis_administration.html#create_new_db_extensions):

```
\dx postgis*
List of installed extensions
-[ RECORD 1 ]--- ...
Name        | postgis
Schema      | public
-[ RECORD 3 ]---
Name        | postgis_tiger_geocoder
Schema      | tiger
-[ RECORD 4 ]---
Name        | postgis_topology
Schema      | topology
```

So PostGIS routinely installs sub-extensions into non-`public` schemas; the
core `postgis` extension is not different in kind.

### Empirical confirmation (against `postgis/postgis:16-3.4`)

```
CREATE DATABASE wtest;
\c wtest
CREATE SCHEMA worker_a;
CREATE EXTENSION postgis SCHEMA worker_a;

-- Where is the geography type?
SELECT t.typname, n.nspname FROM pg_type t JOIN pg_namespace n
  ON t.typnamespace=n.oid WHERE t.typname='geography';
  typname  | nspname
-----------+----------
 geography | worker_a

-- Where is geography_columns?
SELECT schemaname FROM pg_views WHERE viewname='geography_columns';
 schemaname
------------
 worker_a

-- Use it.
SET search_path TO worker_a;
CREATE TABLE t (g geography(POINT,4326));
INSERT INTO t VALUES ('SRID=4326;POINT(0 0)');
SELECT ST_AsText(g) FROM t;
 st_astext
------------
 POINT(0 0)
```

The geography type, the `geography_columns` view, and all `ST_*` functions
live in `worker_a` and work there. With `search_path = worker_a` everything
resolves unqualified, exactly as the suite's SQLAlchemy models expect.

### The one gotcha

The extension's types resolve via `search_path`. If `search_path` does not
include the schema where `postgis` was installed, you get
`ERROR: type "geography" does not exist`. Confirmed:

```
SET search_path TO public;          -- postgis is in worker_a, not public
CREATE TABLE tpub (g geography(POINT,4326));
ERROR:  type "geography" does not exist
```

So the rule for schema-per-worker is: **install `postgis` into the worker's
schema AND set `search_path` to that schema** (the suite already controls
schema creation in `db_engine_session`; adding `SET search_path` per worker
connection is a one-liner).

### Verdict for this suite

The serial-only rationale is factually wrong for PostGIS 3.4. Schema-per-worker
isolation works. The `conftest.py:198-201` comment should be corrected.

---

## Question 3: Alternative parallelism that doesn't need DB isolation

### pytest-split

Not investigated in depth. `pytest-split` distributes tests across *separate
pytest invocations* (CI shards) using a previously-recorded durations file.
Each shard is a full, independent pytest process — so it does NOT share a
database by design; each shard would need its own DB. It is a CI-sharding
tool, not an in-session parallelism tool, and does not solve the PostGIS
isolation question — it sidesteps it by requiring N independent DBs. Viable
for CI (run N jobs, each with its own container) but not for local `-n auto`.

### pytest-parallel

**Unmaintained / archived** (https://github.com/kevlened/pytest-parallel):
"This repository was archived by the owner on May 29, 2024." The README
itself says "The project is currently unmaintained." Its own pitch is that it
suits *threadsafe, low-state* tests (e.g. Selenium) — the opposite of a
PostGIS integration suite that mutates database state. Not viable.

### File-level parallelism with a test-DB-per-file pool

Spawn N shells, each running one test file against its own DB (or schema).
This is just a hand-rolled version of pytest-xdist with worse ergonomics —
xdist already does file-scoped distribution by default (`--dist=loadfile`),
and you give up xdist's collection, reporting, and fixture caching. Viable
as a stopgap but dominated by the xdist schema-per-worker option.

### Running test files in parallel shells (no plugin)

Same as above, with the added pain of merging test output and exit codes.
Not recommended.

### Verdict for this suite

None of these beat pytest-xdist with schema-per-worker. `pytest-split` is
the only one with a real use case here (CI sharding across separate
containers), and it's orthogonal to in-session parallelism — you can do both.

---

## Question 4: Known-good reference setups

### pytest-xdist docs — the canonical "session fixture once" pattern

The pytest-xdist how-to explicitly shows the per-worker schema/database
pattern using `worker_id` + `tmp_path_factory` + `filelock`, and calls out
database initialization as the motivating example
(https://pytest-xdist.readthedocs.io/en/latest/how-to.html, "Making
session-scoped fixtures execute only once"):

> "The example above can also be use in cases a fixture needs to execute
> exactly once per test session, like initializing a database service and
> populating initial tables."

The example uses a `FileLock` to ensure exactly-once setup; for per-worker
schemas you drop the lock and key on `worker_id`.

### pytest-postgresql — template-DB cloning, xdist-aware noproc

`pytest-postgresql` (https://github.com/dbfixtures/pytest-postgresql) is the
closest off-the-shelf plugin. Its model:

- A *process* fixture (`postgresql_proc` / `postgresql_noproc`) builds a
  **template database** once per session by running a `load` list (SQL files
  or callables — which could `CREATE EXTENSION postgis`).
- A *client* fixture (`postgresql`) clones that template per test
  (`CREATE DATABASE ... TEMPLATE ...`), giving each test a fresh DB without
  re-running the schema/extension setup.
- Its config table marks `postgresql_noproc`'s `dbname` argument as
  "handles xdist" — the noproc path derives per-worker dbnames for xdist
  runs.

This is the most production-ready pattern for fast Postgres testing in
pytest, and it composes with PostGIS (the `load` callable runs
`CREATE EXTENSION postgis` in the template). The repo's own docs cite
Warehouse (pypi.org) as a user of `DatabaseJanitor` for this approach.

### testcontainers-python — no first-class xdist pattern

As noted in Q1, `testcontainers-python` has no documented per-worker pattern.
Issue #567 ("concurrency causes Premature destruction of containers and
networks (e.g. w/pytest-xdist)") is the closest xdist-related thread and it
is a *bug report* about concurrent container teardown, not a supported
workflow. The takeaway: do not rely on spinning N containers with
testcontainers under xdist; use one shared container (which the suite
already does) and isolate inside it.

### postgis/docker-postgis

The `postgis/postgis` image
(https://github.com/postgis/docker-postgis) provides a `template_postgis`
template database alongside the default initialized database, specifically
for the "clone a PostGIS-enabled DB quickly" use case:

> "If you would prefer to use the older template database mechanism for
> enabling PostGIS, the image also provides a PostGIS-enabled template
> database called `template_postgis`."

This is directly useful for the pytest-postgresql template-clone pattern
and for any `CREATE DATABASE ... TEMPLATE template_postgis` approach.

### No blog-post-grade "high-throughput parallel PostGIS pytest" reference found

A targeted search of the primary sources (PostGIS docs, pytest-xdist docs,
testcontainers-python issues, pytest-postgresql repo) did not surface a
canonical blog write-up of *parallel PostGIS* testing specifically. The
building blocks (xdist worker_id, schema-per-worker, postgis-in-any-schema,
template-DB cloning) are all documented independently; the composition is
left to the reader. The closest ready-made composition is
pytest-postgresql's `noproc` + template + xdist-aware dbname.

---

## Recommendation for THIS suite

1. **Correct the comment at `conftest.py:198-201`.** The "geography only in
   public" claim is wrong for PostGIS 3.4.
2. **Adopt schema-per-worker isolation** under pytest-xdist:
   - Each worker derives `schema_test_<worker_id>` from the `worker_id`
     fixture.
   - The session-scoped `pg_container` fixture stays as-is (one shared
     persistent container).
   - A new session-scoped, xdist-aware fixture creates the worker's schema
     and runs `CREATE EXTENSION postgis SCHEMA <worker_schema>` once per
     worker, then sets `search_path` to the worker schema for all
     connections in that worker.
   - `Base.metadata.create_all` then creates tables in the worker's schema
     because `search_path` points there.
3. **Keep the persistent `traindash-test-db` container.** Schemas are
   cheap (~0.1 s each); the container boot (~3-5 s) is the only meaningful
   startup cost and it's already paid once.
4. **Per-worker-DB isolation is viable but not worth the `CREATE DATABASE`
   outside-transaction friction** for this suite.
5. **`pytest-split` is a complementary option for CI sharding** across
   separate containers, not a replacement for in-session xdist parallelism.

The destination stated in #278 (≤2 min full suite) may well be reachable
*without* parallelism if per-test setup tax is cut (template-DB cloning via
pytest-postgresql or `template_postgis` is the lever there). Parallelism is
an option, not a requirement; this research surveys it without committing
to it.