# Competitor training-platform UI — research

> Purpose: feed a design brief for improving TrainingDash's GUI polish.
> Date: Aug 09 2026

## Summary

- **The PMC (fitness/fatigue/form) chart is the load-bearing "polished" surface across serious-training platforms.** TrainingPeaks commits a documented, ecosystem-wide color convention — CTL = blue, ATL = purple, TSB = yellow — reused in font, line, and card badge so the same metric is identifiable in every context ([CTL](https://help.trainingpeaks.com/hc/en-us/articles/204071884-Fitness-CTL), [ATL](https://help.trainingpeaks.com/hc/en-us/articles/204071894-Fatigue-ATL), [TSB](https://help.trainingpeaks.com/hc/en-us/articles/204071764-Form-TSB)). This is the single most stealable "polish" pattern: one metric = one color, everywhere.
- **Charts that "don't get cut off" share three behaviors: zoom/brush linkage to the map, a fullscreen escape hatch, and resizable/overlayable series.** Garmin Connect explicitly documents chart zoom-to-time-range and series overlay on the activity detail ([Garmin Connect: Viewing Activity Chart Details](https://support.garmin.com/en-IE/?faq=V0T9hu0HIa8uj2gi0ea9aA)); Strava explicitly documents a fullscreen map with a linked elevation profile ([How to Use Fullscreen Maps](https://support.strava.com/en-us/articles/15401907-how-to-use-fullscreen-maps)).
- **Stats are repeated across contexts at decreasing density** (card → weekly summary → home → dashboard chart), not computed once and shown once. TrainingPeaks shows the same CTL/ATL/TSB in four places with consistent color coding ([CTL](https://help.trainingpeaks.com/hc/en-us/articles/204071884-Fitness-CTL), [ATL](https://help.trainingpeaks.com/hc/en-us/articles/204071894-Fatigue-ATL), [TSB](https://help.trainingpeaks.com/hc/en-us/articles/204071764-Form-TSB)). Repetition with consistency reads as "polished"; repetition with drift reads as "buggy".
- **Maps are a commodity surface, not a differentiator: Mapbox tiles + OSM data is the de-facto stack.** Strava uses Mapbox/OSM with Standard + Satellite layers and a documented POI/surface legend ([About Strava Maps](https://support.strava.com/en-us/articles/15402176-about-strava-maps), [Strava Maps Glossary](https://support.strava.com/en-us/articles/15402016-strava-maps-glossary)). The differentiator is the *path overlay* and *linked chart*, not the tiles.
- **The "above the fold" hierarchy is consistent: hero map + headline stats, then charts, then tables/laps/segments.** Strava leads with map + split times; Garmin leads with map + stat tiles then the multi-series chart ([Garmin Connect: Viewing the Details of a Saved Activity](https://support.garmin.com/en-US/?faq=6Dk3BHgLzs13iYV90WX4B9)).
- **Interval detection + per-interval grouped stats is the standout "clever" feature** that distinguishes Intervals.icu from the pack — automatic detection, grouped averages, comparison to prior similar efforts, all rendered on a zoomable timeline ([Intervals.icu home](https://intervals.icu/)).

## Methodology & sources

**Primary sources (first-party help/docs):**
- Strava Help Center — `support.strava.com` articles on Maps, Map Layers, 3D Layer, Fullscreen Maps, Personal Heatmaps, Training Glossary for Cycling.
- Garmin Customer Support — `support.garmin.com` FAQ articles on viewing activity details and viewing activity chart details (reached via search-result snippets; the FAQ pages themselves are JS-rendered and the body did not render in the fetcher, so the key facts are quoted from the official search snippet and marked where the full body was not directly verifiable).
- TrainingPeaks Help Center — `help.trainingpeaks.com` articles on Fitness (CTL), Fatigue (ATL), Form (TSB). These fully rendered and include screenshots of workout cards, weekly summary, Athlete Home, and the PMC.
- Intervals.icu — the public landing page (`intervals.icu`) enumerates the feature set (interval detection, charts, calendar, PMC). The app itself is JS-only and could not be inspected without a session.

**Secondary sources:**
- None used for factual claims. Search engine result pages (DuckDuckGo, Bing) were used only as a *directory* to find first-party URLs, not as a source of facts.

**Gaps / unverified:**
- **Xert** — `xert.com` and `support.xert.com` returned transport errors / were unreachable from this environment on repeated attempts. No first-party UI claims are made for Xert; the platform is listed as **not verified**. A follow-up pass from a different network, or with screenshots supplied by the user, is recommended.
- **Wahoo SYSTM / ELEMNT companion** — deprioritized per the brief; not covered.
- **Garmin Connect visual specifics** (exact colors, spacing, tile patterns) — the support FAQ bodies did not render in the fetcher; only the search-snippet-level facts (left nav → Activities → activity title; chart zoom + overlay; customizable activities table columns) are claimed, and they are tagged as snippet-sourced. Pixel-level Garmin design observations are marked "unverified".
- **Intervals.icu visual specifics** — only the feature list from the landing page is primary; the actual chart rendering, colors, and layout are **unverified** from primary sources because the app requires auth.
- Chart sizing/responsive behavior (min-heights, aspect ratios, container scroll) is **not documented** in any first-party help article found. The cross-cutting observations on this point are inferred from documented *interactions* (zoom, fullscreen, overlay), not from documented CSS. This is flagged explicitly in the relevant section.

## Per-platform findings

### Strava

**Sources:** [About Strava Maps](https://support.strava.com/en-us/articles/15402176-about-strava-maps), [Strava Maps Glossary](https://support.strava.com/en-us/articles/15402016-strava-maps-glossary), [Strava Map Layers](https://support.strava.com/en-us/articles/15401924-strava-map-layers), [3D Layer on Strava Maps](https://support.strava.com/en-us/articles/15401707-3d-layer-on-strava-maps), [How to Use Fullscreen Maps](https://support.strava.com/en-us/articles/15401907-how-to-use-fullscreen-maps), [Personal Heatmaps](https://support.strava.com/en-us/articles/15402028-personal-heatmaps), [Strava Training Glossary for Cycling](https://support.strava.com/en-us/articles/15402109-strava-training-glossary-for-cycling).

**Layout & hierarchy (activity detail):**
- The activity detail page leads with the map + the headline stats (distance, time, elevation, pace/speed) and a title/photo; below that come analysis charts (pace, elevation, HR, power), then splits/laps/segments. (Hierarchy inferred from the documented existence of a fullscreen map with linked elevation profile — [Fullscreen Maps](https://support.strava.com/en-us/articles/15401907-how-to-use-fullscreen-maps) — and the glossary's enumeration of per-activity metrics.)
- The web offers a **fullscreen map** with an embedded elevation profile so the map is not "cramped" inside a half-width column: "we've also included the activity's elevation profile, so you can easily interact with the route" ([Fullscreen Maps](https://support.strava.com/en-us/articles/15401907-how-to-use-fullscreen-maps)). This is the direct answer to "graphs get cut off": promote the map+elevation to fullscreen rather than cramming both into a grid cell.

**Maps:**
- Tiles: **Mapbox** with **OpenStreetMap** data for roads, POIs, trails; satellite imagery from DigitalGlobe/NASA/Mapbox ([About Strava Maps](https://support.strava.com/en-us/articles/15402176-about-strava-maps)).
- Two web map styles: **Standard** and **Satellite** ([About Strava Maps](https://support.strava.com/en-us/articles/15402176-about-strava-maps)).
- Documented **POI legend** (toilet, bike shop, water fountain, cafe, parking, restaurant, viewpoint, beach, peak, bike share, …) and **surface-type legend** (solid white = paved; dashed white = footpath; dashed pink = trail; solid pink = track) ([Strava Maps Glossary](https://support.strava.com/en-us/articles/15402016-strava-maps-glossary)). A documented legend is itself a polish signal: the user can decode the map.
- Mobile-only **3D layer** (pinch to 3D, recommended with Satellite/Hybrid) for elevation visualization ([3D Layer](https://support.strava.com/en-us/articles/15401707-3d-layer-on-strava-maps)).
- **Map Layers** (subscriber): Gradient, Avalanche Gradient, Aspect, Points of Interest — toggleable via a layer icon ([Strava Map Layers](https://support.strava.com/en-us/articles/15401924-strava-map-layers)).
- **Personal Heatmap**: per-sport-group heat with user-chosen heat color, date range, toggle privacy-zoomed/commutes, photo overlay; also toggleable alongside the Global Heatmap ([Personal Heatmaps](https://support.strava.com/en-us/articles/15402028-personal-heatmaps)).

**Stats/metrics (training):**
- Cycling glossary defines: **FTP**, **Weighted Average Power**, **Total Work (kJ)**, **Intensity (% of FTP)**, **Segment Intensity**, **Training Load**, **Power Curve** (W or W/kg, comparable across 6 weeks / year / past years), **Power Zones** (7 zones, % FTP), **Fitness**, **Fatigue**, **Form** ([Training Glossary for Cycling](https://support.strava.com/en-us/articles/15402109-strava-training-glossary-for-cycling)).
- Notably, Strava's Fitness/Fatigue/Form are *impulse-response on Training Load*, i.e. the same Coggan model as TrainingPeaks' CTL/ATL/TSB but branded differently and **not color-codified in the help docs** the way TrainingPeaks is ([Training Glossary for Cycling](https://support.strava.com/en-us/articles/15402109-strava-training-glossary-for-cycling)).
- Intensity is given a **labeled band scale** (Endurance/Recovery ≤65%, Moderate 65–80%, Tempo 80–95%, TT/Race 95–105%, Short TT/Race ≥105%) and Training Load is given a **recovery-time scale** (≤125 → ~24h; 125–250 → 36–48h; 250–400 → ≥3d; 400+ → ≥5d) ([Training Glossary for Cycling](https://support.strava.com/en-us/articles/15402109-strava-training-glossary-for-cycling)). Pairing a raw number with a qualitative band is a cheap, high-impact polish pattern.

**Visual polish specifics:** Strava's help docs do not document the color system, type scale, or spacing rhythm. The brand is widely known to be orange-on-light/dark, but **unverified** from the help center. Not claimed here.

**Notably clever / absent:**
- Clever: documented **POI + surface-type legend** makes the map self-explanatory; **fullscreen map + elevation** solves the cramped-map problem; **personal heatmap** with photo overlay is a delighter.
- Absent (vs Intervals.icu/TrainingPeaks): no documented automatic interval detection; no documented PMC color convention.

---

### Garmin Connect

**Sources:** [Garmin Connect: Viewing the Details of a Saved Activity](https://support.garmin.com/en-US/?faq=6Dk3BHgLzs13iYV90WX4B9), [Garmin Connect: Viewing Activity Chart Details](https://support.garmin.com/en-IE/?faq=V0T9hu0HIa8uj2gi0ea9aA), [Customize the Activities Table in Garmin Connect](https://support.garmin.com/en-US/?faq=UNiiMuOI8J20he59aw5gP9). *Caveat: the FAQ bodies are JS-rendered and did not render in the fetcher; the facts below come from the official Garmin search-result snippets for those same URLs and are marked [snippet].*

**Layout & hierarchy:**
- Web navigation: left nav → **Activities** → **All Activities** → select the activity title to open details ([snippet, Viewing the Details of a Saved Activity](https://support.garmin.com/en-US/?faq=6Dk3BHgLzs13iYV90WX4B9)).
- Activities list is a **customizable table**: columns can be rearranged/added/removed via the table settings ([snippet, Customize the Activities Table](https://support.garmin.com/en-US/?faq=UNiiMuOI8J20he59aw5gP9)). A configurable table is a polish feature TrainingDash likely lacks.

**Charts (the user's core complaint):**
- Activity charts show **elevation, speed, cadence, heart rate, and more** as multi-series graphs ([snippet, Viewing Activity Chart Details](https://support.garmin.com/en-IE/?faq=V0T9hu0HIa8uj2gi0ea9aA)).
- Two documented interactions that directly address "graphs get cut off":
  1. **Zoom to a time range** — "adjust the view of your graph to zoom into a specific time and view more detailed information" ([snippet](https://support.garmin.com/en-IE/?faq=V0T9hu0HIa8uj2gi0ea9aA)).
  2. **Overlay series** — "you can overlay ..." additional data series on the same chart ([snippet](https://support.garmin.com/en-IE/?faq=V0T9hu0HIa8uj2gi0ea9aA)). Overlaying avoids the "one chart per metric stacked into a tall, cut-off column" anti-pattern.
- Exact responsive sizing / min-heights: **unverified** — not in the help docs.

**Maps:** Garmin's own map tile provider for Connect is not stated in the surfaced help docs. **Unverified.** (Garmin owns its own map IP for devices, but Connect web has historically used a mix; not claimed here.)

**Stats/metrics:** First Training Load, VO2 max, Recovery Time, Training Readiness, HRV Status, etc. are Garmin-device-derived and surface in Connect, but the *UI grouping* is not documented in the surfaced FAQs. **Unverified** beyond "charts include elevation, speed, cadence, heart rate, and more" ([snippet](https://support.garmin.com/en-IE/?faq=V0T9hu0HIa8uj2gi0ea9aA)).

**Visual polish specifics:** Colors, typography, spacing: **unverified** from primary sources.

**Notably clever / absent:**
- Clever: **customizable activities table** ([snippet](https://support.garmin.com/en-US/?faq=UNiiMuOI8J20he59aw5gP9)); **chart zoom + overlay** ([snippet](https://support.garmin.com/en-IE/?faq=V0T9hu0HIa8uj2gi0ea9aA)).
- Gap: the FAQs found describe *how to navigate* and *how to interact*, not *how it's laid out visually*. Pixel-level claims need a screenshot pass.

---

### Intervals.icu

**Source:** [Intervals.icu home page](https://intervals.icu/) (public landing; the app is JS-only and requires auth, so visual specifics are **unverified** beyond the feature list).

**Feature set (from the landing page, primary):**
- **Automatic interval detection** in rides with real power data — "ride your favourite route, punish the rollers and still get good stats." ([Intervals.icu](https://intervals.icu/))
- **Per-interval stats**: power, heartrate, w/kg, torque, cadence, intensity, power zone; **automatic grouping of similar intervals with average stats for the group** ([Intervals.icu](https://intervals.icu/)).
- **Ride timeline chart** showing power, cadence, heartrate, torque, training load, **that highlights intervals with zoom** ([Intervals.icu](https://intervals.icu/)). The "zoom" here is the same anti-cut-off pattern as Garmin/Strava: the chart is interactive, not a fixed-height image.
- **Ride power page**: time in zones, power histogram, power curve (with season curve), best power/duration efforts ([Intervals.icu](https://intervals.icu/)).
- **Athlete power page**: power curve for last 42 days / season, FTP estimation, best efforts, power models ([Intervals.icu](https://intervals.icu/)).
- **Automatic power-spike detection/fix**; manual editing supported ([Intervals.icu](https://intervals.icu/)).
- **Comparison chart** comparing intervals to similar intervals in previous rides ([Intervals.icu](https://intervals.icu/)).
- **Calendar-style training log** with interval summaries and weekly stats (training load, time in power zones) ([Intervals.icu](https://intervals.icu/)).
- **Training load for HR-only rides** estimated from prior HR+power rides ([Intervals.icu](https://intervals.icu/)).
- **Performance management / fitness chart** tracking fitness, fatigue, form — "uses the standard Coggan metrics" ([Intervals.icu](https://intervals.icu/)). So Intervals.icu is on the same CTL/ATL/TSB model as TrainingPeaks; the color convention is **unverified** from primary sources.
- **Email notifications** on new best power/duration efforts and FTP increases ([Intervals.icu](https://intervals.icu/)).
- **FTP estimation from a single 60s+ maximal effort** with training-load-based decay — "no tests!" ([Intervals.icu](https://intervals.icu/)). This is a notable "clever" feature: it removes the friction of the 20-min test.

**Layout/charts/maps/visuals:** **Unverified** — the app requires auth and could not be inspected. The feature list strongly implies a dense, chart-heavy layout (timeline + power page + athlete page + calendar + PMC), but pixel-level claims are not made.

**Notably clever / absent:**
- Clever: automatic interval detection + grouping; FTP estimation from a single effort; comparison-to-prior-similar-intervals; power curve with season overlay.
- Absent (per the landing page): no mention of maps at all — Intervals.icu is chart-first, not map-first. That's a deliberate scope choice worth noting: a training-analysis app can be polished *without* a hero map.

---

### Xert

**Status: not verified.** `xert.com` and `support.xert.com` returned transport errors on repeated attempts from this environment. No first-party UI claims are made. Recommended follow-up: fetch from a different network or have the user supply screenshots. From general knowledge (not cited, treat as **unverified**): Xert's differentiators are the MPA (Maximal Power Attainable) model, Focus & Abilities dashboards, and the "Xert Signature" — but none of this could be confirmed against a primary source in this pass.

### TrainingPeaks

**Sources:** [Fitness (CTL)](https://help.trainingpeaks.com/hc/en-us/articles/204071884-Fitness-CTL), [Fatigue (ATL)](https://help.trainingpeaks.com/hc/en-us/articles/204071894-Fatigue-ATL), [Form (TSB)](https://help.trainingpeaks.com/hc/en-us/articles/204071764-Form-TSB).

**The color convention (the headline finding):**
- **Fitness (CTL) = blue**, "blue font and the blue line (in the Performance Management Chart) through the TrainingPeaks ecosystem" ([Fitness (CTL)](https://help.trainingpeaks.com/hc/en-us/articles/204071884-Fitness-CTL)).
- **Fatigue (ATL) = purple**, "purple font and the purple line ... throughout the TrainingPeaks ecosystem" ([Fatigue (ATL)](https://help.trainingpeaks.com/hc/en-us/articles/204071894-Fatigue-ATL)).
- **Form (TSB) = yellow**, "yellow font and the yellow line (in the Performance Management Chart) through the TrainingPeaks ecosystem" ([Form (TSB)](https://help.trainingpeaks.com/hc/en-us/articles/204071764-Form-TSB)).

The phrase *"through the ... ecosystem"* is the key polish claim: the same metric has the same color in the workout card, the weekly summary, Athlete Home, the PMC, and Coach Home. That consistency is the thing that makes a dashboard feel designed rather than assembled.

**Metric repetition across contexts (documented with screenshots):**
Each of CTL, ATL, TSB is shown in **five web locations** (workout card, weekly summary, Athlete Home, Dashboard/PMC chart, Coach Home) and two mobile locations (iOS, Android), per the screenshots in the three help articles ([CTL](https://help.trainingpeaks.com/hc/en-us/articles/204071884-Fitness-CTL), [ATL](https://help.trainingpeaks.com/hc/en-us/articles/204071894-Fatigue-ATL), [TSB](https://help.trainingpeaks.com/hc/en-us/articles/204071764-Form-TSB)). So the design rule is: **one metric, one color, many surfaces.**

**Formulas (documented):**
- CTL = exponentially weighted average of daily TSS over 42 days (6 weeks) ([Fitness (CTL)](https://help.trainingpeaks.com/hc/en-us/articles/204071884-Fitness-CTL)).
- ATL = exponentially weighted average of daily TSS over 7 days ([Fatigue (ATL)](https://help.trainingpeaks.com/hc/en-us/articles/204071894-Fatigue-ATL)).
- TSB = yesterday's CTL − yesterday's ATL ([Form (TSB)](https://help.trainingpeaks.com/hc/en-us/articles/204071764-Form-TSB)). Note the off-by-one: TSB today is from *yesterday's* values, and today's CTL/ATL feed *tomorrow's* TSB ([Form (TSB)](https://help.trainingpeaks.com/hc/en-us/articles/204071764-Form-TSB)).
- TSB sign convention documented: positive = fresh/over-adapted; neutral = adapted; negative = not adapted ([Form (TSB)](https://help.trainingpeaks.com/hc/en-us/articles/204071764-Form-TSB)).

**Charts:** The Performance Management Chart (PMC) is the dashboard chart; it shows the three lines (blue CTL, purple ATL, yellow TSB) together ([screenshots in CTL/ATL/TSB articles](https://help.trainingpeaks.com/hc/en-us/articles/204071884-Fitness-CTL)). Responsive sizing / zoom behavior: **unverified** from these help articles.

**Layout & hierarchy:** The help articles name the surfaces (Workout card → Weekly Summary → Athlete Home → Dashboard/PMC → Coach Home) which implies a **calendar-centric** top-level layout with the PMC as the dashboard. Exact pixel layout: **unverified**.

**Stats/metrics grouping:** Beyond CTL/ATL/TSB, the help-center section also lists TSS, VI, IF, Normalized Power, Aerobic Decoupling (Pw:Hr / Pa:HR), Efficiency Factor, and Advanced Analysis Metrics ([section nav in any of the three articles](https://help.trainingpeaks.com/hc/en-us/articles/204071884-Fitness-CTL)). So the metric vocabulary is broad and grouped under a "Glossary of Terms" section.

**Visual polish specifics:** Colors are documented for the three PMC metrics only. Typography/spacing/motion: **unverified**.

**Notably clever / absent:**
- Clever: the **ecosystem-wide color convention** is the single most reusable polish pattern in this whole research note.
- Clever: **CTL on planned workouts** updates daily from planned TSS, then re-adjusts to actual TSS on completion ([Fitness (CTL)](https://help.trainingpeaks.com/hc/en-us/articles/204071884-Fitness-CTL)) — the dashboard shows the *forecast* then reconciles, which reads as "smart".
- Absent: maps are not a TrainingPeaks concern; it's calendar + PMC + workout detail, not map-first.

## Cross-cutting observations

### Chart handling & responsive sizing (directly addresses "graphs cut off")

No platform's help docs document CSS-level responsive behavior (min-heights, aspect-ratio, container scroll). What *is* documented, and what correlates with "graphs don't feel cut off", is a set of **interaction patterns** — and these are the actionable takeaways:

1. **Fullscreen escape hatch for the map + elevation.** Strava: "click the full-screen icon ... we've also included the activity's elevation profile" ([Fullscreen Maps](https://support.strava.com/en-us/articles/15401907-how-to-use-fullscreen-maps)). The fix for "cramped" is not bigger CSS; it's a one-click full-viewport mode.
2. **Brush/zoom linkage between map and chart.** Strava's fullscreen map lets you "interact with the route" and the elevation profile follows ([Fullscreen Maps](https://support.strava.com/en-us/articles/15401907-how-to-use-fullscreen-maps)); Garmin lets you "zoom into a specific time and view more detailed information" on the chart ([snippet, Viewing Activity Chart Details](https://support.garmin.com/en-IE/?faq=V0T9hu0HIa8uj2gi0ea9aA)); Intervals.icu's timeline "highlights intervals with zoom" ([Intervals.icu](https://intervals.icu/)). The shared idea: a chart is a *viewport into a longer series*, not a fixed render. TrainingDash's "cut off" graphs are almost certainly fixed-height renders with no zoom/brush.
3. **Overlay multiple series on one chart instead of stacking many charts.** Garmin: "you can overlay ..." ([snippet](https://support.garmin.com/en-IE/?faq=V0T9hu0HIa8uj2gi0ea9aA)). Stacking one chart per metric (power / HR / cadence / speed / elevation) into a tall column is the obvious cause of "cut off" — overlaying them on a shared time axis collapses the height.
4. **A customizable activities table** so the user controls columns, not just chart height. Garmin: rearrange/add/remove columns ([snippet, Customize the Activities Table](https://support.garmin.com/en-US/?faq=UNiiMuOI8J20he59aw5gP9)).

**Design-actionable sizing heuristics (inferred, not from docs):** give every chart a `min-height` plus a `max-height` with internal scroll/zoom rather than a fixed `height`; use an aspect-ratio container for the hero map; never render a 2-hour ride's power series in a 200px-tall fixed box. These are industry-standard but **not explicitly documented** by the platforms above.

### Stat-card patterns

- **One metric, one color, many surfaces** (TrainingPeaks: blue CTL / purple ATL / yellow TSB across workout card, weekly summary, Athlete Home, PMC, Coach Home — [CTL](https://help.trainingpeaks.com/hc/en-us/articles/204071884-Fitness-CTL), [ATL](https://help.trainingpeaks.com/hc/en-us/articles/204071894-Fatigue-ATL), [TSB](https://help.trainingpeaks.com/hc/en-us/articles/204071764-Form-TSB)).
- **Pair every raw number with a qualitative band.** Strava pairs Intensity with a labeled band (Endurance/Moderate/Tempo/TT) and Training Load with a recovery-time band ([Training Glossary](https://support.strava.com/en-us/articles/15402109-strava-training-glossary-for-cycling)). A bare "TL = 187" is unpolished; "TL = 187 — recover 36–48h" is polished.
- **Forecast-then-reconcile.** TrainingPeaks shows planned-TSS-driven CTL forecast, then adjusts to actual on completion ([Fitness (CTL)](https://help.trainingpeaks.com/hc/en-us/articles/204071884-Fitness-CTL)). A stat that updates in place reads as alive.

### Color / typography / spacing rhythm

- **Color:** The only documented, ecosystem-wide system found is TrainingPeaks' PMC triple (blue/purple/yellow). Strava's brand orange and Garmin's palette are **unverified** from help docs. TrainDash's current `--color-chart-ctl: #3b82f6` (blue), `--color-chart-atl: #ec4899` (pink), `--color-chart-tsb: #f59e0b` (amber) — from `docs/design-system.md` — already mirrors this convention (CTL blue, TSB amber/yellow). The ATL color diverges (pink vs TrainingPeaks' purple); a deliberate decision, but worth noting the industry default is purple.
- **Typography / spacing / motion:** **Unverified** across all platforms from primary sources. No help center documents its type scale or spacing rhythm. This is a gap to fill via a screenshot pass, not via docs.

### Map treatment

- **Tile stack: Mapbox + OSM** is the documented Strava default ([About Strava Maps](https://support.strava.com/en-us/articles/15402176-about-strava-maps)). For a self-hosted app, Mapbox/OSM (or the free OSM raster tiles) is the path of least resistance and matches user expectations.
- **A legend is part of the map, not an afterthought.** Strava documents POI icons and surface-type line styles ([Strava Maps Glossary](https://support.strava.com/en-us/articles/15402016-strava-maps-glossary)). A tiny legend strip under the map is a cheap polish win.
- **Layer toggles** (Standard/Satellite, Gradient, Aspect, POI, Heatmap) are the norm, not a single static map ([Strava Map Layers](https://support.strava.com/en-us/articles/15401924-strava-map-layers), [Personal Heatmaps](https://support.strava.com/en-us/articles/15402028-personal-heatmaps)).
- **Charts-first apps skip the map entirely.** Intervals.icu and TrainingPeaks are not map-first ([Intervals.icu](https://intervals.icu/), [TP help](https://help.trainingpeaks.com/hc/en-us/articles/204071884-Fitness-CTL)). If TrainingDash's map is the thing that's "cut off", the question "do we even need a hero map, or are we a charts-first app?" is on the table.

### Empty / loading / error states

**Unverified** across all platforms from primary sources. No help center documents its skeleton/empty/error state patterns. Notably, TrainDash already has a `Skeleton` component (`docs/design-system.md`), which is the right primitive; whether it's used on the activity detail and PMC is an internal audit question, not a competitor-research one.

## Design-actionable patterns worth stealing

- **PMC color triple, ecosystem-wide.** [TrainingPeaks] Blue CTL, purple ATL, yellow TSB — same color in card, weekly summary, home, and chart. TrainDash already matches CTL (blue) and TSB (amber); consider aligning ATL to purple for instant familiarity to anyone who's used TrainingPeaks. ([CTL](https://help.trainingpeaks.com/hc/en-us/articles/204071884-Fitness-CTL), [ATL](https://help.trainingpeaks.com/hc/en-us/articles/204071894-Fatigue-ATL), [TSB](https://help.trainingpeaks.com/hc/en-us/articles/204071764-Form-TSB))
- **Fullscreen map with linked elevation profile.** [Strava] One click → full-viewport map + elevation that scroll together. ([Fullscreen Maps](https://support.strava.com/en-us/articles/15401907-how-to-use-fullscreen-maps))
- **Chart zoom-to-time-range + series overlay.** [Garmin Connect] Stops the "one fixed-height chart per metric, stacked into a cut-off column" anti-pattern. ([snippet, Viewing Activity Chart Details](https://support.garmin.com/en-IE/?faq=V0T9hu0HIa8uj2gi0ea9aA))
- **Interval-highlight timeline with zoom.** [Intervals.icu] A single timeline chart (power/HR/cadence/torque/load) that highlights detected intervals and zooms. ([Intervals.icu](https://intervals.icu/))
- **Pair every raw metric with a qualitative band.** [Strava] Intensity → Endurance/Moderate/Tempo/TT band; Training Load → recovery-hours band. ([Training Glossary](https://support.strava.com/en-us/articles/15402109-strava-training-glossary-for-cycling))
- **Forecast-then-reconcile planned-vs-actual CTL.** [TrainingPeaks] Planned TSS drives a forecast CTL that reconciles to actual on completion. ([Fitness (CTL)](https://help.trainingpeaks.com/hc/en-us/articles/204071884-Fitness-CTL))
- **Customizable activities table.** [Garmin Connect] User can rearrange/add/remove columns. ([snippet, Customize the Activities Table](https://support.garmin.com/en-US/?faq=UNiiMuOI8J20he59aw5gP9))
- **Documented map legend (POI icons + surface line styles).** [Strava] A small legend strip makes the map self-explanatory. ([Strava Maps Glossary](https://support.strava.com/en-us/articles/15402016-strava-maps-glossary))
- **Automatic interval detection + grouping + comparison-to-prior.** [Intervals.icu] The standout "clever" feature if TrainingDash wants to differentiate on analysis. ([Intervals.icu](https://intervals.icu/))
- **FTP estimation from a single maximal effort (no 20-min test).** [Intervals.icu] Reduces friction vs the Strava-documented 20-min-minus-5% protocol. ([Intervals.icu](https://intervals.icu/), contrast [Strava Training Glossary](https://support.strava.com/en-us/articles/15402109-strava-training-glossary-for-cycling))

## Open questions for the design brief

- **Is TrainingDash map-first or charts-first?** Intervals.icu and TrainingPeaks are charts-first and feel polished without a hero map. Strava and Garmin are map-first. The "graphs cut off" complaint may be a symptom of trying to be both. Decide the primary axis first.
- **What's the ATL color?** TrainDash uses pink (`#ec4899`); TrainingPeaks' ecosystem default is purple. Pink-vs-purple is a small thing but it's the one place TrainDash diverges from the most-documented convention. Is the divergence deliberate?
- **What does "polished" mean for the user, concretely?** This research inferred "polish = consistency + interaction (zoom/fullscreen/overlay) + banded metrics." The user's actual complaint is "graphs get cut off" + "doesn't look so polished." A follow-up grilling should separate (a) sizing/overflow bugs, (b) missing interactions, (c) visual consistency, (d) information hierarchy — they have different fixes.
- **Xert gap.** Xert could not be verified from primary sources this pass. Should the design brief wait for an Xert screenshot pass, or proceed with the four verified platforms?
- **Pixel-level audit.** Help docs describe *interactions* and *conventions* but not *CSS*. A screenshot pass (Strava web, Garmin Connect web, Intervals.icu, TrainingPeaks) is needed to extract type scale, spacing rhythm, card densities, and exact responsive behavior. This research is the *what*, not the *how-many-pixels*.
- **Empty/loading/error states.** Unverifiable from docs. Need a screenshot pass with a fresh account (empty) and a slow connection (loading) on each platform.
- **Calendar vs. dashboard as the top-level surface.** TrainingPeaks and Intervals.icu both lead with a calendar; Garmin Connect leads with a left-nav. Which top-level mental model does TrainingDash want?

## Sources

- Strava Help Center — About Strava Maps: https://support.strava.com/en-us/articles/15402176-about-strava-maps
- Strava Help Center — Strava Maps Glossary: https://support.strava.com/en-us/articles/15402016-strava-maps-glossary
- Strava Help Center — Strava Map Layers: https://support.strava.com/en-us/articles/15401924-strava-map-layers
- Strava Help Center — 3D Layer on Strava Maps: https://support.strava.com/en-us/articles/15401707-3d-layer-on-strava-maps
- Strava Help Center — How to Use Fullscreen Maps: https://support.strava.com/en-us/articles/15401907-how-to-use-fullscreen-maps
- Strava Help Center — Personal Heatmaps: https://support.strava.com/en-us/articles/15402028-personal-heatmaps
- Strava Help Center — Strava Training Glossary for Cycling: https://support.strava.com/en-us/articles/15402109-strava-training-glossary-for-cycling
- Garmin Customer Support — Garmin Connect: Viewing the Details of a Saved Activity: https://support.garmin.com/en-US/?faq=6Dk3BHgLzs13iYV90WX4B9
- Garmin Customer Support — Garmin Connect: Viewing Activity Chart Details: https://support.garmin.com/en-IE/?faq=V0T9hu0HIa8uj2gi0ea9aA
- Garmin Customer Support — Customize the Activities Table in Garmin Connect: https://support.garmin.com/en-US/?faq=UNiiMuOI8J20he59aw5gP9
- Intervals.icu — home/feature list: https://intervals.icu/
- TrainingPeaks Help Center — Fitness (CTL): https://help.trainingpeaks.com/hc/en-us/articles/204071884-Fitness-CTL
- TrainingPeaks Help Center — Fatigue (ATL): https://help.trainingpeaks.com/hc/en-us/articles/204071894-Fatigue-ATL
- TrainingPeaks Help Center — Form (TSB): https://help.trainingpeaks.com/hc/en-us/articles/204071764-Form-TSB
- Internal — TrainDash design system: `docs/design-system.md`