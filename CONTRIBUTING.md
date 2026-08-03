# Contributing to TrainDash

Thanks for your interest in contributing! This guide will help you get started.

## Getting Started

1. Fork the repository
2. Clone your fork: `git clone https://github.com/YOUR_USERNAME/training-dash.git`
3. Set up the development environment (see below)
4. Create a branch for your changes: `git checkout -b feature/your-feature-name`

## Development Setup

### Prerequisites

- Docker and Docker Compose
- Node.js 20+
- Python 3.12+ and [uv](https://docs.astral.sh/uv/)

### Backend

```bash
cd backend
uv sync                    # Install dependencies
source .venv/bin/activate  # Activate virtualenv
cp .env.example .env       # Create local config
```

Run tests:
```bash
pytest                     # All tests
pytest -x                  # Stop on first failure
pytest -k "test_name"      # Run specific test
pytest --cov               # With coverage
```

### Frontend

```bash
cd frontend
npm install
npm run dev     # Dev server on :5173
npm test        # Run tests
npm run lint    # Run linter
```

### Full Stack

```bash
# Terminal 1: Database + Redis
docker compose up db redis

# Terminal 2: Backend with hot reload
cd backend && source .venv/bin/activate
uvicorn trainingdash.app:app --reload

# Terminal 3: Frontend with hot reload
cd frontend && npm run dev
```

## Code Style

### Python (Backend)

- Follow PEP 8
- Use type hints for function signatures
- Docstrings for public functions
- Max line length: 88 characters (Black default)

```python
async def compute_tss(
    normalized_power: float,
    ftp: float,
    duration_seconds: int,
) -> float:
    """
    Compute Training Stress Score.

    Args:
        normalized_power: Normalized power in watts
        ftp: Functional Threshold Power in watts
        duration_seconds: Activity duration

    Returns:
        TSS value (typically 0-300 for most rides)
    """
    intensity_factor = normalized_power / ftp
    return (duration_seconds * normalized_power * intensity_factor) / (ftp * 3600) * 100
```

### TypeScript (Frontend)

- Use TypeScript strict mode
- Prefer functional components with hooks
- Use explicit return types for functions

```typescript
interface ActivityCardProps {
  activity: Activity;
  onClick?: () => void;
}

function ActivityCard({ activity, onClick }: ActivityCardProps): JSX.Element {
  return (
    <div onClick={onClick} className="p-4 rounded-lg bg-surface">
      <h3>{activity.title}</h3>
    </div>
  );
}
```

## Project Structure

```
traindash/
├── backend/
│   ├── src/trainingdash/    # Python package
│   │   ├── routers/         # API endpoints
│   │   ├── models.py        # SQLAlchemy models
│   │   └── ...
│   ├── tests/               # pytest tests
│   └── migrations/          # Alembic migrations
├── frontend/
│   ├── src/
│   │   ├── pages/           # Route components
│   │   ├── components/      # Reusable components
│   │   └── api.ts           # API client
│   └── ...
└── docs/
```

## Making Changes

### Adding a New API Endpoint

1. Add the route in `backend/src/trainingdash/routers/`
2. Add Pydantic models for request/response in `serializers.py`
3. Add tests in `backend/tests/`
4. Update `docs/api.md`

### Adding a New Frontend Page

1. Create the component in `frontend/src/pages/`
2. Add the route in `App.tsx`
3. Add API types in `api.ts` if needed
4. Add tests alongside the component (e.g., `MyPage.test.tsx`)

### Database Migrations

When changing models:

```bash
cd backend
source .venv/bin/activate
alembic revision --autogenerate -m "description of change"
alembic upgrade head
```

Review the generated migration before committing!

## Testing

### Backend Tests

Tests use [testcontainers](https://testcontainers.com/) to spin up real PostgreSQL and Redis instances:

```bash
cd backend
pytest                          # Run all tests
pytest tests/test_activities.py # Run specific file
pytest -v --tb=short            # Verbose with short tracebacks
```

### Frontend Tests

Tests use [Vitest](https://vitest.dev/) and [Testing Library](https://testing-library.com/):

```bash
cd frontend
npm test              # Run tests in watch mode
npm test -- --run     # Run once
npm test -- MyComponent.test.tsx  # Run specific file
```

## Pull Request Process

1. **Create a focused PR** — One feature or fix per PR
2. **Write a clear description** — What does it do? Why?
3. **Include tests** — New features need tests, bug fixes should add regression tests
4. **Update docs** — If you changed the API or added features
5. **Keep commits clean** — Squash WIP commits, write meaningful commit messages

### Commit Message Format

```
type(scope): brief description

Longer explanation if needed. Wrap at 72 characters.

Fixes #123
```

Types: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`

Examples:
- `feat(api): add pagination to activities endpoint`
- `fix(pmc): correct CTL calculation for rest days`
- `docs: update API reference for new endpoints`

## Architecture Decisions

Major decisions are documented as ADRs in `docs/adr/`. If your change involves a significant architectural choice, consider adding an ADR:

```markdown
# ADR-NNNN: Title

## Status
Proposed | Accepted | Deprecated

## Context
What is the issue or question?

## Decision
What did we decide?

## Consequences
What are the tradeoffs?
```

## Getting Help

- Check existing issues and PRs
- Read the [Architecture docs](docs/architecture.md)
- Open a discussion for questions

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
