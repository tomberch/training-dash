# Energy-balance science for the deterministic nutrition engine — research

> Purpose: feed the nutrition-engine spec (child of #706, blocks #714). A concrete, enforceable formula set for estimating an athlete's energy needs, sizing deficits/surpluses, and distributing macros — plus hard floors/ceilings code can reject plans against.
> Date: Sep 30 2026
> Ticket: tomberch/training-dash#711

## Summary

- **Default BMR formula: Mifflin-St Jeor.** It predicted measured RMR within ±10% in more adults than any other population-level equation (Frankenfield 2005, n=202; [PubMed 15883556](https://pubmed.ncbi.nlm.nih.gov/15883556/)). **Katch-McArdle (`370 + 21.6 × FFM`) becomes the default whenever a validated body-fat % exists** — i.e., for the lean, muscular athletes this app targets, where height-weight equations systematically under-estimate RMR (see O'Neill 2023 athletic-population comparison, [PMC10687135](https://pmc.ncbi.nlm.nih.gov/articles/PMC10687135/)).
- **Never collapse activity into one static multiplier for an app that already knows training load.** `TDEE = BMR × rest-day PAL_base` + explicit exercise energy expenditure (EEE) per session. The classic 1.2/1.375/1.55/1.725/1.9 multipliers bundle exercise and non-exercise activity; using them on top of computed EEE double-counts. PAL_base (non-exercise) ranges 1.2–1.5; EEE comes from power/duration (kcal ≈ kJ ÷ 4.184, gross or ⅔ net).
- **Energy availability (EA) is the primary safety gate, with a hard floor of 30 kcal/kg FFM/day even during deliberate weight loss.** EA = (EI − EEE) / FFM; optimal function at ≥45, clinical LEA risk <30 (female) / <25 (male) (IOC 2018 consensus, [PDF](https://stillmed.olympics.com/media/Documents/Athletes/Medical-Scientific/Consensus-Statements/REDs/IOC-consensus-statement-Relative-Energy-Deficiency-in-Sport-2018.pdf); [Cabre 2022 review](https://pmc.ncbi.nlm.nih.gov/articles/PMC9724109/)). Harmful effects have appeared after just 5 days below 30.
- **Weight-loss rate ceiling: 1.0% BW/week as the engine's enforced max; 0.5% is the recommended target.** Garthe 2011 RCT: 0.7%/wk gained lean mass and strength; 1.4%/wk stalled on both ([PubMed 21558571](https://pubmed.ncbi.nlm.nih.gov/21558571)). Ruiz-Castellano 2021 recommends 0.5–1.0%/wk for lean-mass retention ([Nutrients](https://www.mdpi.com/2072-6643/13/9/3255)).
- **Protein in a deficit: 1.8–2.4 g/kg BW/day (floor 1.6 at maintenance), computed conservatively as 2.0–3.1 g/kg FFM for lean athletes.** ISSN position: 1.4–2.0 g/kg/day maintenance ([Jäger 2017](https://link.springer.com/article/10.1186/s12970-017-0177-8)); Helms 2014: 2.3–3.1 g/kg FFM in energy-restricted resistance-trained athletes, scaled up with leanness and deficit severity ([PubMed 24092765](https://pubmed.ncbi.nlm.nih.gov/24092765/)); Burke/IAAF 2019: >1.6 and up to ~2.4 g/kg BW/day for "high-quality" weight loss.
- **Carbs scale with training volume, not with calories:** 3–5 g/kg/day light training → 5–7 moderate (1 h/day) → 6–10 heavy endurance (~1–3 h/day) → 8–12 extreme (>4–5 h/day). In a deficit, protect carbs around sessions and take the remaining deficit from fat, with fat floored at 20% of energy and ≥1 g/kg being comfortable but the hard floor 0.5–0.8 g/kg (ACSM/AND/DC joint position stand 2016, [PDF](https://femaleandmaleathletetriad.org/wp-content/uploads/2020/10/Nutrition_and_Athletic_Performance.27.pdf); [ISSN Kerksick 2017](https://pmc.ncbi.nlm.nih.gov/articles/PMC5596471/)).
- **Absolute calorie floors:** intake ≥ max(RMR, 1,200 kcal (women) / 1,500 kcal (men)) and ≥30 kcal/kg FFM + EEE on any day. The engine must clamp, warn, or refuse — never emit a plan below these.

## Methodology & sources

**Position stands & consensus statements (primary):**
- IOC consensus statement on Relative Energy Deficiency in Sport (RED-S), 2018 — EA definition, 45 kcal/kg FFM/day optimal, 30 floor even while cutting ([PDF](https://stillmed.olympics.com/media/Documents/Athletes/Medical-Scientific/Consensus-Statements/REDs/IOC-consensus-statement-Relative-Energy-Deficiency-in-Sport-2018.pdf); journal version [BJSM 52:687](https://bjsm.bmj.com/content/52/11/687)).
- IOC 2023 REDs consensus update (BJSM 57:1073) — refines EA risk categorization; keeps 45/30 thresholds as the practical anchors.
- Joint Position Statement: Academy of Nutrition and Dietetics, Dietitians of Canada, ACSM — "Nutrition and Athletic Performance" (Thomas 2016, Med Sci Sports Exerc) — CHO 3–10 g/kg/day (up to 12 for extreme durations), fat 20–35% of energy, protein 1.2–2.0 g/kg/day. [PDF](https://femaleandmaleathletetriad.org/wp-content/uploads/2020/10/Nutrition_and_Athletic_Performance.27.pdf)
- ISSN position stands: protein & exercise ([Jäger 2017](https://pmc.ncbi.nlm.nih.gov/articles/PMC2117006/)), nutrient timing ([Kerksick 2017](https://pmc.ncbi.nlm.nih.gov/articles/PMC5596471/)), diets & body composition ([Aragon 2017](https://link.springer.com/article/10.1186/s12970-017-0174-y)).
- IAAF/World Athletics consensus on Nutrition for Athletics (Burke 2019, IJSNE) — deficit-phase guidance: >1.6 up to 2.4 g/kg BW/day protein, slow cut off-season/early season. ([Journal page](https://journals.humankinetics.com/view/journals/ijsnem/29/2/article-p73.xml))

**Peer-reviewed validation & reviews:**
- BMR equations: [Frankenfield 2005, J Am Diet Assoc](https://pubmed.ncbi.nlm.nih.gov/15883556/) (Mifflin-St Jeor most reliable ±10%); [O'Neill 2023, PMC10687135](https://pmc.ncbi.nlm.nih.gov/articles/PMC10687135/) (equation accuracy in athletes).
- Protein during caloric restriction: [Helms 2014 systematic review](https://pubmed.ncbi.nlm.nih.gov/24092765/) (2.3–3.1 g/kg FFM); [Hector & Phillips 2018, IJSNE](https://journals.humankinetics.com/view/journals/ijsnem/28/2/article-p170.xml) (1.8–2.7 g/kg BW in deficit).
- Weight-loss rate: [Garthe 2011 RCT](https://pubmed.ncbi.nlm.nih.gov/21558571/) (0.7% vs 1.4%/wk); [Ruiz-Castellano 2021](https://www.mdpi.com/2072-6643/13/9/3255) (0.5–1.0%/wk target).
- LEA/RED-S physiology: [Cabre 2022, Dtsch Z Sportmed / PMC9724109](https://pmc.ncbi.nlm.nih.gov/articles/PMC9724109/) (LEA <30 F/<25 M; 5-day onset; EA ≥45 "optimal").

**Gaps / unverified:**
- The 1,200/1,500 kcal floors are convention-anchored (AHA/ACC/TOS obesity-guideline practice; Dietary Guidelines context) rather than a single canonical citation — treat them as conservative legal/UX floors, with the EA- and RMR-derived floors doing the real physiological work.
- Male LEA thresholds (<25) rest on very few studies (explicitly flagged in Cabre 2022); code should treat 30 kcal/kg FFM as the male floor too.
- The exact 2023 IOC graded-EA table was not reachable from this environment (BMJ 403); the 2018 statement's values are used as canonical constants.

## Part 1 — Energy expenditure pipeline

### 1.1 BMR / resting metabolic rate (RMR)

Two equations, selected by data availability (both produce kcal/day):

```
// Mifflin-St Jeor (default — no body-comp data)
BMR = 10·W + 6.25·H − 5·A + (5 if male else −161)
  W = weight kg, H = height cm, A = age years

// Katch-McArdle (default — user has measured body-fat %)
BMR = 370 + 21.6·FFM      FFM = W·(1 − BF%)
```

Selection rules for the engine:
- `bfPct` present **and** within a plausible gate (men 3–40%, women 8–48%; reject outside — garbage-in protection) → Katch-McArdle.
- Otherwise → Mifflin-St Jeor.
- Accuracy envelope to surface in UI: ±10% of measured RMR for ~most healthy adults (Mifflin-St Jeor); single-equation error is why **plans must be correctable by observed weight trend** (see 1.4 feedback loop) rather than treated as truth.

### 1.2 Activity layering (avoid the double-count)

The app knows training; use textbook multipliers only for the **non-exercise** remainder:

```
PAL_base (non-exercise, chosen from user's job/lifestyle):
  1.2  desk/sedentary
  1.35 light (some standing/walking, ~2k–6k steps)
  1.5  active lifestyle (physical job, >8k–10k steps)

EEE per session, from device data:
  cycling with power:  kcal = avgWatts(h)·3600 / 1000 / 4.184 · efficiency
    (use gross efficiency 1.0 i.e. joules→kcal directly, or 0.9 for net-of-baseline)
  running:              kcal ≈ MET(1.0)·W·km   (~1.0–1.05 kcal/kg/km on flat)
  other:                kcal = MET·W·hours·1.0 (Compendium METs, Ainsworth 2011)

TDEE(day) = BMR · PAL_base + EEE(day)
```

Reference table for the classic *stacked* multipliers (only if a per-day EEE is unavailable, e.g. manual-only users): sedentary 1.2, light 1.375, moderate 1.55, very active 1.725, extreme 1.9. **The engine should prefer 1.2's path: multiply the base by PAL_base and add EEE — never multiply by both.**

### 1.3 Rest-day TDEE floor

`TDEE(rest day) = BMR · PAL_base` (no EEE). Deficits are sized against the **weekly average** of daily TDEE, not any single day.

### 1.4 Correction loop (determinism-friendly)

Prediction error is real (±10% BMR, worse for EEE in non-power sports). The engine should expose a calibration multiplier recomputed from weigh-ins:

```
error = (expected weekly change from intake vs measured 7-day rolling weight trend)
adaptFactor = clamp(0.9, 1/1.1, 1 + k·error / |planned rate|)   // e.g. k small, bounded
```
Rationale: standard practice in app engineering; keeps the engine deterministic while letting reality win. Bounds keep the correction from compounding bad input data.

## Part 2 — Energy availability gate (the hard safety floor)

```
EA = (EI − EEE) / FFM        [kcal per kg FFM per day]
```

Thresholds to enforce (IOC 2018 / Cabre 2022):

| EA (kcal/kg FFM/day) | Zone | Engine behavior |
|---|---|---|
| ≥ 45 | Optimal | green — all goal types allowed |
| 30–45 | Acceptable / subclinical risk | amber — allowed with warning; weight-loss rate cap shrinks (see Part 5) |
| 25–30 | Low | red — refuse weight-loss plans; warn on maintenance/surplus plans that land here |
| <30 (F) / <25 (M) | Clinical LEA | hard refuse for any plan that produces it |

Code rules:
1. Every emitted plan must satisfy `EI(day) ≥ 30·FFM + EEE(day)` for **all** days. This is the *binding* floor on deficit depth for lean, high-volume athletes — usually tighter than any calorie floor.
2. If no FFM is known, derive a standing FFM proxy: FFM ≈ W·(1 − BF_est) with BF_est from the engine's body-fat estimator, or fall back to `EA_gate = 0.85·W·30` (assume 15% BF) — conservative for most, and flagged for the user to add body-fat data.
3. EA is evaluated **per day** (acute harm onset can be days, not weeks) — but tolerance for single rest days with EEE=0 is high (EA rises mechanically).
4. A "recovery/fuel-up" mode (fixed `EI = 45·FFM + EEE`) is the natural remedy path the UI should offer when a plan violates the floor.

## Part 3 — Protein

```
protein_g/kg BW/day:
  maintenance or surplus:  1.6 (floor) … 2.0 (comfortable)          // ISSN 1.4–2.0; ~1.6 breakpoint (Morton 2018)
  deficit:                 1.8 … 2.4, scale by deficit severity      // Hector/Phillips 2018; Burke/IAAF 2019
  deficit, lean athlete (BF% ≤ 15 M / ≤ 23 F):  use FFM basis: 2.0 … 3.1 ·FFM   // Helms 2014
hard floor: 1.4 g/kg BW/day (never plan below this for an exercising user)
hard ceiling: 3.5 g/kg BW/day (no benefit beyond; guardrail, ISSN notes safety up to ~3 g/kg long-term)
```

Engine defaults:
- `deficit: 2.0 g/kg if deficit ≤ 20% of TDEE; 2.2 if 20–30%; 2.4 if >30% (capped by the 1.0%/wk rule, so >30% shouldn't occur for athletes)` — for lean athletes compute from FFM and take `min(g/kg-BW value, FFM-basis value)` sensibly (use FFM basis when BF data exists and athlete is lean).
- Distribute across ≥3 meals of 0.25–0.4 g/kg per feeding (ISSN timing position) — a scheduling constraint, not a math constraint, but worth carrying into the meal-slicer.

## Part 4 — Carbohydrate and fat distribution

### 4.1 Carb targets (g/kg BW/day, by daily training time — Thomas 2016 / Kerksick 2017 / Burke)

| Daily training | CHO (g/kg/day) |
|---|---|
| <1 h light / rest | 3–5 |
| ~1–3 h moderate, mixed intensity | 5–7 |
| ~1–3 h high intensity or 4 h moderate | 6–10 |
| >4–5 h extreme (stage racing, ultra) | 8–12 |

In a **deficit**: compute carbs from the training-load table *first*, protein from Part 3, and let **fat absorb the deficit**:

```
kcal_target = TDEE_week_avg · (1 − deficit_frac)
fat_kcal = kcal_target − protein_kcal − carb_kcal
fat_floor: fat_kcal ≥ max(0.20·kcal_target, 0.5·W·9)   // 20% of energy; ≥0.5 g/kg absolute
fat_ceiling for plan generation: ≤ 35% energy at maintenance/surplus
```

If the fat floor is violated after subtracting carbs+protein, **reduce the deficit** (or raise the target) until it fits — that's the "carbs and protein are protected" behavior the position stands imply. Never strip below 20% of energy from fat chronically (fat-soluble-vitamin and EFA adequacy).

### 4.2 Deficit vs maintenance vs surplus splits (practical defaults)

| Fuel state | Deficit frac | Typical macro ordering |
|---|---|---|
| **Deficit** (off-season / prep block) | sized for ≤1.0% BW/wk; ≤0.5% for lean athletes | protein 1.8–2.4 g/kg; carbs at training-load floor; fat rest, ≥20% energy |
| **Maintenance** | 0 | protein 1.6–2.0; carbs per load table; fat 20–35% |
| **Surplus** (base-building, lean-massing) | +300–1000 kcal/day (Delany 2025 review range) | carbs lead (top end of load table); protein 1.6–1.8; fat 20–30% |

Surplus guidance: keep +500–1,000 kcal/day as the working range for deliberate gain phases; beyond that, the marginal gain skews to fat mass and the engine should warn (Delany et al. 2025, [Sports Medicine](https://link.springer.com/article/10.1007/s40279-025-02285-4)).

## Part 5 — Weight-loss rate bounds (the deficit sizer)

```
maxRate (fraction of BW/week):
  0.5%      if BF% ≤ 15 (M) / ≤ 23 (F)  or in-season or EA < 45   ← recommended target, "quality" cut
  0.5–1.0%  general athlete range                                             ← enforced max: 1.0
  >1.0%     never planned; warn if user-configured above maxRate
absolute hard ceiling: 1.5% BW/week (NATA 2025; observed strength/lean-mass costs ≥1.4 — Garthe 2011)
```

Then:

```
deficit_kcal_per_day = (rate_frac · BW · 7700) / 7 · 0.75
   7700 kcal ≈ 1 kg body mass (varies 7100–8000 by tissue mix)
   0.75 = safety coefficient so realized loss does not run faster than planned
      (empirical adherence/adaptive-thermogenesis buffer; 0.7–0.8 common in practice)
clamp: EI = TDEE_week_avg − deficit_kcal_per_day, subject to
   ≥ max(30·FFM + EEE, BMR, 1200(F)/1500(M))          // EA, metabolic, convention floors
recompute realized EA and re-check Part 2 after clamping.
```

Weight-loss timing rule carried from the goal-compatibility research (#708): composition work belongs in preparatory/off-season blocks; the engine should refuse to *start* a cut inside ~4 weeks of a priority event. The floors above hold regardless of timing.

## Part 6 — Consolidated constants (code-enforceable)

| Constant | Value | Source anchor |
|---|---|---|
| BMR default (no BF data) | Mifflin-St Jeor | Frankenfield 2005 |
| BMR default (BF data) | Katch-McArdle 370 + 21.6·FFM | standard; validated in lean/muscular |
| PAL_base (non-exercise) | 1.2 / 1.35 / 1.5 | multi-class convention; EEE added separately |
| kcal ↔ kJ (cycling from power) | ÷ 4.184 (or net ⅔–0.9 by choice, documented) | energy-notation standard |
| EA green | ≥ 45 kcal/kg FFM/day | IOC 2018 |
| EA amber | 30–45 | IOC 2018; Cabre 2022 |
| EA floor (any plan, any day) | 30 (both sexes; 25 male clinical ref) | IOC 2018 / Cabre 2022 |
| Protein floor (maint) | 1.6 g/kg BW/day | Morton 2018 breakpoint; ISSN 1.4–2.0 |
| Protein in deficit | 1.8–2.4 g/kg BW; 2.0–3.1 g/kg FFM lean | Helms 2014; Hector 2018; Burke 2019 |
| Protein hard ceiling | 3.5 g/kg BW/day | guardrail |
| Fat floor | max(20% of energy, 0.5 g/kg) | Thomas 2016 (20–35%) |
| Fat comfort ceiling | 35% of energy | Thomas 2016 |
| CHO by load | 3–5 / 5–7 / 6–10 / 8–12 g/kg | Thomas 2016; ISSN Kerksick 2017 |
| Max weekly loss (target) | 0.5% BW | Garthe 2011; Ruiz-Castellano 2021 |
| Max weekly loss (hard) | 1.0% (configurable warn to 1.5%) | Garthe 2011; NATA 2025 ≤~1.5% |
| Deficit coefficient | 0.75 of gross kcal deficit | practice convention (bounded) |
| Calorie floors | ≥ BMR and ≥ 1,200 F / 1,500 M | AHA/ACC/TOS-line convention; EA floor usually tighter |
| kcal per kg body mass | 7,700 | standard energy-equivalent figure |
| Carbs lead deficit sizing | protein & CHO set first, fat absorbs deficit | Thomas 2016 ordering logic |

## Appendix — Ready-to-implement formula set

```python
# Deterministic nutrition engine: core formulas and enforced bounds.
# All energies kcal; masses kg. Constants sourced per Part 6.

CAL_PER_KG_BW = 7700.0
DEFICIT_COEFF = 0.75          # realized-loss safety coefficient
EA_GREEN, EA_AMBER, EA_FLOOR = 45.0, 30.0, 30.0
EA_FLOOR_MALE_TIGHT = 25.0    # clinical reference; enforce 30 for both sexes
WEEKLY_RATE_TARGET, WEEKLY_RATE_MAX, WEEKLY_RATE_HARD = 0.005, 0.010, 0.015

def bmr(weight, height_cm, age, is_male, bf_pct=None):
    """Katch-McArdle when measured body fat is usable, else Mifflin-St Jeor."""
    if bf_pct is not None and _plausible_bf(bf_pct, is_male):          # men 3–40, women 8–48
        return 370.0 + 21.6 * weight * (1.0 - bf_pct / 100.0)          # Katch-McArdle
    return (10.0 * weight + 6.25 * height_cm - 5.0 * age
            + (5.0 if is_male else -161.0))                            # Mifflin-St Jeor

def tdee_day(bmr_kcal, pal_base, eee_kcal=0.0):
    """Non-exercise PAL (1.2 desk / 1.35 light / 1.5 active) + explicit EEE.
    Never stack textbook multipliers on top of EEE (double-counts)."""
    return bmr_kcal * pal_base + eee_kcal

def energy_availability(ei, eee, ffm):
    return (ei - eee) / ffm                                            # kcal/kg FFM/day

def max_weekly_loss_rate(bf_pct, is_male, in_season):
    lean = (bf_pct is not None and bf_pct <= (15.0 if is_male else 23.0))
    return WEEKLY_RATE_TARGET if (lean or in_season) else WEEKLY_RATE_MAX

def deficit_daily(rate_frac, weight):
    return DEFICIT_COEFF * rate_frac * weight * CAL_PER_KG_BW / 7.0

def calorie_floor(bmr_kcal, is_male, ffm, eee_kcal, bf_pct=None):
    """Hard minimum EI for a day: EA floor and metabolic floor, whichever binds."""
    proxy_ffm = ffm if ffm is not None else weight_ffm_proxy(bf_pct)   # fallback engine-derived FFM
    ea_floor_energy = EA_FLOOR * proxy_ffm + eee_kcal
    convention_floor = 1200.0 if not is_male else 1500.0
    return max(bmr_kcal, ea_floor_energy, convention_floor)

def plan(ee_week_avg, bmr_kcal, is_male, weight, ffm=None, bf_pct=None,
         in_season=False, surplus=False):
    """Top-level deterministic target for one plan block."""
    if surplus:
        return {"target": ee_week_avg + (500.0 if ffm is None else 500.0),
                "surplus_gte": 300.0, "surplus_lte": 1000.0, "mode": "surplus"}
    if in_season:
        return {"target": ee_week_avg, "mode": "maintenance"}
    rate = max_weekly_loss_rate(bf_pct, is_male, in_season)
    target = ee_week_avg - deficit_daily(rate, weight)
    floor = calorie_floor(bmr_kcal, is_male, ffm, 0.0, bf_pct)         # EEE added per-day downstream
    target = max(target, floor)                                        # EA/metabolic/convention clamp
    # re-check EA after clamping; if EA < 30·FFM, raise target until satisfied (fuel-up mode)
    ffm_eff = ffm if ffm is not None else weight_ffm_proxy(bf_pct)
    if energy_availability(target, 0.0, ffm_eff) < EA_FLOOR:
        target = EA_FLOOR * ffm_eff                                   # refuse the cut, fuel up instead
    return {"target": target, "rate": rate, "mode": "deficit"}

def macros(target_kcal, weight, ffm=None, bf_pct=None, is_male=True,
           training_hours_day=1.0, in_deficit=False):
    """Protein and carbs are protected; fat fills the remainder, floor max(20% energy, 0.5 g/kg)."""
    # 1) protein
    if ffm is not None and bf_pct is not None and bf_pct <= (15.0 if is_male else 23.0):
        protein_g = (2.0 if not in_deficit else 2.6) * ffm            # Helms 2014 lean-basis
    else:
        protein_g = (1.7 if not in_deficit else 2.1) * weight         # deficit 1.8–2.4 by severity
    protein_g = min(protein_g, 3.5 * weight)                          # hard ceiling
    # 2) carbs from training load (Thomas 2016 / Kerksick 2017)
    if training_hours_day < 0.2: carb_gpk = 3.0
    elif training_hours_day < 1.5: carb_gpk = 6.0
    elif training_hours_day < 3.5: carb_gpk = 8.0
    else: carb_gpk = 10.0
    if not in_deficit and training_hours_day >= 1.5:
        carb_gpk += 1.0 if training_hours_day >= 3.5 else 2.0
    carb_g = min(carb_gpk, 12.0) * weight
    # 3) fat absorbs the remainder; floor binds → shrink deficit, don't strip fat
    fat_kcal = target_kcal - 4.0 * protein_g - 4.0 * carb_g
    fat_floor_kcal = max(0.20 * target_kcal, 0.5 * weight * 9.0)
    if fat_kcal < fat_floor_kcal:
        fat_kcal = fat_floor_kcal                                     # caller must re-inflate target_kcal
    return {"protein_g": protein_g, "carb_g": carb_g, "fat_g": fat_kcal / 9.0}

def weight_ffm_proxy(bf_pct):
    """Fallback when no FFM: use supplied BF% or a mid-range assumption (flag for user input)."""
    bf = bf_pct if bf_pct is not None else 18.0
    return weight * (1.0 - bf / 100.0)   # needs `weight` as arg in real implementation
```

**Enforcement matrix for the code:**

| Check | Rule | On violation |
|---|---|---|
| EA floor | `EI ≥ 30·FFM + EEE` each day | raise target (fuel-up) or refuse plan |
| Rate cap | `rate ≤ 1.0% BW/wk` (warn ≤1.5% if user-set) | clamp rate first, then re-derive deficit |
| Protein floor | `≥ 1.4 g/kg BW` (maint 1.6) | raise protein, push deficit down if fat floor collides |
| Fat floor | `≥ max(20% energy, 0.5 g/kg)` | reduce deficit depth |
| Carb sanity | `≤ 12 g/kg`, `≥ 3 g/kg` while training | clamp |
| Calorie floor | `≥ max(BMR, 1200/1500, EA-derived)` | clamp + warn |
| BF plausibility gate | 3–40% M, 8–48% F | ignore BF data, use Mifflin-St Jeor |