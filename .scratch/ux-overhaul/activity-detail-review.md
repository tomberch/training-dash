# Activity Detail Review Against Strava/TrainingPeaks Patterns

## Review Summary (Issue #52)

Reviewing `frontend/src/ActivityDetail.tsx` against competitor UI patterns.

---

## Current ActivityDetail Features

### Layout Structure
```
Header
├── Back button
├── Title (editable, with generate button)
├── Date/time subtitle with icons
└── Breakthrough badge

Stats Grid - Ride Basics
├── Distance | Moving Time | Elevation | Avg Speed | Avg HR

Stats Grid - Training Metrics
├── Avg Power | NP | IF | TSS | W'bal Min | Max HR

Peak Powers Section
Zone Distribution (Power + HR)
Route Comparison Selector
Map (with start/end markers, hover position)
Gap Chart (comparison mode)
Data Charts (Speed, HR, Power, Elevation)
W'bal Chart
```

### Existing Strengths ✓
1. **Comprehensive metrics** - All key training metrics (TSS, IF, NP, zones, peaks)
2. **Interactive charts** - Time/distance toggle, hover sync with map
3. **Route comparison** - Unique feature with gap analysis
4. **W'bal visualization** - Advanced anaerobic tracking
5. **Editable titles** - With auto-generate from GPS
6. **Dark mode** - Full support
7. **Zone charts** - Both power and HR with color coding
8. **Start/end markers** - Visual map markers
9. **Breakthrough badge** - Prominent when applicable

---

## Comparison with Strava/TrainingPeaks

### Header Section
| Feature | Strava | TrainingPeaks | TrainDash |
|---------|--------|---------------|-----------|
| Activity title prominent | ✓ Hero | ✓ Top | ✓ Good |
| Date/time visible | ✓ | ✓ | ✓ |
| Activity type icon | ✓ | ✓ | ✗ |
| Edit title inline | ✓ Quick Edit | ✓ | ✓ |

**Gap**: Activity type icon (bike, run, etc.) not shown. Minor.

### Stats Display
| Feature | Strava | TrainingPeaks | TrainDash |
|---------|--------|---------------|-----------|
| Distance | ✓ | ✓ | ✓ |
| Time | ✓ | ✓ | ✓ |
| Elevation | ✓ | ✓ | ✓ |
| Speed | ✓ | ✓ | ✓ |
| TSS/IF/NP | ✗ Premium | ✓ | ✓ |
| Zones | ✗ Premium | ✓ | ✓ |
| Peak powers | ✗ Premium | ✓ | ✓ |
| W'bal | ✗ | ✗ | ✓ Unique |

**Strength**: TrainDash has TrainingPeaks-level metrics without subscription.

### Map Features
| Feature | Strava | TrainingPeaks | TrainDash |
|---------|--------|---------------|-----------|
| Route display | ✓ | ✓ | ✓ |
| Start/end markers | ✓ | ✓ | ✓ |
| Hover sync | ✓ | ✓ | ✓ |
| 3D terrain | ✓ FATMAP | ✗ | ✗ |
| Segment markers | ✓ | ✗ | ✗ |
| Comparison overlay | ✗ | ✗ | ✓ Unique |

**Strength**: Route comparison with gap coloring is unique to TrainDash.

### Charts
| Feature | Strava | TrainingPeaks | TrainDash |
|---------|--------|---------------|-----------|
| Multi-stream chart | ✓ | ✓ | ✓ Separate |
| Time/distance toggle | ✓ | ✓ | ✓ |
| Zone backgrounds | ✗ | ✓ | ✗ |
| Lap markers | ✓ | ✓ | ✗ |

**Gap**: Could add zone threshold lines or lap markers to charts.

---

## Recommendations

### No Action Needed
These are already at parity or better:
- Title editing
- Core stats display
- Training metrics (TSS/IF/NP)
- Zone distribution
- Peak powers
- Map with markers
- Chart hover sync
- Route comparison

### Minor Enhancements (Future)
1. **Activity type icon** - Add bike/run icon next to title
2. **Lap markers on charts** - If lap data available, show vertical lines
3. **Zone threshold lines** - Show FTP/threshold on power chart

### Won't Do
- 3D terrain (requires FATMAP-style infrastructure)
- Segment crowns (requires segment database like Strava)
- Photos (not in current scope)

---

## Verdict

**ActivityDetail is already competitive with Strava and TrainingPeaks.**

The page provides:
- TrainingPeaks-level training analytics (TSS, IF, NP, zones, peaks, W'bal)
- Strava-like visual appeal (clean layout, map, dark mode)
- Unique features (route comparison with gap analysis, W'bal chart)

The recent UX overhaul (#47-59) addressed the main visual gaps. The Activity Detail page is solid as-is.
