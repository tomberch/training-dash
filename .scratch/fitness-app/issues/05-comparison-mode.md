# 05 — Comparison mode: second-ride selection + time-gap curve + map recolor

**What to build:** On an activity detail whose `route_id` is set, the user selects a second same-route ride to compare against. The app resamples both rides' records to a common distance axis (50m buckets via the resampler from ticket 02), computes the cumulative-elapsed-time difference at each bucket, and renders a continuous time-gap-vs-distance curve (positive = current ride slower/behind, negative = faster/ahead). The map polyline recolors by per-bucket gap value (green where faster, red where slower). The second ride's polyline overlays on the map in a contrasting color.

**Blocked by:** 02 (distance resampler), 04 (route matching provides `route_id` to find candidate rides)

**Status:** ready-for-agent

- [ ] When the current activity has a `route_id`, the detail page offers a picker of other same-route activities for this user
- [ ] Selecting a second ride renders the time-gap-vs-distance curve (single line, distance on x-axis, gap seconds on y-axis, positive=slower)
- [ ] Selecting a second ride overlays its polyline on the map in a contrasting color
- [ ] The current ride's polyline recolors by per-bucket gap value (green=faster, red=slower)
- [ ] `GET /activities/:id/compare?other=:id2` returns the time-gap series as JSON: `[{ distance_m, gap_s }, ...]`
- [ ] Both rides must share a `route_id`; mismatched routes return a no-comparison message
- [ ] Integration test: two same-route rides return a time-gap series aligned by 50m distance buckets; signs correct (faster ride has negative gap)
- [ ] Integration test: gap series truncates to the shorter ride's total distance
- [ ] Component test: time-gap curve renders green where gap is negative, red where positive; second polyline overlay renders; no-overlap message renders when routes don't match