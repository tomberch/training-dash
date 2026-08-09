# ADR 0002: Clean Architecture Refactor

## Status

Accepted

## Context

The backend has a flat module structure with ~25 files at the root of `src/trainingdash/`. This causes friction for both humans and AI coding agents:

- **Finding where code lives** — DB queries appear in routers, services, and standalone modules. No single answer to "where does this query go?"
- **Understanding what a change affects** — Without clear boundaries, changing the Activity model means scanning many files to find all usages.
- **Adding new features** — No established pattern for "where does new code go?", so each addition is a judgment call.

We considered two approaches:

1. **Full Clean Architecture** — Separate domain entities (plain Python) from ORM models, abstract repository protocols with concrete implementations, strict dependency rules between layers.
2. **Pragmatic layering** — SQLAlchemy models serve as domain entities, repositories encapsulate queries, use cases orchestrate workflows, but no entity mapping layer.

## Decision

We will adopt a **pragmatic Clean Architecture** with the following structure:

```
src/trainingdash/
├── app.py                      # FastAPI entry point
├── worker.py                   # arq entry point
├── config.py                   # Environment settings
├── auth.py                     # JWT, password hashing, CurrentUser dependency
├── crypto.py                   # Fernet encryption
├── dependencies.py             # Dependency wiring (repos → use cases)
│
├── domain/                     # Pure business logic (no I/O)
│   ├── fitness.py              # TSS, NP, IF
│   ├── pmc.py                  # CTL/ATL/TSB
│   ├── peaks.py                # Peak detection
│   ├── wbal.py                 # W'bal calculation
│   ├── zones.py                # HR/power zones
│   ├── metrics.py              # Other calculations
│   ├── thresholds.py           # FTP/LTHR logic
│   ├── polyline.py             # Polyline encoding
│   ├── resampler.py            # Time-series resampling
│   └── title_generator.py      # Activity title generation
│
├── use_cases/                  # Application workflows (classes with execute())
│   ├── ingest_activity.py
│   ├── delete_activity.py
│   ├── sync_from_provider.py
│   ├── recalculate_metrics.py
│   └── ...
│
├── repositories/               # Data access
│   ├── protocols.py            # Abstract interfaces
│   └── postgres/
│       ├── db.py               # Session management
│       ├── models.py           # SQLAlchemy models
│       ├── activity_repo.py
│       ├── user_repo.py
│       ├── route_repo.py
│       └── ...
│
├── integrations/               # External APIs
│   ├── protocols.py            # SyncProvider protocol
│   ├── geocoding.py            # Reverse geocoding
│   ├── garmin/
│   │   └── client.py
│   └── xert/
│       └── client.py
│
└── routers/                    # HTTP layer (thin, calls use cases)
    ├── activities.py
    ├── admin.py
    ├── analytics.py
    ├── auth.py
    ├── user.py
    └── serializers.py
```

### Key decisions within this structure:

1. **Use cases are classes with `execute()`** — Dependencies injected via constructor, one class per workflow. Easier to test than functions with many parameters.

2. **Repositories use protocols** — Abstract interfaces in `repositories/protocols.py`, concrete Postgres implementations in `repositories/postgres/`. Enables fast unit tests with in-memory fakes.

3. **Dependencies wired in `dependencies.py`** — Centralized FastAPI dependency functions. Routers import use cases from here, stay thin.

4. **SQLAlchemy models are not separated from domain** — No mapping layer between "domain entities" and "ORM models". The models live in `repositories/postgres/models.py` and flow through the system. Pure domain logic in `domain/` works with primitives, not models.

5. **Entry points stay at root** — `app.py` and `worker.py` are how you run the application. They wire up frameworks to call use cases.

6. **Background jobs become use cases** — `jobs.py` disappears; its logic moves to use cases. Worker just calls use cases, same as routers.

### Dependency rules:

- `routers/` → `use_cases/`, `dependencies.py`
- `use_cases/` → `domain/`, `repositories/protocols.py`, `integrations/protocols.py`
- `repositories/postgres/` → `repositories/protocols.py`
- `domain/` → nothing (pure)
- `integrations/*` → `integrations/protocols.py`

## Consequences

**Benefits:**

- **Clear answers for agents**: "Where does DB access go?" → `repositories/postgres/`. "Where does business logic go?" → `domain/` if pure, `use_cases/` if orchestration. "Where does a new endpoint go?" → `routers/`, calling a use case.
- **Testable without database** — Use cases can be tested with fake repos, domain is pure functions.
- **Explicit boundaries** — Changes to persistence don't leak into business logic.
- **Consistent patterns** — Every new feature follows the same structure.

**Drawbacks:**

- **More files** — A simple feature touches router, use case, possibly repo. More navigation.
- **Initial refactoring cost** — Moving existing code into the new structure is significant work.
- **Learning curve** — Contributors need to understand the layering to contribute effectively.

**Mitigations:**

- Agent instructions can encode the rules ("use cases are classes with `execute()`").
- The structure is documented here and can be referenced.
- Migration can be incremental — new code follows the pattern, old code migrates over time.

## Why not full Clean Architecture?

We rejected separate domain entities (plain Python dataclasses mapped to/from SQLAlchemy models) because:

- **Postgres is non-negotiable** — PostGIS is load-bearing for route matching. We're not swapping databases.
- **The domain is mostly computation** — `fitness.py`, `pmc.py`, `peaks.py` already work with primitives. The heavy logic doesn't need ORM-free entities.
- **Mapping adds bugs** — Forgetting to map a new field is a common source of errors.

The pragmatic approach captures ~80% of the benefit with ~30% of the ceremony.
