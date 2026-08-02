# Dashboard-centric Training Analytics

## Problem Statement

TrainingDash currently shows basic activity data (distance, time, speed, HR, power) but lacks the training analytics that help a self-coached cyclist make informed decisions about their training. Users cannot answer fundamental questions like "Am I getting fitter or burning out?", "How hard was that ride relative to my fitness?", or "What's my power profile?". Without metrics like TSS, NP, IF, CTL/ATL/TSB, and power duration curves, users must rely on external tools like TrainingPeaks or Golden Cheetah for serious training analysis.

## Solution

Build a dashboard-centric analytics experience that gives users immediate insight into their training load and fitness. The dashboard becomes the landing page, showing current form (fresh/fatigued), recent activity headlines, and trend sparks. Users can drill down into:

- **Activity detail** with computed training metrics (TSS, NP, IF), zone distribution, W'bal depletion, and peak power comparisons
- **PMC chart** showing fitness (CTL), fatigue (ATL), and form (TSB) over time with color-coded zones
- **Power Duration Curve** showing best power at each duration with comparisons across time periods

The system computes all metrics from raw power/HR data using the user's threshold history, with optional HR-derived power estimation for rides without a power meter.

## User Stories

1. As a cyclist, I want to see my current training form (fresh/fatigued) on the dashboard, so that I can decide if today should be a hard or easy day
2. As a cyclist, I want to see TSS, NP, and IF for each activity, so that I can understand how hard the ride was relative to my fitness
3. As a cyclist, I want to see time spent in each power zone, so that I can verify I'm training the right energy systems
4. As a cyclist, I want to see time spent in each heart rate zone, so that I can monitor my aerobic development
5. As a cyclist, I want to see W'bal depletion during a ride, so that I can understand when I was digging deep into my anaerobic reserves
6. As a cyclist, I want to see my peak powers for this ride compared to my all-time PRs, so that I know if I achieved something notable
7. As a cyclist, I want rides that set new PRs to be flagged as "breakthroughs", so that I can celebrate improvements
8. As a cyclist, I want to see a PMC chart showing CTL/ATL/TSB over time, so that I can track my fitness progression and manage fatigue
9. As a cyclist, I want the PMC to show color-coded zones (fresh/optimal/fatigued), so that I can quickly assess my current state
10. As a cyclist, I want to see FTP change markers on the PMC, so that I can understand why metrics shifted
11. As a cyclist, I want to hover on the PMC and see the activity for that day, so that I can connect the chart to real rides
12. As a cyclist, I want to see my Power Duration Curve, so that I can understand my power profile across all durations
13. As a cyclist, I want to compare power curves across time periods, so that I can see if I'm getting faster
14. As a cyclist, I want to toggle between watts and W/kg on the power curve, so that I can compare myself to benchmarks
15. As a cyclist, I want to see a table of my peak powers with dates achieved, so that I know the exact numbers and when I set them
16. As a cyclist, I want stale PRs (>90 days old) flagged, so that I know which records need refreshing
17. As a cyclist, I want to set my FTP manually, so that metrics are calculated correctly
18. As a cyclist, I want TrainingDash to auto-detect my FTP from ride data, so that I don't have to do formal tests
19. As a cyclist, I want to be notified when my FTP may have increased, so that I can accept or dismiss the suggestion
20. As a cyclist, I want my FTP history tracked with effective dates, so that past activities use the correct threshold
21. As a cyclist, I want to set my LTHR manually or have it estimated from my age, so that HR zones are correct
22. As a cyclist, I want to customize my power zones, so that I can use my coach's zone model if different from Coggan
23. As a cyclist, I want to customize my HR zones, so that I can match my preferred training methodology
24. As a cyclist, I want to enter my weight, so that W/kg calculations are accurate
25. As a cyclist, I want to enter my date of birth, so that HR defaults can be estimated
26. As a cyclist, I want to enable HR-derived power estimation for rides without a power meter, so that those rides contribute to my training load
27. As a cyclist, I want HR-derived power marked as estimated with a confidence score, so that I know which data to trust
28. As a cyclist, I want the dashboard to show my weekly training volume, so that I can track consistency
29. As a cyclist, I want the dashboard to show my fitness trend (FTP over time), so that I can see long-term progress
30. As a cyclist, I want the dashboard to show a power curve thumbnail, so that I can quickly see my power profile
31. As a cyclist, I want the dashboard to show notifications (FTP suggestions, breakthroughs), so that I don't miss important updates
32. As a cyclist, I want a sidebar navigation to switch between Dashboard, Activities, PMC, and Power Curve views
33. As a cyclist, I want URLs for each view, so that I can bookmark and share specific pages
34. As a cyclist, I want the sidebar to collapse to icons on desktop, so that I can maximize chart space
35. As a cyclist, I want a hamburger menu on mobile, so that navigation works on small screens
36. As a cyclist, I want initial sync to not spam me with notifications, so that bulk imports are handled gracefully

## Implementation Decisions

### Schema Changes

**User table (add columns):**
- `date_of_birth: date` — required for HR estimation
- `weight_kg: float` — optional, enables W/kg calculations
- `hr_derived_power_enabled: bool` — opt-in for HR→power estimation

**New table: ThresholdHistory**
- `id`, `user_id` (FK), `sport` (cycling/running/swimming), `threshold_type` (ftp/lthr/hrmax), `value`, `effective_from`, `source` (estimated/manual/auto-detected/test), `created_at`

**New table: PowerZone**
- `id`, `user_id` (FK), `sport`, `zone_number` (1-7), `min_watts`, `max_watts`, `min_pct`, `max_pct`, `name`, `color`, `created_at`

**New table: HrZone**
- `id`, `user_id` (FK), `sport`, `zone_number` (1-5), `min_bpm`, `max_bpm`, `min_pct`, `max_pct`, `name`, `color`, `created_at`

**Activity table (add columns):**
- `normalized_power_w: int`
- `intensity_factor: float`
- `tss: float`
- `time_in_power_zone_s: JSON` — array [z1, z2, z3, z4, z5, z6, z7]
- `time_in_hr_zone_s: JSON` — array [z1, z2, z3, z4, z5]
- `wbal_min_j: int`
- `metrics_ftp_w: int` — FTP used for computation (audit)
- `metrics_computed_at: datetime`
- `power_source: str` — "device" or "estimated_hr"
- `power_confidence: float` — 0.0 to 1.0
- `is_breakthrough: bool`

**Record table (add column):**
- `wbal_j: int` — W'bal at this timestamp

**New table: ActivityPeakPower**
- `id`, `activity_id` (FK), `duration_s` (1, 2, 5, 10, 30, 60, 120, 300, 600, 1200, 1800, 3600, 7200, 18000), `power_w`
- Unique constraint on (activity_id, duration_s)

**New table: FitnessHistory**
- `id`, `user_id` (FK), `computed_at`, `pp_w` (peak power), `wprime_j` (W'), `cp_w` (critical power), `data_window_days`

**New table: HrPowerModel**
- `id`, `user_id` (FK, unique), `ef_value` (efficiency factor), `rides_used`, `newest_ride_at`, `computed_at`

**New table: UserNotification**
- `id`, `user_id` (FK), `type` (ftp_suggestion, etc.), `payload: JSON`, `created_at`, `dismissed_at`, `accepted_at`

### Computation Pipeline

Metrics are computed **on ingest only** — the FTP history handles time-correctness, so no recomputation is needed when FTP changes.

**On activity ingest:**
1. Parse FIT → save Activity + Records (existing)
2. Lookup user's FTP/LTHR at activity date from ThresholdHistory
3. If no power data and HR-derived power enabled: estimate power using HrPowerModel
4. Compute NP, IF, TSS, zone times from Records + thresholds
5. Compute W'bal series, store in Records, save min to Activity
6. Compute peak powers at 14 durations, save to ActivityPeakPower
7. Check if any peaks are new PRs → recalculate fitness model → snapshot to FitnessHistory
8. If fitness model CP differs from current FTP by >5%, queue notification
9. If new PR at key duration, set `is_breakthrough = True`

**Bulk import mode:**
- Initial sync (>10 activities) runs in bulk mode
- Compute metrics for each activity, but defer fitness model recalc and notifications
- After all activities imported: single fitness model calculation, single FTP notification if warranted
- No breakthrough badges for historical activities

### Threshold Defaults

**For new users:**
- HRmax: `208 - (0.7 × age)` (Tanaka formula, requires date_of_birth)
- LTHR: `HRmax × 0.85`
- FTP: `weight_kg × 2.5` if weight provided, else 200W
- All marked with `source: estimated`

**Zone models:**
- Power zones: Coggan 7-zone model (default)
- HR zones: Friel 5-zone model (default)
- Zones stored explicitly for all users (no on-the-fly calculation)
- Regenerated when user changes threshold

### HR-Derived Power

**Model:** EF-based (power = HR × EF)
- Requires 5+ dual-sensor rides to enable
- EF calculated from rolling 90-day window with decay weighting
- Flag as "low confidence" when best data >60 days stale
- Accept HR lag limitation — works for steady-state, not intervals

### FTP Auto-Detection

**Algorithm:** Derive FTP from Critical Power (CP) in fitness model
- Calculate after each ride
- Notify only when change >5%
- User accepts → new ThresholdHistory entry with `source: auto-detected`
- User dismisses → hide until next significant change

### API Endpoints

**Thresholds & Zones:**
- `GET /me/thresholds` — list threshold history
- `POST /me/thresholds` — add new threshold
- `GET /me/zones` — get current power and HR zones
- `PUT /me/zones` — update zone customizations

**Analytics:**
- `GET /pmc?start=&end=` — CTL/ATL/TSB time series
- `GET /power-curve?start=&end=` — peak powers for date range
- `GET /fitness` — current fitness model (PP, W', CP)
- `GET /dashboard` — aggregated dashboard data (form, recent activities, weekly volume, notifications)

**Notifications:**
- `GET /me/notifications` — list pending notifications
- `POST /me/notifications/{id}/accept` — accept (e.g., FTP suggestion)
- `POST /me/notifications/{id}/dismiss` — dismiss

**Activity (extended):**
- `GET /activities/{id}` — now includes TSS, NP, IF, zones, peaks, is_breakthrough
- `GET /activities/{id}/records` — now includes wbal_j

### Frontend Architecture

**Navigation:**
- Sidebar with icons + text (collapsible on desktop, hamburger on mobile)
- URL-based routing with react-router
- Routes: `/` (Dashboard), `/activities`, `/activities/:id`, `/pmc`, `/power-curve`, `/records`, `/settings`, `/admin`

**Dashboard layout:**
- Hero: PMC sparkline with TSB form number and color
- Left column: Featured activity card + recent activities list (5 items)
- Right column: Weekly volume, Fitness trend, Power curve thumbnail
- Bottom: Notifications banner

**Activity detail layout:**
- Row 1: Ride basics (Date, Distance, Time, Elevation, Speed)
- Row 2: Training metrics (TSS, NP, IF, Avg Power, Avg HR)
- Peaks row with PR% comparison and breakthrough badges
- Map
- Zone charts (horizontal bars, power left, HR right)
- Time-series charts: Power, W'bal, HR, Speed, Elevation
- Route comparison selector (existing)

**PMC chart:**
- Lines: CTL (blue), ATL (pink), TSB (yellow)
- Background zones: Fresh (>25), Optimal (5-25), Neutral (-10 to 5), Fatigued (-30 to -10), Very fatigued (<-30)
- Controls: Preset buttons (6W, 12W, 6M, 1Y, All) + date picker
- Annotations: FTP change markers, activity details on hover
- Form badge above chart + endpoint callout

**Power Duration Curve:**
- Log X-axis
- 7 key durations marked: 5s, 30s, 1min, 5min, 20min, 60min, 120min (LTP)
- Controls: Date range presets, comparison toggle, W/kg toggle, fitness model toggle
- Table below with duration, power, W/kg, date achieved + staleness indicator

## Testing Decisions

### What Makes a Good Test

Tests should verify external behavior, not implementation details:
- **Do** test that uploading a FIT file results in correct TSS on the activity
- **Don't** test that a specific internal function was called
- **Do** test that the PMC endpoint returns correct CTL/ATL/TSB values
- **Don't** test the internal structure of intermediate calculations

### Unit Tests (Pure Functions)

New modules with pure computation logic, tested without database:

| Module | Tests |
|--------|-------|
| `metrics.py` | NP calculation from power array; IF from NP/FTP; TSS from duration/NP/IF/FTP; zone time from power array + zone boundaries |
| `wbal.py` | W'bal series from power array + CP/W'; handles intervals and recovery |
| `peaks.py` | Extract max power for various durations; handles edge cases (short rides) |
| `fitness_model.py` | Fit CP/W'/PP from peak power data; handles insufficient data |
| `hr_power_model.py` | EF calculation from dual-sensor data; HR→power estimation; decay weighting |
| `pmc.py` | CTL/ATL/TSB from daily TSS series; exponential moving averages |
| `zones.py` | Zone boundaries from FTP + Coggan model; from LTHR + Friel model |

Prior art: `tests/unit/test_fit_parser.py`

### Integration Tests (HTTP API)

Test full request/response cycle through the HTTP client:

| Area | Tests |
|------|-------|
| Activity metrics | Upload FIT → activity has NP, IF, TSS, zones; metrics use correct FTP from history |
| Peak powers | Upload FIT → ActivityPeakPower rows created; power curve endpoint returns them |
| Thresholds | CRUD operations on thresholds; zone regeneration on threshold change |
| PMC | Returns correct CTL/ATL/TSB for date range; handles empty data |
| Notifications | FTP suggestion created on breakthrough; accept/dismiss flow |
| Dashboard | Returns aggregated data; handles new user with no data |

Prior art: `tests/integration/test_activities.py`

### Ingest Pipeline

End-to-end tests that verify the complete flow:
- Upload activity → metrics computed → peaks stored → fitness model updated → notification created (if applicable)
- Bulk import mode defers notifications
- HR-derived power used when enabled and no power data

## Out of Scope

- Workout planning / calendar scheduling
- Indoor trainer control (ERG mode, Zwift-style)
- Multi-athlete / coach dashboard
- Mobile app (native iOS/Android)
- AI coaching recommendations
- Social features (sharing, leaderboards)
- Non-cycling sports (running, swimming) — schema supports it, but UI/logic is cycling-only for now

## Further Notes

### Domain Glossary Updates

The following terms should be added to `CONTEXT.md`:

- **FTP (Functional Threshold Power)** — The highest power a cyclist can sustain for approximately one hour. Used as the basis for power zones and TSS calculations.
- **LTHR (Lactate Threshold Heart Rate)** — Heart rate at lactate threshold. Used as the basis for HR zones.
- **TSS (Training Stress Score)** — A measure of training load combining duration and intensity. TSS = (duration × NP × IF) / (FTP × 3600) × 100.
- **NP (Normalized Power)** — A weighted average power that accounts for variability. Better represents physiological cost than average power.
- **IF (Intensity Factor)** — Ratio of NP to FTP. IF = 1.0 means threshold effort.
- **CTL (Chronic Training Load)** — 42-day exponentially weighted average of daily TSS. Represents fitness.
- **ATL (Acute Training Load)** — 7-day exponentially weighted average of daily TSS. Represents fatigue.
- **TSB (Training Stress Balance)** — CTL minus ATL. Represents form: positive = fresh, negative = fatigued.
- **W' (W Prime)** — Anaerobic work capacity above critical power, measured in joules.
- **W'bal** — Real-time balance of W' during a ride. Depletes during efforts above CP, recovers below.
- **CP (Critical Power)** — Power that can theoretically be sustained indefinitely. Approximately equal to FTP.
- **Power Duration Curve** — Chart showing best power output at each duration from seconds to hours.
- **Breakthrough** — An activity where a new personal record was set at a meaningful duration.

### Research References

Detailed formulas and UI patterns are documented in:
- `.scratch/training-metrics-research/fit-file-metrics.md`
- `.scratch/training-metrics-research/metrics-formulas.md`
- `.scratch/training-metrics-research/golden-cheetah-ui.md`
- `.scratch/training-metrics-research/trainingpeaks-ui.md`
