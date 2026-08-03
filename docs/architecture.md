# Architecture

This document describes TrainDash's system design and code organization for developers.

## System Overview

```mermaid
flowchart TB
    subgraph Browser["Browser"]
        SPA["React SPA<br/>(TypeScript, Tailwind, Recharts, Leaflet)"]
    end

    subgraph Backend["FastAPI Backend"]
        subgraph Routers["API Routers"]
            Auth["Auth"]
            Activities["Activities"]
            Analytics["Analytics"]
            Admin["Admin"]
        end
        subgraph Services["Domain Services"]
            Ingest["ingest.py"]
            Fitness["fitness.py"]
            PMC["pmc.py"]
            Peaks["peaks.py"]
            Metrics["metrics.py"]
        end
        subgraph Data["Data Layer"]
            Models["SQLAlchemy Models"]
        end
    end

    subgraph Infrastructure
        DB[("PostgreSQL<br/>+ PostGIS")]
        Redis[("Redis<br/>(Queue)")]
        Worker["Worker<br/>(arq)"]
    end

    subgraph External["External Services"]
        Garmin["Garmin Connect"]
        Xert["Xert API"]
        FIT["FIT Parser"]
    end

    SPA --> Routers
    Routers --> Services
    Services --> Models
    Models --> DB
    Worker --> Redis
    Worker --> Garmin
    Worker --> Xert
    Worker --> FIT
    Backend --> DB
    Backend --> Redis
```

## Backend Structure

```
backend/src/trainingdash/
├── app.py              # FastAPI application setup, middleware, static files
├── config.py           # Environment configuration (Settings class)
├── db.py               # Database session management
├── models.py           # SQLAlchemy ORM models
├── auth.py             # Authentication (JWT sessions, password hashing)
├── crypto.py           # Credential encryption (Fernet)
│
├── routers/            # API endpoints organized by domain
│   ├── auth.py         # /api/auth/* (login, logout, me)
│   ├── activities.py   # /api/activities/* (CRUD, upload, detail)
│   ├── analytics.py    # /api/analytics/* (PMC, power curve, records)
│   ├── admin.py        # /api/admin/* (user management, nuke, sync)
│   ├── user.py         # /api/user/* (preferences, integrations)
│   └── serializers.py  # Pydantic response models
│
├── ingest.py           # FIT file parsing and activity creation
├── fitness.py          # TSS, IF, NP calculations
├── pmc.py              # Performance Management Chart (CTL/ATL/TSB)
├── peaks.py            # Peak power detection
├── metrics.py          # Activity metrics computation
├── hr_power.py         # HR zones, power zones
├── wbal.py             # W'bal (anaerobic capacity) tracking
├── thresholds.py       # FTP/LTHR management
├── route_matching.py   # GPS route similarity (Hausdorff distance)
├── polyline.py         # Google polyline encoding for map thumbnails
├── resampler.py        # Time-series resampling for charts
├── geocoding.py        # Reverse geocoding for activity locations
├── title_generator.py  # Auto-generate activity titles
│
├── garmin.py           # Garmin Connect client
├── xert.py             # Xert API client
├── sync.py             # Sync orchestration
├── sync_providers.py   # Provider abstraction
│
├── worker.py           # arq worker settings and job definitions
├── jobs.py             # Background job implementations
└── init_db.py          # Database initialization script
```

## Frontend Structure

```
frontend/src/
├── main.tsx            # React entry point
├── App.tsx             # Router setup, auth context
├── api.ts              # API client (fetch wrappers, types)
├── format.ts           # Formatting utilities (distance, duration, pace)
├── resampler.ts        # Client-side data resampling
├── prs.ts              # Personal records calculation
│
├── pages/              # Route-level components
│   ├── Dashboard.tsx       # Home page with PMC, recent activities, PRs
│   ├── ActivityTable.tsx   # Sortable table view of activities
│   ├── AnalyzePage.tsx     # Deep activity analysis
│   ├── ComparePage.tsx     # Compare two activities
│   ├── PMCView.tsx         # Full PMC chart page
│   └── PowerCurveView.tsx  # Power curve analysis
│
├── components/         # Reusable UI components
│   ├── PolylineMap.tsx     # SVG polyline renderer (no tile server)
│   ├── MiniMap.tsx         # Leaflet map for activity detail
│   ├── Pagination.tsx      # Page navigation
│   └── ...
│
├── ActivityDetail.tsx  # Single activity view
├── ActivityList.tsx    # Activity list with thumbnails
├── RecordsView.tsx     # Lifetime and route PRs
├── Settings.tsx        # User preferences and integrations
├── AdminView.tsx       # Admin panel
├── Header.tsx          # Top navigation bar
├── Sidebar.tsx         # Left navigation
└── hooks/              # Custom React hooks
```

## Data Flow

### Activity Upload

1. User uploads FIT file via `/api/activities/upload`
2. `ingest.py` parses FIT file using `fitdecode`
3. Creates `Activity` and `Record` rows in database
4. Computes metrics (TSS, NP, IF) via `fitness.py`
5. Detects peaks via `peaks.py`
6. Matches to existing routes via `route_matching.py`
7. Generates polyline for map thumbnail via `polyline.py`
8. Returns activity ID to frontend

### Background Sync

1. Scheduled job runs at 2 AM (Xert) or 3 AM (Garmin)
2. Worker picks up job from Redis queue
3. Fetches new activities from provider API
4. For each activity, runs the same ingest pipeline as upload
5. Updates `last_synced_at` on user's credentials

### PMC Calculation

1. Frontend requests `/api/analytics/pmc?start=...&end=...`
2. `pmc.py` queries activities in date range
3. Calculates daily TSS, then rolling CTL (42-day) and ATL (7-day)
4. TSB = CTL - ATL
5. Returns time series for charting

## Database Schema

Key tables:

- **users** — Account info, preferences, admin flag
- **activities** — Summary data (distance, duration, TSS, etc.)
- **records** — Per-second data points (lat, lon, HR, power, speed)
- **peaks** — Best efforts at standard durations (5s, 1m, 5m, 20m, etc.)
- **routes** — Clustered GPS paths for route matching
- **garmin_credentials** / **xert_credentials** — Encrypted provider auth
- **audit_log** — Admin action history

PostGIS is used for:
- Storing GPS tracks as `LINESTRING` geometry
- Route matching via `ST_HausdorffDistance`
- Bounding box queries for map views

## Key Design Decisions

See [docs/adr/](adr/) for Architecture Decision Records:

- **ADR-0001**: Hard delete for nuke actions (no soft delete or trash)

### Why PostGIS?

Route matching needs spatial operations. Hausdorff distance between simplified polylines determines if two activities follow the same route. PostGIS handles this efficiently.

### Why arq + Redis?

Background sync jobs can take minutes (fetching from Garmin, parsing large FIT files). arq provides reliable job processing with retries, and Redis is already lightweight.

### Why Polyline Thumbnails?

Activity list shows 20+ activities per page. Loading Leaflet maps for each would be slow. Instead, we store a simplified Google-encoded polyline and render it as pure SVG — no tile server needed.

## Testing

```bash
# Backend (uses testcontainers for PostgreSQL)
cd backend
pytest

# Frontend (Vitest + Testing Library)
cd frontend
npm test
```

Integration tests use testcontainers to spin up real PostgreSQL and Redis instances.
