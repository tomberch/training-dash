# Golden Cheetah UI/UX Research

## Overview

Golden Cheetah is an open-source performance analysis software for cyclists, runners, triathletes, and coaches. It provides comprehensive tools for downloading, importing, analyzing, and tracking workout data from power meters and other devices.

**Primary Sources:**
- GC3-Manual.texinfo (official user guide)
- GC3-FAQ.texinfo (official FAQ)
- Source code: src/Gui/Views.h, src/Charts/*, src/Gui/GcWindowRegistry.cpp

---

## 1. Main Views/Screens

Golden Cheetah uses a **four-view architecture** accessed via a **scope bar** at the top of the window:

### Analysis View
- **Purpose:** Per-activity analysis - review individual workouts in detail
- **Sidebar:** Activity list, interval sidebar, activity metadata
- **Focus:** Deep-dive into a single ride/activity
- **Available charts:** Performance plot, CP curve, histogram, map, scatter, Aerolab, HR vs Power, PfPv

### Trends View (formerly "Home View")
- **Purpose:** Long-term performance tracking across date ranges/seasons
- **Sidebar:** Date ranges, seasons, events, LTM (Long Term Metrics) sidebar
- **Focus:** Tracking progress over weeks/months/years, PMC charts
- **Available charts:** LTM (Long Term Metrics), TreeMap, Power Duration, Distribution, Calendar, Navigator

### Plan View
- **Purpose:** Training planning and plan adherence tracking
- **Sidebar:** Shares LTM sidebar with Trends view
- **Focus:** Future planning, target events, performance targets
- **Available charts:** Agenda, Plan Adherence, Calendar, LTM, TreeMap, Power Duration

### Train View
- **Purpose:** Real-time workout control on indoor trainers
- **Sidebar:** Devices, workouts, media library
- **Focus:** Live training sessions with ANT+ devices, video playback
- **Available charts:** Telemetry dials, workout plot, realtime plot, pedal stroke analysis, video player, live map

---

## 2. Chart Types

### Per-Activity Charts (Analysis View)

| Chart Name | Type | Purpose |
|------------|------|---------|
| **Performance (AllPlot)** | Multi-series time plot | Primary ride plot showing power, HR, cadence, speed, altitude over time |
| **Power Duration (CP Curve)** | Mean-max curve | Critical power analysis, shows best power for each duration |
| **Histogram** | Distribution | Power/HR/cadence distribution for single activity |
| **Map** | Geographic | GPS route visualization (OSM, Google, Bing options) |
| **Scatter** | XY scatter | 2D correlation plots (any metric pair) |
| **Aerolab** | Virtual elevation | Aerodynamic analysis using Chung method (CdA estimation) |
| **HR vs Power (HrPw)** | Scatter | Heart rate to power relationship, cardiac drift analysis |
| **PfPv (Pedal Force vs Velocity)** | Quadrant analysis | Pedal stroke analysis, force vs velocity quadrants |
| **Activity Overview** | Dashboard tiles | Summary cards with key metrics |
| **Data (Metadata)** | Form/table | Activity details, metadata editing |

### Long-Term Charts (Trends/Plan Views)

| Chart Name | Type | Purpose |
|------------|------|---------|
| **LTM (Long Term Metrics)** | Time series | Plot any metric over time (TSS, CTL, ATL, hours, etc.) |
| **PMC (Performance Manager)** | Specialized LTM | CTL/ATL/TSB fatigue model visualization |
| **TreeMap** | Treemap | Visualize time/metrics by category (workout type, location) |
| **Distribution** | Histogram | Aggregate distribution across date range |
| **Power Duration** | Mean-max curve | Aggregate CP curve across season/date range |
| **Calendar** | Calendar grid | Month/week calendar with color-coded activities |
| **Navigator** | Table/list | Sortable activity list with configurable columns |
| **Agenda** | List view | Planning-focused activity list |
| **Plan Adherence** | Chart | Tracking planned vs actual training |

### Realtime Charts (Train View)

| Chart Name | Type | Purpose |
|------------|------|---------|
| **Telemetry (Dials)** | Gauge/dial | Live power, HR, cadence, speed displays |
| **Workout** | Target plot | Workout profile with target zones |
| **Realtime** | Live plot | Scrolling live telemetry |
| **Pedal Stroke (SpinScan)** | Polar/radial | Computrainer pedal stroke analysis |
| **Video Player** | Media | Workout videos, Sufferfest, ERG videos |
| **Live Map** | Map | Real-time position on route |
| **Elevation Chart** | Profile | Elevation profile with current position |

---

## 3. Metrics Organization

### Per-Activity Metrics
Displayed in the Analysis view sidebar and Details/Metadata panel:

- **Primary metrics:** Duration, Distance, TSS, IF, NP/xPower, Average Power, Work (kJ)
- **Maximums:** Peak power at various durations (1s, 5s, 1min, 5min, 20min, 60min)
- **Zones:** Time in power zones, HR zones
- **Derived:** W/kg, VAM, Gradient, Pace
- **HR metrics:** Average HR, Max HR, TRIMP, LTHR ratio
- **Cadence:** Average cadence, max cadence

**Override capability:** Users can manually override calculated metrics (e.g., TSS) in the Details screen for manual entries or corrections.

### Aggregate/Long-Term Metrics
Displayed in Trends view over date ranges:

- **Stress metrics:** Daily TSS, Weekly TSS, CTL (Chronic Training Load), ATL (Acute Training Load), TSB (Training Stress Balance)
- **Volume metrics:** Total hours, total distance, total work, ride count
- **Averages:** Rolling averages of any metric
- **Bests:** Best power for custom durations over date range
- **Custom:** User-defined metrics and formulas

### Metric Database
- SQLite database (`metricDBv3`) storing all calculated metrics
- Can be exported to CSV
- Automatic refresh on data import
- Supports custom user-defined metrics

---

## 4. Navigation Patterns

### Primary Navigation Structure
```
┌──────────────────────────────────────────────────────────┐
│ Menu Bar                                                 │
├──────────────────────────────────────────────────────────┤
│ Tool Bar (common actions: download, import, save, etc.) │
├──────────────────────────────────────────────────────────┤
│ Scope Bar: [Analysis] [Trends] [Plan] [Train]    [+ Add]│
├─────────────┬────────────────────────────────────────────┤
│             │                                            │
│  Sidebar    │  Main View (Charts)                        │
│             │  - Tabbed or Tiled mode                    │
│  - Context  │  - Multiple charts per view                │
│    specific │  - Resizable, draggable                    │
│  - Lists    │                                            │
│  - Filters  │                                            │
│             │                                            │
├─────────────┴────────────────────────────────────────────┤
│ [Optional] Bottom Panel (Compare mode, intervals)        │
└──────────────────────────────────────────────────────────┘
```

### Sidebar Behavior
- **Context-sensitive:** Content changes based on active view
- **Collapsible:** Can be hidden by dragging or toggle
- **Analysis sidebar:** Activities list, intervals, metadata
- **LTM sidebar (Trends/Plan):** Date ranges, seasons, events, filters

### Chart Navigation
- **Tabbed mode:** Charts as tabs, one visible at a time
- **Tiled mode:** Multiple charts visible simultaneously, scrollable
- **"More..." menu:** Hover over chart to access settings, close, full screen
- **Add charts:** Via `+` menu in scope bar (shows relevant charts for current view)
- **Zoom:** Left-click drag to zoom, right-click to unzoom
- **Pan:** Slider controls on plots

### Drill-Down Patterns
1. **Trends → Activity:** Click on point in LTM chart to select that activity
2. **Activity list → Activity:** Click to load activity data
3. **Interval selection:** Click/drag on performance plot to define intervals
4. **Compare mode:** Toggle to compare activities or date ranges side-by-side

### Search and Filter
- **Free text search:** Search across all activity metadata
- **Data filter syntax:** Filter activities by metric values (e.g., `TSS > 300`, `IF > 0.9`)
- **Applied to charts:** Filters affect which activities are included in aggregate charts

---

## 5. Customization Options

### Layout Customization
- **Perspectives:** Save/restore different chart layouts per view
- **Chart arrangement:** Add, remove, resize, reorder charts
- **Sidebar width:** Adjustable via splitter
- **View mode:** Switch between tabbed and tiled

### Chart Customization (per chart)
- **Title:** Custom chart title
- **Data series:** Toggle which series to show (power, HR, cadence, etc.)
- **Colors:** Configure colors globally in preferences
- **Axes:** Configure scale, log scale, ranges
- **Smoothing:** Adjust smoothing algorithms
- **Stack/Separate:** Stack multiple series or use separate axes
- **Date range:** Select seasons, custom date ranges

### Appearance Settings
- **Themes:** Light/dark modes, custom color schemes
- **Fonts:** Configurable chart fonts
- **Colors:** Comprehensive color configuration for all data series and UI elements
- **Units:** Imperial/metric

### Athlete Configuration
- **Profile:** Weight, LTHR, CP/FTP values (used in metric calculations)
- **Power zones:** Custom zone boundaries
- **HR zones:** Custom zone boundaries
- **Sports:** Multi-sport support with per-sport settings

### Data Fields Configuration
- **Custom fields:** Add custom metadata fields
- **Field placement:** Configure which fields appear on which tabs
- **Keywords:** Color-coding rules based on field values

### Preferences Panes (accessed via Tools → Options or Preferences)
1. **General:** Units, date formats, defaults
2. **Athlete:** Profile, zones, settings
3. **Passwords:** Service credentials (Strava, TrainingPeaks, etc.)
4. **Appearance:** Colors, themes
5. **Data Fields:** Custom fields, notes keywords
6. **Metrics:** Configure which metrics to show in summaries
7. **Train Devices:** Device setup for realtime training

---

## Key UI/UX Patterns for Training Dashboard

### Applicable Patterns
1. **Multi-view architecture:** Separate views for different tasks (analysis vs trends vs training)
2. **Context-sensitive sidebar:** Sidebar content matches current view/task
3. **Tabbed + tiled charts:** Flexible chart layout options
4. **Date range selection:** Central to all trend analysis
5. **Metric override:** Manual entry and correction capability
6. **Search + filter:** Powerful filtering across activities
7. **Perspectives:** Saved layouts for different analysis workflows
8. **Compare mode:** Side-by-side activity/period comparison

### Chart Type Priorities
1. **Performance/ride plot:** Essential for per-activity analysis
2. **LTM/trend chart:** Essential for progress tracking
3. **PMC chart:** Core for training load management
4. **CP/power duration curve:** Key performance benchmark
5. **Distribution/histogram:** Understanding training composition
6. **Calendar:** Time-based activity overview

### Metric Organization
- Group metrics by category (stress, volume, performance)
- Allow per-activity and aggregate views
- Support manual override for edge cases
- Store in queryable database format
