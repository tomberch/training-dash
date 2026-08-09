# Test Architecture

This document describes the test organization and coverage strategy for the TrainingDash backend.

## Directory Structure

```
tests/
├── unit/                    # Fast tests, no external dependencies
│   ├── domain/              # Domain logic tests (fitness, metrics, peaks, etc.)
│   └── use_cases/           # Use case tests with fake repositories
├── integration/             # Tests requiring real Postgres/Redis
├── fakes/                   # Fake repository implementations for unit tests
└── fixtures/                # Shared test data (FIT files, etc.)
```

## Test Categories

### Unit Tests (`tests/unit/`)

Unit tests run without external services. They test:

- **Domain logic** (`unit/domain/`): Pure functions for fitness calculations, metrics, peaks, zones, W'bal, resampling, polyline simplification
- **Use cases** (`unit/use_cases/`): Business operations using fake repositories
- **Infrastructure** (`unit/`): FIT parsing, crypto, activity pipeline logic

Run with: `pytest tests/unit/ -q`

### Integration Tests (`tests/integration/`)

Integration tests require real Postgres (with PostGIS) and sometimes Redis. They test:

- **API endpoints**: Full HTTP request/response cycles
- **Database operations**: Complex queries, PostGIS functions, CASCADE behavior
- **Background jobs**: SAQ worker processing
- **External integrations**: Xert sync (with mocked HTTP)

Run with: `pytest tests/integration/ -q`

## Why Integration Tests Remain

The following tests **cannot** be converted to unit tests:

| Test File | Reason |
|-----------|--------|
| `test_hausdorff.py` | Tests PostGIS `ST_HausdorffDistance` and `ST_Simplify` |
| `test_route_matching.py` | PostGIS geometry operations for route matching |
| `test_comparison.py` | Distance-based gap calculations with real DB |
| `test_tiles.py` | External HTTP tile proxy calls |
| `test_xert_sync.py` | External API integration, credential storage |
| `test_activities.py` | CASCADE deletes, route maintenance, full ingest |
| `test_upload.py` | Full ingest pipeline with DB persistence |
| `test_batch_import.py` | Batch mode fitness model interactions |
| `test_pmc.py`, `test_fitness.py` | Complex time-series queries |
| `test_power_curve.py`, `test_records.py` | Aggregation queries |
| `test_metrics_api.py` | Full API flow with threshold/zone logic |
| `test_user_settings.py` | User preferences with DB persistence |
| `test_notifications.py` | Notification creation and queries |

## Fake Repositories

Fake implementations in `tests/fakes/` implement the same protocols as production repositories:

- `FakeActivityRepo` - In-memory activity storage
- `FakeRecalculationJobRepo` - In-memory job tracking
- `FakeUserRepo` - In-memory user storage
- `FakeCredentialsRepo` - In-memory credentials storage
- (etc.)

Use fakes for:
- Testing use cases without database
- Testing business logic in isolation
- Fast feedback during development

## Coverage Gaps

### Current Gaps

1. **IngestActivity use case**: Not unit tested because it depends heavily on FIT parsing and the activity pipeline. Covered by integration tests.

2. **SyncFromProvider use case**: Complex provider interactions make it difficult to unit test meaningfully. Covered by `test_xert_sync.py` integration tests.

3. **Repository implementations**: Postgres repositories are tested through integration tests only. The protocols they implement are tested via fakes.

### Intentional Non-Coverage

1. **OAuth flows**: Tested only via integration tests due to cookie/session complexity
2. **PostGIS functions**: Cannot be faked, must use real Postgres
3. **CASCADE behavior**: Relies on database constraints

## Running Tests

```bash
# All unit tests (fast, ~5s)
pytest tests/unit/ -q

# All integration tests (slower, requires Docker)
pytest tests/integration/ -q

# Specific test file
pytest tests/unit/use_cases/test_delete_activity.py -v

# With coverage
pytest tests/unit/ --cov=trainingdash --cov-report=term-missing
```

## Adding New Tests

1. **Pure logic** → `tests/unit/domain/`
2. **Use case with repos** → `tests/unit/use_cases/` with fakes
3. **API endpoint** → `tests/integration/`
4. **Database query** → `tests/integration/`
5. **External service** → `tests/integration/` with mocks

When adding a use case test:
1. Create fake repos if needed in `tests/fakes/`
2. Mock external calls (Redis, external APIs)
3. Test happy path, error handling, and edge cases
