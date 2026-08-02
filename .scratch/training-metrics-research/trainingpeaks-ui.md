# TrainingPeaks UI Research

## Overview

TrainingPeaks is a leading endurance training platform used by athletes and coaches. This document captures how TrainingPeaks structures its analytics dashboard and metrics display based on official TrainingPeaks help documentation and resources.

---

## 1. Dashboard Layout and Key Widgets

### Main Dashboard Structure

The TrainingPeaks dashboard uses a **widget-based layout** that provides an at-a-glance view of training status.

**Source:** [TrainingPeaks Dashboard Help](https://help.trainingpeaks.com/hc/en-us/articles/204071804-Dashboard)

#### Key Dashboard Widgets:

1. **Performance Management Chart (PMC) Widget**
   - Compact view of fitness (CTL), fatigue (ATL), and form (TSB)
   - Shows current values with trend indicators
   - Clickable to expand to full PMC view

2. **Weekly Summary Widget**
   - Total hours, distance, and TSS for the current week
   - Comparison to planned values if a training plan exists
   - Progress bar visualization

3. **Upcoming Workouts Widget**
   - Next scheduled workouts from calendar
   - Quick access to workout details

4. **Recent Activities Widget**
   - Latest completed activities
   - Quick metrics: duration, distance, TSS
   - Compliance indicators (completed vs planned)

5. **Goals Widget**
   - Active goals with progress tracking
   - Target events countdown

6. **ATP (Annual Training Plan) Widget**
   - Current training phase
   - Weekly volume targets

### Dashboard Customization

- Widgets can be rearranged via drag-and-drop
- Some widgets can be resized
- Premium features allow additional widget options

---

## 2. Activity Detail View

### Metrics Display Structure

**Source:** [TrainingPeaks Workout Details](https://help.trainingpeaks.com/hc/en-us/articles/204071944-Viewing-Workout-Details)

#### Header Section
- Activity title/name
- Date and time
- Sport type icon
- Compliance status (if planned workout existed)

#### Summary Metrics Panel

Displayed in a **card/tile format** at the top:

| Metric | Description |
|--------|-------------|
| **Duration** | Total time, moving time |
| **Distance** | Total distance covered |
| **TSS** | Training Stress Score |
| **IF** | Intensity Factor |
| **NP/NGP** | Normalized Power (cycling) / Normalized Graded Pace (running) |
| **Avg/Max HR** | Heart rate statistics |
| **Avg/Max Power** | Power statistics (cycling) |
| **Avg/Max Pace** | Pace statistics (running) |
| **Elevation** | Total ascent/descent |
| **Calories** | Estimated energy expenditure |
| **Work** | Total kilojoules (cycling) |

#### Time-in-Zone Charts

**Heart Rate Zones:**
- Horizontal bar chart showing time spent in each zone (Z1-Z5)
- Percentage breakdown
- Color-coded (typically: gray, blue, green, yellow, orange, red)

**Power Zones (Cycling):**
- Similar horizontal bar visualization
- Based on FTP percentage zones
- 7-zone model common (Active Recovery through Neuromuscular)

**Pace Zones (Running):**
- Based on threshold pace settings

#### Graph/Chart Section

**Main Activity Graph Features:**
- Multi-axis time-series chart
- Stackable data streams:
  - Power (watts)
  - Heart Rate (bpm)
  - Speed/Pace
  - Cadence
  - Elevation profile
  - Temperature
- Smoothing controls (3s, 10s, 30s averaging)
- Zoom and pan capabilities
- Lap/interval markers overlaid

**Interactive Features:**
- Hover tooltips showing instant values
- Click-and-drag to select intervals
- Right-click context menu for interval analysis

#### Laps/Intervals Table

- Tabular breakdown of each lap or interval
- Columns: Duration, Distance, Avg Power, NP, Avg HR, Avg Cadence, TSS
- Sortable columns
- Click to highlight on graph

#### Map View (GPS Activities)

- Interactive map with route trace
- Color-coded by metric (power, HR, pace, elevation)
- Playback feature to animate activity

#### Peaks Analysis

**Source:** [TrainingPeaks Peak Performance](https://help.trainingpeaks.com/hc/en-us/articles/204072044-Peak-Performance-Charts)

- Best efforts for various durations (5s, 1min, 5min, 20min, etc.)
- Comparison to historical bests
- Power curve visualization

---

## 3. Performance Management Chart (PMC)

### PMC Overview

**Source:** [TrainingPeaks PMC Explained](https://help.trainingpeaks.com/hc/en-us/articles/204071764-Performance-Management-Chart)

The PMC is TrainingPeaks' signature feature for tracking long-term training load and readiness.

### Visual Structure

#### Chart Layout
- **X-axis:** Date (typically 6-12 months view)
- **Y-axis:** TSS/day equivalent scale
- **Three main lines:**
  1. **CTL (Chronic Training Load)** - "Fitness"
     - Color: Typically blue
     - 42-day exponentially weighted average of TSS
  2. **ATL (Acute Training Load)** - "Fatigue"
     - Color: Typically pink/magenta
     - 7-day exponentially weighted average of TSS
  3. **TSB (Training Stress Balance)** - "Form"
     - Color: Typically yellow
     - Calculated as CTL - ATL
     - Shown as filled area or separate line

#### Additional PMC Elements
- **Daily TSS bars:** Vertical bars showing daily training stress
- **Event markers:** Flagged events/races on timeline
- **Annotations:** Coach notes or athlete comments
- **Planned future TSS:** If training plan exists, projected values shown

### PMC Interaction Features

- Date range selector
- Zoom controls
- Hover tooltips with exact values for any date
- Click to view daily breakdown
- Toggle individual metrics on/off
- Sport-specific filtering (view only cycling TSS, etc.)

### PMC Metrics Configuration

**Default time constants:**
- CTL: 42-day time constant
- ATL: 7-day time constant

**Starting TSS:**
- Users can set initial CTL value for accuracy
- Default starting value is 0

### Visual Indicators

**TSB Interpretation (Color zones):**
| TSB Range | Status | Visual |
|-----------|--------|--------|
| > +25 | Transition/Detraining | Light blue/gray |
| +10 to +25 | Fresh/Race Ready | Green |
| -10 to +10 | Neutral | Yellow |
| -10 to -30 | Tired | Orange |
| < -30 | Very Tired/Overreaching | Red |

---

## 4. Calendar/Planning Views

### Calendar Structure

**Source:** [TrainingPeaks Calendar](https://help.trainingpeaks.com/hc/en-us/articles/204071674-Calendar)

#### View Modes
1. **Week View** - Default, most detailed
2. **Month View** - Overview of training distribution
3. **Day View** - Single day detail

#### Week View Layout

```
| Mon | Tue | Wed | Thu | Fri | Sat | Sun | Weekly Total |
|-----|-----|-----|-----|-----|-----|-----|--------------|
| [W] | [W] | [W] | [W] | [W] | [W] | [W] | TSS: XXX     |
|     |     |     |     |     |     |     | Hours: XX    |
```

**Daily Cell Contents:**
- Planned workout (top, outlined)
- Completed workout (filled)
- Compliance indicator (checkmark, X, or partial)
- Quick metrics (duration, TSS)
- Color-coded by workout type/sport

#### Workout Type Color Coding
- **Cycling:** Blue
- **Running:** Red/Orange
- **Swimming:** Teal/Cyan
- **Strength:** Purple
- **Other:** Gray

#### Calendar Interactions
- Drag and drop workouts to reschedule
- Click to open workout detail
- Right-click context menu (copy, move, delete)
- Multi-select for bulk operations

### Planning Features

**Annual Training Plan (ATP):**
- Phase-based periodization view
- Weekly volume targets (TSS, hours)
- Base, Build, Peak, Race, Recovery phases
- Visual timeline spanning months

**Workout Library:**
- Searchable workout templates
- Drag from library to calendar
- Filter by sport, duration, type, intensity

---

## 5. Metric Configuration (FTP, Zones, Thresholds)

### Settings Structure

**Source:** [TrainingPeaks Zones Settings](https://help.trainingpeaks.com/hc/en-us/articles/204071884-Setting-Your-Zones)

#### Threshold Settings (Per Sport)

**Cycling:**
- **FTP (Functional Threshold Power):** Watts
- **LTHR (Lactate Threshold Heart Rate):** BPM
- **Max Heart Rate:** BPM
- Effective date (for historical accuracy)

**Running:**
- **Threshold Pace:** Min/km or min/mile
- **LTHR:** BPM
- **Max Heart Rate:** BPM

**Swimming:**
- **Threshold Pace:** Per 100m/100yd
- **CSS (Critical Swim Speed)**

### Zone Configuration Interface

#### Power Zones (Cycling)
Default 7-zone model based on FTP percentage:

| Zone | Name | % FTP | Description |
|------|------|-------|-------------|
| Z1 | Active Recovery | < 55% | Easy spinning |
| Z2 | Endurance | 55-75% | Aerobic base |
| Z3 | Tempo | 76-90% | Moderate intensity |
| Z4 | Threshold | 91-105% | FTP work |
| Z5 | VO2max | 106-120% | High intensity |
| Z6 | Anaerobic | 121-150% | Short, hard efforts |
| Z7 | Neuromuscular | Max | Sprints |

**Customization Options:**
- Adjust zone boundaries
- Rename zones
- Use custom zone models (3, 5, 6, or 7 zones)
- Import from other platforms

#### Heart Rate Zones
Default 5-zone model:

| Zone | % LTHR | % Max HR |
|------|--------|----------|
| Z1 | < 81% | < 68% |
| Z2 | 81-89% | 68-83% |
| Z3 | 90-93% | 84-94% |
| Z4 | 94-99% | 95-99% |
| Z5 | 100%+ | 100%+ |

#### Settings UI Pattern

1. **Navigation:** Settings > Zones
2. **Sport selector:** Tabs or dropdown for Bike/Run/Swim
3. **Threshold input:** Numeric field with unit
4. **Auto-calculate:** Button to derive zones from threshold
5. **Manual override:** Editable zone boundaries
6. **History:** View/edit past threshold values with dates

### Threshold History

- Timestamped records of FTP/threshold changes
- Activities use the threshold active at time of recording
- Retroactive recalculation option

---

## 6. Mobile vs Desktop Differences

### Desktop (Web Application)

**Full Feature Set:**
- Complete PMC with all controls
- Multi-pane workout analysis
- Full calendar with drag-drop
- Detailed settings configuration
- Coach dashboard features
- Bulk operations

**Layout:**
- Horizontal navigation bar
- Sidebar for quick access
- Multiple panels visible simultaneously
- Wide charts and graphs

### Mobile Application

**Source:** [TrainingPeaks Mobile App](https://help.trainingpeaks.com/hc/en-us/sections/200328903-Mobile-Apps)

#### Optimized Features

**Dashboard:**
- Vertically stacked widgets
- Swipe between sections
- Key metrics prominently displayed
- Simplified PMC view (current values, mini chart)

**Activity View:**
- Summary metrics at top
- Scrollable metric cards
- Simplified graph (fewer overlay options)
- Full-screen map view
- Swipe between activities

**Calendar:**
- Week view default (scrollable)
- Tap to expand day
- Limited drag-drop (reschedule via edit)
- Pull-to-refresh

#### Mobile-Specific Features
- Push notifications for workout reminders
- Quick-log for manual entries
- Sync with device (Garmin, Wahoo, etc.)
- Offline access to planned workouts
- Apple Watch / WearOS companion apps

#### Feature Parity Gaps
- No full ATP editing
- Limited workout builder
- Simplified zone settings
- Cannot manage coach relationships
- Reduced chart interactivity

### Responsive Design Notes

TrainingPeaks web app is responsive but optimized for desktop:
- Tablet: Near-full experience
- Phone browser: Redirects to app download
- PWA support: Limited

---

## Key Takeaways for Implementation

### Design Patterns to Consider

1. **Widget-based dashboard** - Modular, customizable layout
2. **Card-based metrics** - Clear hierarchy, scannable
3. **Layered graphs** - Multi-metric overlay with toggles
4. **Color consistency** - Sport types and zone levels
5. **Threshold-aware calculations** - Historical accuracy
6. **Progressive disclosure** - Summary → detail views

### Essential Features (MVP)

1. PMC visualization (CTL/ATL/TSB)
2. Activity detail with time-in-zone
3. Calendar with planned vs completed
4. Configurable thresholds (FTP, LTHR)
5. Zone display and calculations

### Premium Differentiators in TrainingPeaks

- Coach-athlete sharing
- Workout library and builder
- WKO integration
- Advanced analytics (power duration curve)
- Multi-sport scheduling

---

## Sources

1. TrainingPeaks Help Center - https://help.trainingpeaks.com/
2. TrainingPeaks Dashboard - https://help.trainingpeaks.com/hc/en-us/articles/204071804-Dashboard
3. TrainingPeaks PMC - https://help.trainingpeaks.com/hc/en-us/articles/204071764-Performance-Management-Chart
4. TrainingPeaks Workout Details - https://help.trainingpeaks.com/hc/en-us/articles/204071944-Viewing-Workout-Details
5. TrainingPeaks Zones Settings - https://help.trainingpeaks.com/hc/en-us/articles/204071884-Setting-Your-Zones
6. TrainingPeaks Calendar - https://help.trainingpeaks.com/hc/en-us/articles/204071674-Calendar
7. TrainingPeaks Mobile Apps - https://help.trainingpeaks.com/hc/en-us/sections/200328903-Mobile-Apps
8. TrainingPeaks Peak Performance - https://help.trainingpeaks.com/hc/en-us/articles/204072044-Peak-Performance-Charts

---

*Research compiled: August 2025*
*Based on publicly available TrainingPeaks documentation*
