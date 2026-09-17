# Segment Max Grade Fix + Elevation Profile Design

Date: 2026-09-17
Status: Approved

## Problem

Two issues on the segment detail page:

1. **Bogus Max Grade.** `compute_elevation_stats` in `backend/src/trainingdash/domain/segment_geometry.py` computes `max_grade_pct` over raw consecutive record pairs. With ~20m record spacing, barometric/GPS noise produces spikes (verified: raw pair grades up to 187% in a source activity; a 16.1km commuter segment displays "60.1% Max Grade" while its smoothed 50m gradient bars peak at ~14%). The activity view already computes max grade sensibly (sliding ~200m windows in `ingest.py`), but the logic is duplicated and divergent.

2. **Gradient bars are less useful than an altitude curve.** The segment pages render a bar-chart "Gradient Profile" (one bar per 50m window). A Strava-style elevation curve conveys the same information plus actual altitude, and the user prefers it.

## Goals

1. One shared max-grade algorithm for activities and segments: max grade over sliding 200m windows, extracted to a reusable module.
2. Replace `gradient_segments` (50m grade bars) with an `elevation_profile` (distance/altitude/grade points) rendered as an area chart, everywhere the old chart appears.

## Non-Goals

- Changing climb detection, course segmentation (race planner), or activity-level metric semantics.
- Storing raw altitude arrays at full record resolution; profile is sampled at ~50m.

## Design

### 1. Shared max-grade module

New `backend/src/trainingdash/domain/grade_stats.py`:

```python
def compute_max_grade_pct(
    records: list[tuple[float, float]],  # (distance_m, altitude_m), distance-ascending
    window_m: float = 200.0,
) -> float | None:
    """Max grade over sliding windows of ~window_m. None if insufficient data."""
```

- Extracted from the current `ingest.py` `_compute_extended_metrics` logic (sliding windows over cumulative distance, grade from window endpoints, max over windows; requires >10 points).
- `ingest.py` calls it — activity behavior unchanged (same numbers as today).
- `compute_elevation_stats` in `segment_geometry.py` calls it for `max_grade_pct` instead of the raw-pair loop — segment Max Grade now matches activity Max Grade exactly.

### 2. Elevation profile replaces gradient_segments

**Domain (`segment_geometry.py`):**

- `GradientSegment` → `ElevationPoint` dataclass: `{distance_m: float, elevation_m: float, grade_pct: float}`.
- `SegmentGeometry.gradient_segments` → `elevation_profile: list[ElevationPoint]`.
- `compute_gradient_segments` → `compute_elevation_profile(records, sample_interval_m=50.0)`: same 50m walk, but each sample records the altitude at that point plus the grade of the preceding window. Points are cumulative-distance-anchored so the chart X axis is true distance. A final point at the exact end distance is emitted if the last window is partial (>10m remainder).
- `compute_segment_geometry` returns the new field; `max_grade_pct` via the shared module.

**Storage:**

- Migration 033: add `segments.elevation_profile` JSONB NOT NULL (comment `# [{distance_m, elevation_m, grade_pct}, ...]`), drop `segments.gradient_segments`. Follow repo migration conventions (numeric revision `"033"`, down_revision `"032"`).
- `models.py` `Segment`: replace the `gradient_segments` column with `elevation_profile` (untyped JSONB, same pattern).
- Both writers updated:
  - `create_segment.py`: builds `Segment(...)` from geometry's `elevation_profile`.
  - `process_activity_segments.py`: the detected-climb path currently takes stats from `DetectedClimb`; its `max_grade_pct` comes from smoothed climb metrics. Change: the persisted `Segment` row uses the shared `compute_max_grade_pct` on the climb's records and builds the profile from `compute_elevation_profile` — one algorithm everywhere. (`DetectedClimb`'s internal fields stay as-is for detection/category logic.)
- Serializers:
  - `routers/segments.py` `segment_detail`: `gradient_segments` key → `elevation_profile`.
  - `routers/suggestions.py` `suggestion_response` + `segment_response`: same replacement (both read `gradient_segments` from the segment row — only the `segments` table stores it).

**Backfill:**

- New `backend/scripts/backfill_segment_profiles.py`, patterned on `backfill_extended_metrics.py`: argparse with `--dry-run`, `--batch-size` (default 100), `--segment-id` (optional single-segment recompute). For each non-deleted segment with a `source_activity_id`: load source activity records, recompute `compute_segment_geometry`, update `elevation_profile`, `max_grade_pct`, `avg_grade_pct`, `elevation_gain_m`, `distance_m`. Commit per batch; log progress; return `(total, updated, skipped)`.

### 3. Frontend

**API types:**

- `api/segments.ts` + `api/suggestions.ts`: `GradientSegment` interface → `ElevationPoint { distance_m: number; elevation_m: number; grade_pct: number }`; `SegmentDetailData.gradient_segments` → `elevation_profile: ElevationPoint[]`; same for suggestion types.

**Component:**

- New `frontend/src/components/segments/ElevationProfile.tsx`, modeled on RacePlanner's `ElevationChart` (`frontend/src/pages/RacePlanner/CourseDetail.tsx` L116–196):
  - recharts `AreaChart`, X = distance (formatted via injected `formatDistanceLabel`), Y = elevation_m.
  - Area fill color varies by `grade_pct` buckets (reuse `gradientColor()` thresholds from `SegmentBadges.tsx`).
  - Tooltip: distance, elevation, grade.
  - Props: `{ profile: ElevationPoint[], height?: number, formatDistanceLabel?: (m: number) => string }`. Resamples to ≤200 points for large segments.
- Delete `GradientProfile` from `SegmentBadges.tsx` (keep `ClimbCategoryBadge`, `SegmentTypeIcon`).
- Replace in all four consumers:
  - `SegmentDetailPage.tsx`: heading "Gradient Profile" → "Elevation Profile"; `ElevationProfile` with `segment.elevation_profile`, height ~200 (taller chart for the detail page).
  - `SuggestionsPage.tsx`: `ElevationProfile` height ~48 (inline card).
  - `ActivitySegments.tsx`: `ElevationProfile` height ~48.
  - `SegmentCreationModal.tsx`: live preview `ElevationProfile` height ~40.

**Client preview:**

- `lib/segmentPreview.ts`: mirror the backend — 50m `computeElevationProfile` (altitude + grade per point) and 200m-window `max_grade_pct`. `PreviewStats` swaps `gradient_segments` for `elevation_profile`.

### 4. Error handling

- `compute_elevation_profile` with <2 records → empty list (as today).
- Segments with missing `source_activity_id` (none expected; all writers set it) → backfill skips with a warning.
- Backfill finds no records for an activity → skip, log, leave segment unchanged.
- API consumers receiving an old cached payload (no `elevation_profile`) → component renders empty-state message "No elevation data" rather than crashing.

### 5. Testing

**Backend:**

- New `tests/unit/domain/test_grade_stats.py`: windowed max grade (steady climb, variable, noisy data spike suppression, insufficient data → None).
- Update `test_segment_geometry.py`: elevation stats tests (max grade now windowed — e.g. noise spike of +2m over 2m within a 200m window no longer dominates), profile shape tests (spacing ~50m, cumulative distance, final partial window), `SegmentGeometry` dataclass field list.
- Update `test_create_segment.py`, `test_process_activity_segments.py`, `test_suggestions.py` serializer tests, `test_activity_segments.py`, integration `test_segment_models.py` fixtures (`gradient_segments=[...]` → `elevation_profile=[...]`).
- `ingest.py` behavior unchanged — existing extended-metrics tests act as the regression guard for the extraction.

**Frontend:**

- Update `SegmentDetailPage.test.tsx`: elevation chart renders from `elevation_profile` (assert area/axis rather than bar tooltips).
- Update `SuggestionsPage.test.tsx`, `ActivitySegments.test.tsx`, `SegmentCreationModal.test.tsx` mocks and assertions.
- Update `segmentPreview.test.ts` for the new preview math.
- New `ElevationProfile.test.tsx`: renders points, tooltip content, empty-state.

## Migration & Rollout

1. Ship code with new column (033 adds `elevation_profile`, drops `gradient_segments`) — old payloads stop including `gradient_segments`; frontend deploy is atomic with backend (single docker deployment, same repo).
2. Run `backfill_segment_profiles.py` post-deploy to populate profiles and fix `max_grade_pct` for existing segments.

## Verification

- Backend: `cd backend && pytest` (unit + integration).
- Frontend: `cd frontend && npm test` + `npm run typecheck` + `npm run lint`.
- Manual: load `/segments/d151c46a-...`, confirm Max Grade ≈ 14% (200m-window value) and elevation chart renders; run backfill script first.