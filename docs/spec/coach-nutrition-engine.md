# Coach Spec: Nutrition Engine & Photo Pipeline

> Wayfinder ticket #714 (map #706). Resolution of the deterministic nutrition engine and the meal-photo pipeline.
> Research inputs: [energy-balance](../research/energy-balance-nutrition-engine.md) (#711), [photo accuracy](../research/photo-nutrition-accuracy.md) (#710), [Ollama Cloud audit](../research/ollama-cloud-model-audit.md) (#707).

## 1. Deterministic Nutrition Engine

### Cadence & ownership

- **Nightly deterministic compute** (cron, alongside existing jobs): Daily Targets derived from the
  #711 formula set — inputs: latest weight, moving 4-week-average intake, 4-week weight trend,
  active goal type (deficit/surplus selector). No LLM dependency: targets exist without any model call.
- **User's daily view** always shows yesterday's finalized targets — no intraday recalibration.
- **Weekly LLM adjustment** (v2 adaptation step): may modify *deficit size and macro split only*,
  always within #711 bounds — floors never move. Runs off-peak on `deepseek-v4.1-flash` (#707);
  stores a narrative "why your targets changed this week" summary with the weekly record
  (visibly-flagged requirement).
- **Trend-safety shrink (immediate, deterministic):** if weight trend deviates from plan
  (losing faster than the 0.5%/wk target), the engine autonomously shrinks the deficit and flags it.
  No LLM involved.

### Bounds (enforced in code, per #711)

EA floor 30 kcal/kg FFM/day; max loss 1.0% BW/wk hard / 0.5% target; protein 1.8–2.4 g/kg BW;
fat floor max(20% energy, 0.5 g/kg); absolute calorie floor max(BMR, EA-derived, 1200F/1500M).
Deficit macro order: protein + carbs protected first, fat absorbs remainder; on collision,
shrink the deficit. Full formula appendix in the research doc.

## 2. Meal-Photo Pipeline (MVP)

1. **Upload** — PWA camera/file input; photo stored, user-attached (retained by default).
2. **Single VLM call** — `glm-5.3-flash` identifies **items + rough quantities in household
   terms** ("2 slices bread, 200g rice"). The LLM never outputs kcal/macros.
3. **Deterministic matching** — per item: food-DB embed-search top-5 → deterministic pick; or
   Open Food Facts barcode/brand match when packaging text is detected. USDA FDC is the primary
   DB (CC0, FNDDS household weights), OFF secondary (ODbL, provenance separated). kcal/macros
   computed in application code only — VLM calorie numbers are never stored.
4. **Correction UI** — per-item cards: portion slider, swap-food, add-missing-item
   (oil/dressing nudges = the hidden-calorie countermeasure), barcode scan.
5. **Clarification** — one follow-up VLM call max, only when item confidence is low or a portion
   input is implausible ("cooked or dry?"); then best guess.
6. **Confirmation** — user confirms → Meal Entry finalized (itemized); photo retained; corrections
   stored verbatim (accuracy mechanism now, correction-learning data later).

### Failure posture

- **Manual-only fallback:** VLM down / no items → direct food-DB search entry. The photo is an
  accelerant, never a gate.
- Target blended accuracy ~20–30% kcal MAPE with corrections; hidden calories dominate the
  unfixable residue (#710).

## 3. Day-Loop Semantics

- **Day definition:** meals belong to the calendar day they are logged on (user's local date);
  no cross-midnight "nutrition day."
- **Compliance math:** confirmed meals only. Drafts (unconfirmed photo entries) show a visible
  preview ("+520 kcal pending") but never count until confirmed.
- **Weekly digest:** the snapshot's 7-day averages (#713 block 5) roll from confirmed entries
  only.
- **Retroactive editing:** confirmed entries are editable; every edit re-computes from the DB
  match and logs `edit` provenance, so the adaptation loop can distinguish estimated vs
  user-corrected intake.
- **Floor flag:** a confirmed day below the absolute floor is flagged visibly ("below safe
  minimum") — informational only; the engine consumes 7-day averages, so single bad days cannot
  whipsaw targets.

## Glossary deltas

_New canonical terms for CONTEXT.md:_

- **Daily Targets** — the per-day kcal + macro goals the engine derives nightly; yesterday's
  finalized set is what the UI shows. The LLM never sets them directly.
- **Meal Entry** — a confirmed, itemized food record for one calendar day, with optional photo,
  item-level provenance (estimate/correction/edit), and deterministic macro computation from the
  food DB.
- **Draft Meal** — an unconfirmed photo-derived entry; excluded from compliance math until
  confirmed; shown as pending preview.
- **Compliance Digest** — the 7-day confirmed-entry averages feeding the Athlete Snapshot's
  nutrition-compliance block and the weekly adaptation.