# 02 — All chart series + time/distance axis toggle

**What to build:** The activity detail page shows HR, power, speed/pace, and elevation chart series (in addition to the speed chart from ticket 01). Each chart has a per-chart toggle between time and distance x-axes. The distance resampler (pure function: resample a ride's records to uniform 50m distance buckets, preserving hr/power/alt/speed at each bucket) lands here, unit-tested, since the distance axis depends on it. Default axis is time; toggle to distance resamples on demand.

**Blocked by:** 01 (tracer-bullet spine)

**Status:** ready-for-agent

- [ ] Activity detail renders HR, power, speed/pace, and elevation series alongside the existing speed chart
- [ ] Each chart has a visible toggle between time and distance axes; default is time
- [ ] Toggling a chart to distance axis resamples its series to 50m buckets via the distance resampler
- [ ] Distance resampler is a pure function, unit-tested: uniform 50m buckets, handles zero-distance activity, preserves hr/power/alt at each bucket, truncates to the shorter ride when comparing (used by ticket 05)
- [ ] Component test: toggling a chart swaps its x-axis and re-renders the series
- [ ] Integration test: `GET /activities/:id/records` returns both time-indexed and distance-indexed shapes (or the raw records + resample params the frontend needs)