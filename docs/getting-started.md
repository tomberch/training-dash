# Getting Started

This guide covers installation, configuration, and first steps with TrainDash.

## Installation

### Docker (Recommended)

The simplest way to run TrainDash is with Docker Compose:

```bash
git clone https://github.com/tomberch/training-dash.git
cd training-dash
docker compose up -d
```

This starts four containers:
- **app** — FastAPI backend + static frontend on port 8000
- **worker** — Background job processor (syncs, imports)
- **db** — PostgreSQL 16 with PostGIS
- **redis** — Job queue

Open http://localhost:8000 to access TrainDash.

### Manual Installation

For development or custom deployments:

**Prerequisites:**
- PostgreSQL 16+ with PostGIS extension
- Redis 7+
- Python 3.12+
- Node.js 20+

**Backend:**
```bash
cd backend
cp .env.example .env
# Edit .env with your database URL and secrets

uv sync
source .venv/bin/activate
alembic upgrade head  # run migrations
uvicorn trainingdash.app:app --host 0.0.0.0 --port 8000
```

**Frontend:**
```bash
cd frontend
npm install
npm run build
# Copy dist/ to backend/static/ or serve separately
```

**Worker:**
```bash
cd backend
source .venv/bin/activate
arq trainingdash.worker.WorkerSettings
```

## Configuration

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `DATABASE_URL` | Yes | PostgreSQL connection string with `asyncpg` driver |
| `SECRET_KEY` | Yes | Secret for session signing (generate a random string) |
| `TRAININGDASH_ENCRYPTION_KEY` | Yes | 32-byte base64 key for encrypting integration credentials |
| `REDIS_HOST` | No | Redis hostname (default: `localhost`) |
| `REDIS_PORT` | No | Redis port (default: `6379`) |
| `ADMIN_PASSWORD` | No | Initial admin password (default: `admin`) |

**Generate an encryption key:**
```bash
python -c "import secrets, base64; print(base64.b64encode(secrets.token_bytes(32)).decode())"
```

### Production Checklist

- [ ] Change `SECRET_KEY` to a random value
- [ ] Generate and set `TRAININGDASH_ENCRYPTION_KEY`
- [ ] Change the default admin password after first login
- [ ] Use a proper PostgreSQL password
- [ ] Consider running behind a reverse proxy (nginx, Caddy) with HTTPS

## First Steps

### 1. Log In

**Docker deployment** — A seed admin account is created automatically:
- **Email:** `admin@example.com`
- **Password:** `admin` (or value of `ADMIN_PASSWORD` env var)

**Manual deployment** — Register the first account at `/register`. The first user automatically becomes admin.

### 2. Upload Activities

Click **Upload FIT** in the header to upload Garmin FIT files directly.

### 3. Configure Integrations (Optional)

For automatic syncing, go to **Settings > Integrations**:

**Garmin Connect:**
1. Enter your Garmin Connect email and password
2. If you have MFA enabled, you'll be prompted for a code
3. Activities sync automatically at 3 AM daily

**Xert:**
1. Enter your Xert email and password
2. Activities sync automatically at 2 AM daily

### 4. Explore Your Data

- **Dashboard** — Overview with PMC chart, recent activities, and lifetime PRs
- **Activities** — Browse all activities with map thumbnails
- **PMC** — Track fitness, fatigue, and form over time
- **Power Curve** — See your best power outputs at each duration
- **Records** — View lifetime PRs and per-route PRs

### 5. Customize Preferences

Go to **Settings** to personalize your experience:

- **Theme** — Light, Dark, or Midnight (or follow system)
- **Unit System** — Metric (km, m) or Imperial (mi, ft)
- **Map Style** — OpenStreetMap, Positron, Dark Matter, or Voyager

### 6. Create Additional Users (Admin)

Go to **Admin > Users** to create accounts for other users. Each user has isolated data.

## Troubleshooting

### Database connection failed

Ensure PostgreSQL is running and the `DATABASE_URL` is correct:
```bash
docker compose logs db
```

### Migrations not applied

Run migrations manually:
```bash
docker compose exec app alembic upgrade head
```

### Garmin sync fails with MFA

Garmin MFA codes are time-sensitive. Enter the code within 30 seconds of receiving it.

### Activities missing after sync

Check the worker logs:
```bash
docker compose logs worker
```

Syncs run at 2 AM (Xert) and 3 AM (Garmin). To trigger a manual sync, go to **Admin** and click the sync button for the desired user.
