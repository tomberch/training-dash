# Coach Spec: Athlete Snapshot & Training Calendar

> Wayfinder ticket #713 (map #706). Resolution of the Athlete Snapshot + Training Calendar decisions.
> Research inputs: [adaptive-planning inputs](../research/adaptive-planning-inputs.md) (#709), [Ollama Cloud audit](../research/ollama-cloud-model-audit.md) (#707), [goal compatibility](../research/goal-compatibility.md) (#708).

## 1. Athlete Snapshot

The **Athlete Snapshot** is the structured, canonical view of one athlete that is fed to the LLM
(plan generation today; weekly adaptation in v2). It is assembled with a deterministic collector —
the LLM never receives raw daily wellness values, only rolling states.

### MVP blocks

| # | Block | Contents | Source |
|---|-------|----------|--------|
| 1 | Fitness | Current FTP / wCP, power-per-kg; 42-day CTL/ATL/TSB trend; 7-day CTL delta (ramp rate) | Existing `FitnessHistory` / `pmc.py` — read, no new computation |
| 2 | Load distribution | Last 28 days TSS by intensity zone; easy / threshold / hard session mix | Existing activity metrics |
| 3 | Weight & body | Latest `weight_kg`, 14-day trend direction, 30-day slope | `MetricEntry` (`weight_kg`) |
| 4 | Wellness (rolling only) | Sleep duration 3-night avg; RHR 7-day avg; HRV 7-day avg **vs 28-day baseline** — each as `normal / elevated / depressed` state, never raw daily numbers | `MetricEntry` (`category: recovery`, `source: device`) |
| 5 | Nutrition compliance | Last-7-days avg kcal + protein vs. targets | Food log (nutrition pillar) |
| 6 | Goals & constraints | Active goal(s) with baseline/target/(optional date); effective Training Calendar availability; equipment | Coach pillar |
| 7 | Session context | Yesterday: planned vs. actual; latest Check-In fatigue feel + free-text note verbatim | Activity data + Check-In |

Design rules:

- **Wellness states are classified** against personal baselines in the collector (deterministic);
  the snapshot exposes the state, the raw number stays in the DB. Rolling averages only —
  never daily values for HRV/RHR (#709: converging signals; single-session noise ±3–5%).
- **Generation-time fatigue shaping:** the current TSB/wellness states can *delay the first
  high-intensity session* of a new plan (deep negative TSB + depressed states → first hard day
  moves mid-week after easy spinning). From week 2 onward the static rule below governs —
  a plan is written before the future exists.
- The snapshot is rendered for auditability (LLM input viewable in the Coach UI) — see map fog.

### Fitness-floor rule (plan validity)

A generated plan is **invalid** if: it contains high-intensity sessions on consecutive days
without a recovery day between, or violates the nutrition engine's deterministic bounds (#711).
Shape is validated by Zod (#712), content by the deterministic engine — split of concerns.

### Daily execution layer (v2 loop hook)

Workouts carry **Movability Flags** at generation time: `pinned` (hard sessions with built-in
recovery) vs `swappable` (easy/endurance). The v2 daily layer makes a *deterministic* swap when
this morning's wellness states go red: move today's `swappable` hard session out, pull an
endurance session in. No LLM call is needed for the swap decision. Named v2 feature — not MVP scope.

## 2. Training Calendar

The **Training Calendar** is the availability model on which generated plans are placed.

### Availability

- **Availability Template** — a weekly recurring grid on the user (per weekday:
  `rest / available(hours)`), e.g. Mon 1h, Tue 0h, Wed 2h. Lives on the user like Preferences.
- **Availability Override** — a per-date exception (travel, race day, holiday). Rare by design;
  merged over the template.
- Effective availability = template + overrides merged for the next N weeks; fed to the
  plan generator.

### Placement semantics

- Weeks are **Monday-start**.
- Every planned workout must fit inside the day's available hours (deterministic placement
  precedes LLM narrative — the LLM orders workout types within an already-feasible skeleton).
- **At most one high-intensity session per available day; no high-intensity on consecutive
  days** unless a recovery day sits between. This is the plan-validity floor above.
- **A-Races** as first-class calendar entries: **deferred** (v2; consumes #708's
  taper-exclusion rule when it lands).

## 3. Check-In

The **Check-In** is the daily self-report source for the Session-context block. Deliberately
minimal (adoption friction is the real risk):

- Fatigue feel: 1–5 (single tap)
- Optional free-text note → flows into the snapshot verbatim (pain can be mentioned informally)
- Soreness flags: **dropped** (noisy, not load-actionable; injury trend-detection is a possible
  later feature — see map fog)
- Session outcome is automatic (planned vs. actual from activity data)

Storage: `MetricEntry` rows (`category: recovery`) — rides existing `/me/metrics` plumbing,
no new table.

## 4. Wellness & weight data flow

- **Nightly Garmin wellness sync** (alongside existing 2/3 AM activity imports):
  sleep sessions (duration only), RHR, HRV → `MetricEntry` rows, `source: device`
  (device entries are protected from manual edits by existing API rules).
- **Watermark self-heal** reused: a missed cron tick backfills the missed window via
  `last_synced_at`.
- **Weight source (MVP): manual Coach daily log** — entries `source: manual`,
  `source_detail: coach_daily_log`, so a future Garmin Index / body-composition sync can
  coexist (device-vs-manual precedence settled in the data-model ticket).
  Body-composition sync: **deferred**.

## Glossary deltas

New canonical terms (to be added to CONTEXT.md by the data-model/spec pass):

- **Athlete Snapshot** — the structured canonical view of one athlete fed to the LLM; raw
  wellness values never enter it, only baseline-classified rolling states.
- **Training Calendar** — the availability model on which plans are placed.
- **Availability Template** — the weekly recurring availability grid on the user.
- **Availability Override** — a per-date exception merged over the template.
- **Check-In** — the minimal daily self-report (fatigue feel 1–5 + optional note).
- **Movability Flag** — per-workout `pinned`/`swappable`; consumed by the v2 daily swap layer.
- **Fitness-Floor Rule** — plan validity: no consecutive high-intensity days without recovery.