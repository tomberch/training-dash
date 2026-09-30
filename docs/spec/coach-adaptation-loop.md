# Coach Spec: Adaptation Loop (v2)

> Wayfinder ticket #716 (map #706). Resolution of the dynamic adaptation loop definition.
> Research inputs: [goal compatibility](../research/goal-compatibility.md) (#708), [adaptive-planning inputs](../research/adaptive-planning-inputs.md) (#709).
> Companion specs: [Snapshot & Calendar](coach-athlete-snapshot-and-calendar.md) (#713), [Nutrition Engine](coach-nutrition-engine.md) (#714), [Goal Model & Plan Schema](coach-goal-model-and-plan-schema.md) (#715).

The **Adaptation Loop** is the feedback-control system through which the Coach adapts nutrition
targets, the training plan, and (later) its own models of the athlete, based on observed
outcomes. Deterministic parts run in MVP; the LLM parts land in v2. Custom ML response-curve
fitting remains deferred (map: out of scope); structured logging from day one keeps it possible.

## 1. Weekly Adaptation Call (LLM, v2)

### Contract

- **Runs:** weekly cron, off-peak (deepseek-v4.1-flash per #707), only when an `active` plan exists.
- **Consumes** (deterministically pre-assembled — never raw data): Compliance Digest (#714),
  weight trend (14d direction + 30d slope, #713), wellness states (rolling, #709), plan
  adherence (completed vs planned, TSS delta), 4-week re-detection markers (§3), goal target
  progress.
- **Two-pass structure:**
  1. **Deterministic proposer** — the engine computes the *allowed adjustment range* for both
     levers first (nutrition bounds from #711; plan-change envelope from #715 validation).
  2. **LLM picks within the range** + writes the weekly narrative. It never invents numbers
     from raw data.
  3. **Deterministic checker** re-validates whatever the LLM produced; violations are clamped
     and visibly flagged (map Notes).
- **Levers (only these):** ① deficit size / macro split, within #711 bounds, floors never move
  (floor-checked by the nightly engine); ② upcoming-week plan modifications, emitted as a **new
  Plan Version** with `attribution: adapted_llm`, passing the full deterministic validation
  envelope (fitness-floor, availability, specificity, ramp).
- **Produces:** the weekly narrative ("why your targets/plan changed") — stored, shown on the
  version/targets, never parsed for meaning.

### Execution-time layer (daily, deterministic — no LLM)

- **Daily swap (#713):** after the nightly wellness sync, if the morning's wellness states are
  red, today's `swappable` HI session is swapped for an endurance pull (or moved), producing a
  new Plan Version with `attribution: adapted_deterministic`. Executed **at sync time**, so the
  day's workout is settled before the user first opens the app. `pinned` sessions with built-in
  recovery are never auto-swapped.
- Nutrition trend-safety shrink (#714) runs in the same nightly pass.

## 2. Conflict Resolution (deterministic precedence)

When goals collide mid-block (e.g. weight dropping faster than plan while an intensity block is
scheduled):

1. **Health floors win, always** — #711 bounds are non-negotiable.
2. **Primary Goal Focus** second.
3. **Subordinate goals** third.

Mechanics: an over-aggressive deficit triggers #714's trend-safety shrink first. Only if the
shrunken deficit cannot fuel the scheduled intensity (energy needed > energy available) does the
engine **soften the plan**: downgrade the day (HI → sweetspot/endurance), emit a new Plan Version
(`adapted_deterministic`), flag it visibly. The LLM narrates the collision at the next weekly
call; the LLM itself never arbitrates conflicts.

## 3. Four-Week Re-Detection Rhythm

Every 4 weeks (aligned to block boundaries; per #708's cadence research), a deterministic
re-detection pass recomputes baseline-dependent values:

- **Wellness baselines** — 28-day HRV/RHR/sleep baselines re-anchored (#709).
- **FTP re-test prompt** — via the existing threshold/recalculation machinery; not forced.
- **Goal velocity re-check** — is each target progressing at its planned rate?

FTP progress measures through the existing threshold pipeline. If the FTP goal has moved less
than half the target delta by mid-plan, the plan's remaining emphasis is **re-derived
deterministically** (new Emphasis Vector mix) and flagged.

No LLM participates in re-detection itself; the LLM first sees re-detected values at the next
weekly call.

## 4. Learning substrate

Every loop cycle appends to the structured history the map's Notes promised: targets +
narrative per week, plan versions with attribution, compliance, weight trends, wellness states,
re-detection results. This is the dataset that makes (a) the v2 loop explainable and
(b) a future ML response-curve model possible without backfilling.

## Glossary deltas

_New canonical terms for CONTEXT.md:_

- **Adaptation Loop** — the feedback-control system: weekly LLM pass (bounded, two-pass,
  narrated) + nightly deterministic pass (trend-safety shrink, daily swap) + 4-week
  re-detection rhythm.
- **Re-Detection** — the deterministic 4-week pass recomputing wellness baselines, prompting
  FTP re-tests, and re-checking goal velocity.
- **Allowed Adjustment Range** — the pre-computed bounds handed to the LLM by the deterministic
  proposer; the LLM never operates outside them.