# Backend Architecture

> Reference: #[[file:docs/adr/0002-clean-architecture.md]]

## Layer Rules

The backend follows Clean Architecture with these layers:

### 1. Domain (`domain/`)
Pure business logic with no I/O dependencies.
- Contains: fitness calculations, metrics, peaks, zones, W'bal, resampling
- Rules: No imports from repositories, routers, or external services
- Test with: Direct function calls, no mocks needed

### 2. Repositories (`repositories/`)
Data access abstraction.
- **Protocols** (`protocols.py`): Interfaces that define repository contracts
- **Postgres** (`postgres/`): SQLAlchemy implementations
- Rules: Repositories implement protocols, never import from routers or use cases
- Test with: Integration tests against real Postgres

### 3. Use Cases (`use_cases/`)
Application business operations that orchestrate domain logic and repositories.
- Contains: IngestActivity, DeleteActivity, SyncFromProvider, RecalculateMetrics
- Rules: Depend on repository protocols (not implementations), call domain functions
- Test with: Fake repositories from `tests/fakes/`

### 4. Routers (`routers/`)
HTTP API endpoints.
- Rules: Call use cases or read directly via `select()` for simple queries
- Inject dependencies via `dependencies.py`
- Never import repository implementations directly

## Where to Put New Code

| You're adding... | Put it in... |
|------------------|--------------|
| Pure calculation (no DB) | `domain/` |
| New database operation | `repositories/protocols.py` + `postgres/` impl |
| New business operation | `use_cases/` |
| New API endpoint | `routers/` calling a use case |
| New external API client | `integrations/` |

## Dependency Injection

Use `dependencies.py` for FastAPI dependency injection:

```python
# In dependencies.py
def get_activity_repo(db: AsyncSession = Depends(get_db)) -> ActivityRepo:
    return PostgresActivityRepo(db)

ActivityRepoD = Annotated[ActivityRepo, Depends(get_activity_repo)]

# In router
@router.delete("/{activity_id}")
async def delete_activity(
    activity_id: UUID,
    current_user: CurrentUser,
    activity_repo: ActivityRepoD,
):
    use_case = DeleteActivity(activity_repo)
    deleted = await use_case.execute(current_user.id, activity_id)
    ...
```

## Testing Use Cases

Use fake repositories from `tests/fakes/`:

```python
from tests.fakes.activity_repo import FakeActivityRepo
from trainingdash.use_cases import DeleteActivity

@pytest.mark.asyncio
async def test_delete_activity():
    repo = FakeActivityRepo()
    await repo.save(sample_activity)
    
    use_case = DeleteActivity(repo)
    result = await use_case.execute(user_id=1, activity_id=activity.id)
    
    assert result is True
```

## Common Patterns

### Read-only endpoints
Simple queries can use `select()` directly in routers:
```python
result = await db.execute(select(Activity).where(...))
```

### Write operations
Always go through use cases:
```python
use_case = IngestActivity(db)
activity = await use_case.execute(user_id, fit_data, source, source_ref)
```

### Background jobs
Jobs in `worker.py` instantiate use cases:
```python
async def recalculate_metrics_job(ctx, user_id: int):
    use_case = RecalculateMetrics(db, recalculation_job_repo)
    return await use_case.execute(user_id)
```
