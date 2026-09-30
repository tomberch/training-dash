# Coach Spec: Goal Model & Plan Schema

> Wayfinder ticket #715 (map #706). Resolution of the Goal model, Plan schema, and plan lifecycle.
> Research inputs: [goal compatibility](../research/goal-compatibility.md) (#708), [structured-output reliability](../research/structured-output-reliability.md) (#712).
> Companion specs: [Athlete Snapshot & Training Calendar](coach-athlete-snapshot-and-calendar.md) (#713), [Nutrition Engine & Photo Pipeline](coach-nutrition-engine.md) (#714).

## 1. Goal Model

A user has **at most one active Plan**. A Plan has **one primary Goal Focus** plus **zero or more
subordinate Goals** (tracked for compliance; subordinated in conflict — the #708 one-primary pattern).

### Goal Focus (closed enum, MVP)

Each focus maps deterministically to an **Emphasis Vector** over the existing 7 power zones
(Endurance, Tempo, Sweet Spot, Threshold, VO2 Max, Anaerobic Capacity, Sprint) — TrainerRoad-style
specificity, approximated from existing data (time-in-zone trends + power-duration bests; not a
full Progression-Level engine for MVP).

| Focus | Meaning | Emphasis lean |
|-------|---------|---------------|
| `threshold` | FTP / sustained power | Threshold + Sweet Spot |
| `endurance` | Aerobic duration & stamina | Endurance + Tempo |
| `climbing` | w/kg sustained uphill | Sweet Spot + Threshold, weight-aware |
| `sprint_anaerobic` | Short high power | VO2 + Anaerobic + Sprint |
| `event_prep` | A-event with date (fondo/crit/century) | auto-derived from event type |

### Goals

- **Targets** (one or two per plan): measurable outcome with baseline + target — FTP delta,
  w/kg, peak-power curve position (ActivityPeakPower), weight. Numeric targets are optional
  (direction-only goals are legal).
- **Compatibility:** enforced at plan-creation from a static matrix (#708). Incompatible pairs
  (aggressive cut + performance focus) are rejected at creation; the UI proposes sequencing
  (cut block → ≥2 weeks energy balance → performance block). Compatible pairs are allowed but
  subordinate.
- Weight goals ride as subordinate compliance goals; their bounds come from the nutrition
  engine (#714).

## 2. Plan Schema

Shape follows #712: ≤2 nesting levels, ≤8–10 fields/object, closed enums, all-required,
`additionalProperties: false`. Generated **week-by-week** (chunked; header contract +
previous-week TSS fed forward for ramp consistency). Zod validates shape; the deterministic
engine validates content.

```text
Plan
├─ header: user_id, goal_refs, start_date, n_weeks, model_id, schema_version, narrative
├─ weeks[1..N]                      ← one LLM call per week
│   ├─ week_meta: week_no, focus_note, total_est_tss, narrative
│   └─ days[1..7]
│       └─ day: (
│             date,
│             workout_type,   ← recovery|endurance|tempo|sweetspot|threshold|
│             │                  vo2|anaerobic|strength|rest
│             duration_min,
│             target_intensity, ← zone1..zone7 (existing zone definitions)
│             est_tss,
│             movability,     ← pinned|swappable   (#713)
│             title,
│             cues            ← short LLM guidance; attached, never primary
│           )
└─ validation envelope (not LLM): fitness-floor, availability, specificity,
   ramp checks — all deterministic (#713, #708)
```

Properties:

1. **Days are fixed 7-per-week**; rest is an explicit day (`workout_type: rest`, duration 0) —
   the schema is complete and closed, making Zod validation airtight.
2. **`est_tss` is the LLM's estimate; authoritative TSS is recomputed by us** (duration ×
   zone × current FTP, deterministic calibration). Deltas >20% are flagged. Same discipline as
   the nutrition rule: model estimates are corrected to our computed values, never trusted.
3. **`narrative` / `cues` are attached text** — stored and shown, never parsed for meaning.
4. **Specificity check:** a plan whose generated zone-mix contradicts the goal's Emphasis
   Vector (e.g. `threshold` plan at 90% endurance volume) is invalid — deterministic check.
5. **Strength-inside-plan:** strength is a workout type, not a separate plan; #708's
   strength/endurance separation is a validation edge (strength not adjacent to HI days).
6. Budget per #712: ≤2 Zod retries/week-chunk, `jsonrepair` salvage, `finish_reason` gate,
   ~$0.05–0.15/plan worst case.

## 3. Plan Lifecycle

- **States:** `draft` (generated, unreviewed) → `active` (user accepted) → `archived`
  (superseded or finished). One `active` plan per user.
- **Immutability by versioning:** an active plan's days are never mutated. Any change —
  regeneration, v2 weekly adaptation, user moving a workout, the daily swap — creates a new
  **Plan Version** (full schema copy) with change **attribution**:
  `generated | adapted_llm | adapted_deterministic | user_edit`.
- **Version chain:** each version references the version it supersedes (chain, not tree).
- **Acceptance flow:** user reviews `draft` → accept, or regenerate with free-text feedback
  ("too much intensity Tuesday") attached as a constraint to the regeneration prompt.
  Regenerate-with-feedback is MVP; mid-plan free-text steering is v2.
- Rationale: the adaptation loop needs version + attribution history to learn from;
  "coach said vs user did" stays auditable.

## Glossary deltas

_New canonical terms for CONTEXT.md:_

- **Goal Focus** — the primary emphasis of a Plan (threshold / endurance / climbing /
  sprint_anaerobic / event_prep); MVP enum; one primary per Plan.
- **Emphasis Vector** — the deterministic per-zone emphasis derived from a Goal Focus; the
  specificity target generated plans are validated against.
- **Plan** — a dated multi-week schedule of Workout Days addressing one primary Goal Focus;
  at most one active per user.
- **Plan Version** — an immutable full copy of a Plan created on any change, chained to the
  version it supersedes, with change attribution.
- **Workout Day** — one day of a Plan Version: workout type, duration, target zone, estimated
  TSS (authoritative TSS recomputed), movability, title, cues.
- **Attribution** — the recorded origin of a Plan Version: `generated`, `adapted_llm`,
  `adapted_deterministic`, or `user_edit`.