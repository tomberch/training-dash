# Strava & TrainingPeaks UI Pattern Comparison

## Research Summary

Research conducted for #53 to identify UI patterns from Strava and TrainingPeaks that could improve TrainDash.

---

## Strava Key UI Patterns (2025)

### Activity Detail Page
- **Immersive full-screen layout** - Route, photos, videos showcased prominently
- **Best efforts mapped to route** - Segment achievements shown along the route visually
- **Quick Edit** - Inline editing of activity details without modal dialogs
- **Stat Stickers** - Export stats to Instagram Stories / social
- **3D terrain maps** - FATMAP integration for realistic terrain
- **Dark mode support** - Full dark theme across app

### Feed & Social
- Activity cards with large map preview
- Kudos and comments inline
- Photo carousel prominent
- Segment achievements highlighted with crowns/badges

### Data Visualization
- Clean, minimal charts
- Emphasis on segments and best efforts over raw data
- Social context (leaderboards, comparisons)

---

## TrainingPeaks Key UI Patterns

### Core Metrics Display
TrainingPeaks emphasizes training science metrics:
- **TSS (Training Stress Score)** - Combines intensity + duration
- **IF (Intensity Factor)** - Workout intensity relative to threshold (0-1 scale)
- **NP (Normalized Power)** - Metabolic cost estimate
- **CTL/ATL/TSB** - Fitness/Fatigue/Form in PMC chart

### Workout Analysis
- Zone distribution charts (power and HR)
- Time-in-zone breakdown
- Peak power durations (5s, 1m, 5m, 20m, etc.)
- Interval detection and analysis

### Activity Detail Layout
- Stats summary at top (TSS, IF, NP, duration, distance)
- Large interactive chart with multiple data streams
- Zone distribution sidebar
- Lap/interval breakdown table

---

## TrainDash Current State vs Patterns

### What TrainDash Already Has ✓
1. **TSS, IF, NP metrics** - Full training metrics in Activity Detail
2. **Peak powers** - Already shows peak durations
3. **Zone distribution charts** - Power and HR zone charts exist
4. **PMC chart** - Dashboard has Fitness/Fatigue/Form
5. **Route comparison** - Gap analysis with colored segments
6. **W'bal tracking** - Advanced metric for anaerobic capacity
7. **Dark mode** - Full theme support

### Gaps Identified (for #52)

#### High Impact
1. **Activity title as hero** - Strava puts activity title/name very prominent
   - TrainDash: Has editable title but could be more prominent
   - Already addressed in recent commits (title shown prominently)

2. **Map interaction** - Strava shows position on map when hovering chart
   - TrainDash: Already implemented with CircleMarker

3. **Segment/PR highlighting on map** - Visual callouts for achievements
   - TrainDash: Has breakthrough badge but no map integration

#### Medium Impact
4. **Photo support** - Strava shows photos from ride prominently
   - TrainDash: No photo support (not in scope currently)

5. **Social features** - Kudos, comments, sharing
   - TrainDash: Single-user app, not applicable

6. **Mobile-first responsive** - Strava mobile is primary
   - TrainDash: Desktop-focused, responsive but not mobile-first

#### Low Impact (Nice to Have)
7. **3D terrain** - FATMAP style 3D maps
8. **Stat stickers** - Social export
9. **Quick edit everything** - Inline editing throughout

---

## Recommendations

### Already Addressed in UX Overhaul
- ✓ Activity titles prominent (#49)
- ✓ Mini-maps for visual preview (#48, #51)
- ✓ What's Notable section for breakthroughs/PRs (#50)
- ✓ Modern card-based layout (#51)
- ✓ Consistent branding (#55)
- ✓ Design tokens (#58)

### Future Enhancements
1. **Segment achievements on map** - Show PR/breakthrough locations
2. **Lap detection UI** - Better interval breakdown display
3. **Activity comparison summary** - Side-by-side stats table
4. **Export/share options** - PNG export of charts/stats

---

## Conclusion

TrainDash already implements the core TrainingPeaks-style analytics (TSS, IF, NP, zones, peaks, PMC) which is appropriate for a training-focused app. The recent UX overhaul brought it closer to Strava's visual appeal (mini-maps, card layouts, prominent titles, breakthrough highlights).

The main differentiator for TrainDash is the deep training science metrics combined with route comparison and W'bal analysis - features that go beyond what Strava offers for free.
