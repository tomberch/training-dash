# Goal-compatibility semantics — research

> Purpose: feed the goal-model spec (child of #706, blocks #715). Which concurrent goal types are physiologically compatible, which are mutually exclusive or need sequencing, how real products structure goal blocks, and what adaptation cadence keeps noisy signals useful.
> Date: Sep 30 2026
> Ticket: tomberch/training-dash#708

## Summary

- **Most goal pairings are compatible; aggression is the axis that breaks them, not the pairing itself.** Moderate weight loss (~0.7% body weight/week) coexists with FTP gains — Garthe et al. found athletes losing 0.7%/wk *gained* lean mass and 1RM while dieting, while 1.4%/wk athletes stalled on both ([Garthe 2011](https://pubmed.ncbi.nlm.nih.gov/21558571)). So "FTP increase + body recomp" is compatible; "FTP increase + aggressive cut" is not.
- **Products structure "goals" as either (a) prioritized target events or (b) a single primary focus per plan block — never simultaneous competing objectives.** TrainerRoad's Plan Builder takes one either/or choice: A/B/C-priority events *or* a General Fitness Goal with a single primary discipline and focus ([Plan Builder Overview](https://support.trainerroad.com/hc/en-us/articles/29263741820955-Plan-Builder-Overview-for-Triathlon)); Wahoo SYSTM names one goal and derives a plan from a single 4DP rider profile ([Wahoo SYSTM](https://www.wahoofitness.com/systm)); TrainingPeaks' ATP forces exactly one priority level per event and requires ≥1 A race for auto-periodization ([ATP guide](https://www.trainingpeaks.com/learn/articles/the-comprehensive-guide-to-creating-an-annual-training-plan)). The consistent shape: **one primary goal at a time, other events/goals explicitly subordinated by priority, not negotiated per day.**
- **Timing rules matter more than simultaneous rules for body-composition goals.** Both NATA ([position statement](https://www.nata.org/sites/default/files/2025-08/safe_weight_loss_and_maintenance_practices_in_sport_and_exercise.pdf)) and the IOC RED-S consensus ([2018 update](https://bjsm.bmj.com/content/52/11/687)) place composition work in the preparatory/off-season period; no active cut during the 4–6 weeks before an A event or during peak competition. Energy availability must stay ≥ ~30 kcal/kg FFM/day **even when deliberately losing weight** (IOC; [RED-S review](https://pmc.ncbi.nlm.nih.gov/articles/PMC9724109/)).
- **Concurrent training interference is real but modest and mostly avoidable with scheduling**: separate same-day strength and endurance sessions by >3 h, put resistance *before* endurance when relative strength/explosive power is the target ([Feng 2026 semi-systematic review](https://www.frontiersin.org/journals/sports-and-active-living/articles/10.3389/fspor.2025.1692399/full); [2026 umbrella review](https://pubmed.ncbi.nlm.nih.gov/41762427) found no significant sequence effect but a trend favoring RT→ET for strength).
- **Adaptation cadence: evaluate on a 4-week loop, adjust at 1–2 week granularity, never daily.** TrainerRoad's own signal (AI FTP Detection + Fatigue Detection) runs on a 28-day simulation/detection window with continuous *projection* in between ([TrainerRoad AI](https://www.trainerroad.com/blog/introducing-trainerroad-ai)); Garthe-style weight loss is staged in weekly check-ins with body-comp measurement no more often than biweekly ([NATA](https://www.nata.org/sites/default/files/2025-08/safe_weight_loss_and_maintenance_practices_in_sport_and_exercise.pdf)); standard noise-smoothing practice is a 7-day window minimum for daily-varying signals (weight, CTL), with 4-week windows for performance metrics that need several hard sessions to manifest.

## Methodology & sources

**Primary sources (first-party product docs):**
- TrainerRoad support/blog — Plan Builder Overview (events & general-fitness goal selection), Season Planning Basics, AI FTP Detection blog posts (Jan–Jun 2026), FTP calculator page.
- TrainingPeaks — Comprehensive Guide to the Annual Training Plan (A/B/C priority, periodization methods), Help Center Events article, Prioritizing Cycling Races blog.
- Wahoo SYSTM — product page (4DP profile, rider types, "Name the goal. The plan writes itself"), 4DP Rider Type support article, Going Beyond Threshold Power blog.

**Peer-reviewed / position stands:**
- Murias/Wilson-style concurrent-training literature: Wilson 2012 meta-analysis ([PubMed 22002517](https://pubmed.ncbi.nlm.nih.gov/22002517)); Schumann 2024 Sports Medicine meta-analysis on sex & training status ([PMC10933151](https://pmc.ncbi.nlm.nih.gov/articles/PMC10933151/)); 2026 Frontiers semi-systematic review on sequence effects; 2026 Sports Medicine umbrella review of meta-analyses ([PubMed 41762427](https://pubmed.ncbi.nlm.nih.gov/41762427)).
- Energy availability: [IOC consensus statement on RED-S, 2018 update](https://bjsm.bmj.com/content/52/11/687) (BJSM); [Melin 2024, Scand J Med Sci Sports](https://onlinelibrary.wiley.com/doi/10.1111/sms.14327) (direct/indirect LEA performance effects; "moderate planned LEA can be OK"); [RED-S female-athlete narrative review](https://pmc.ncbi.nlm.nih.gov/articles/PMC9724109/) (EA ≥ 30 kcal/kg FFM/day floor even during deliberate loss).
- Weight-loss rate & timing: [NATA position statement on safe weight loss](https://www.nata.org/sites/default/files/2025-08/safe_weight_loss_and_maintenance_practices_in_sport_and_exercise.pdf) (≤1.5% BW/week; adjustments in the preparatory period); [Garthe 2011, IJSNE](https://pubmed.ncbi.nlm.nih.gov/21558571) (0.7%/wk vs 1.4%/wk RCT).

**Gaps / unverified:**
- Wahoo SYSTM's exact goal-picker UI (multi-goal vs single-goal) is inferred from marketing copy ("Name the goal. The plan writes itself") + the 4DP docs; the app is auth-gated, so the wizard's step list is **not verified** first-hand.
- Whether TrainerRoad allows *concurrent* general-fitness goals (e.g., FTP + weight) alongside events — the Plan Builder docs show a single primary focus choice; weight/body-composition is **absent from all three products' goal models** (none of them model a weight goal natively; athletes manage it externally). This is a genuine differentiator opportunity for TrainingDash.
- Xert not covered (unreachable from this environment historically; out of scope for this ticket).

## Part 1 — Goal taxonomy used throughout

To make the matrix concrete, define the goal types a training app will model:

| Type | Example | Primary adaptation lever | Signal used to track progress |
|---|---|---|---|
| **Event-peak** (A/B/C priority) | Peak for granfondo June 14 | Periodized load + taper | TSB at race day, B/C race form checks |
| **FTP/threshold power** | 20-min power +8% | Sustained threshold/SST volume | Power duration curve, threshold tests |
| **Aerobic base / VO₂max** | MAP +5%, Z2 efficiency | Volume at easy intensity | VO₂max est., MAP, aerobic decoupling |
| **Sprint/anaerobic capacity** | 1-min & 5-sec power | High-intensity short efforts | 4DP/ACP-type short-duration power |
| **Body recomp (moderate)** | −3% BW over 12 weeks | Modest deficit (~19% intake cut) + protein + strength | 7-day weight average, waist, power-per-kg |
| **Aggressive cut** | −5% BW before making weight | Large deficit (30%+ intake cut) | Daily weight, strict intake logging |
| **Strength gain** (gym) | Squat 1RM PR | Progressive resistance training | 1RM/tonnage |

## Part 2 — Compatibility matrix

Legend: ✅ compatible (co-schedule freely) · ⚠️ compatible-with-constraints (same block only with sizing/sequencing rules, see Part 3) · ❌ sequence required (do not run in the same training block) · ▲/▼ = the first goal is helped/hurt by the second.

|  | Event-peak | FTP ↑ | Aerobic base | Sprint/anaerobic | Recomp (moderate) | Aggressive cut | Strength |
|---|---|---|---|---|---|---|---|
| **Event-peak (A)** | — | ⚠️ | ⚠️ | ⚠️ | ⚠️ | ❌ | ⚠️ |
| **FTP ↑** | | — | ✅ | ⚠️ | ✅ | ❌ | ✅ |
| **Aerobic base** | | | — | ⚠️ | ✅ | ❌ | ✅ |
| **Sprint/anaerobic** | | | | — | ⚠️ | ❌ | ⚠️ |
| **Recomp (moderate)** | | | | | — | ❌ | ✅ |

Key readings from the evidence:

- **FTP ↑ + aggressive cut: ❌ — the canonical conflict the ticket names.** Mechanisms: (1) glycogen restriction prevents sustaining threshold-intensity quality work; (2) protein synthesis is energetically capped, so the hypertrophy/contractile-protein adaptation supporting threshold stalling ([IOC 2018](https://bjsm.bmj.com/content/52/11/687): ≥10% BW loss/month is itself an LEA red flag); (3) acute LEA raises injury & stagnates training response ([Melin 2024](https://onlinelibrary.wiley.com/doi/10.1111/sms.14327)). Product-echo: no mainstream tool lets you combine the two; NSCA explicitly says athletes *"should not pursue active weight loss"* in the competition cycle ([NSCA competition-cycle nutrition](https://www.nsca.com/education/articles/kinetic-select/nutrition-for-competition-cycle/)).
- **FTP ↑ + moderate recomp: ✅ with a constraint** — this is the power-to-weight sweet spot. Garthe's 0.7%/wk arm *increased* lean mass and 1RM during the diet; 33% cut studies still improved power-to-weight via efficiency ([Calorie restriction study 2018](https://www.tandfonline.com/doi/full/10.1186/s12970-018-0214-2)). Constraint: deficit ≤ ~500 kcal/day, protein 1.6–2.2 g/kg, strength sessions retained, EA floor ≥30 kcal/kg FFM/day respected.
- **FTP ↑ + aerobic base: ✅** — largely the same adaptations; volume is the shared resource, so the only conflict is *time budget*, which is a scheduling constraint not a physiological block.
- **Sprint/anaerobic + heavy endurance volume: ⚠️** — classic interference territory. Wilson 2012: interference tracks endurance *frequency × duration*, and running (but not cycling) hurt hypertrophy/strength ([Wilson 2012](https://pubmed.ncbi.nlm.nih.gov/22002517)). Compatible when endurance volume is modest and sprint work is placed fresh.
- **Event-peak + anything: ⚠️** — everything is subordinated by taper timing; a taper invalidates concurrent progression goals for its 1–3 week span. Body-composition changes are excluded outright near the event (composition shifts alter pacing/feel, and restriction kills the taper's purpose).
- **Recomp + aggressive cut: ❌** (not shown as a pair but implied by the ❌ column) — contradictory deficit sizes; only one energy-intake regime can be active at a time.

## Part 3 — Sequencing rules a spec can adopt

**R1 — One "primary" goal per training block; everything else is "supporting" or "parked."** Mirrors all three products. A block has exactly one goal with `mode: primary`; adding a second primary requires the UI to prompt re-periodization (TrainerRoad's Plan Builder literally makes events-vs-general-fitness an either/or at plan creation, then lets A-races be added later).

**R2 — Conflicting-pair guardrail.** When a user accepts a ❌ pairing, the app must (a) refuse to co-schedule them in the same block, and (b) offer sequencing: finish the cut first (off-season/preparatory), then start the FTP block. Minimum gap: 2 weeks at energy balance before the performance block begins (metabolic & glycogen restoration).

**R3 — Cut-velocity cap.** Body-composition goals constrained to ≤0.7% BW/week when a performance goal is co-active (Garthe). 1.0–1.4%/week allowed only in a dedicated no-performance-goal block. Hard ceiling: 1.5% BW/week (NATA). Floor: EA ≥30 kcal/kg FFM/day always.

**R4 — Taper exclusion window.** In the 2–3 weeks before an A event, all non-taper goals (recomp, strength PR, sprint gains) get auto-paused, not just deprioritized. Recomposition resumes after the event's recovery week.

**R5 — Session-order rule for co-scheduled strength + endurance.** If both land in one day: resistance first, or separate by >3 h ([Feng 2026](https://www.frontiersin.org/journals/sports-and-active-living/articles/10.3389/fspor.2025.1692399/full)). The app can encode this as a scheduling hint on the day view rather than a hard block.

**R6 — Cycling > running for interference protection.** Cued by Wilson 2012 (running, not cycling, caused significant decrements). When a strength/anaerobic goal co-exists with endurance volume, prefer cycling-based endurance in the same block.

**R7 — Priority fallback.** When training load unexpectedly rises (life stress, missed recovery), the app should auto-pause the *body-composition* goal first (raise intake to restore EA) before touching the performance goal — LEA degrades everything downstream but is the cheapest thing to reverse.

## Part 4 — Adaptation cadence (how often to re-evaluate & adjust)

Recommended: a **4-week evaluation loop with weekly adjustment checkpoints**:

| Cadence | What happens | Signal |
|---|---|---|
| **Continuous** | Plan *projection* updates (what-if simulation) as the athlete edits/completes workouts | TrainerRoad AI's "4 week Simulation Window" pattern ([blog](https://www.trainerroad.com/blog/introducing-trainerroad-ai)) |
| **Weekly** | Adjustment checkpoint: compare 7-day smoothed weight/load trend vs target; nudge intake or next week's volume. Consistent with NATA ("adjust calories at most every 7 days" guidance from sports-nutrition practice; measurement cadence ≤1/week for weigh-ins) | 7-day moving averages (weight, TSS, hrV) |
| **Biweekly** | Body-composition measurement (skinfold/tape) — too noisy at any shorter interval, per NATA practice & dotFIT-style guidance ("measurements taken biweekly") | Skin folds, waist circumference |
| **4-week** | Hard performance re-detection (FTP/ramp/4DP-style), fatigue state review, goal block re-planning. Matches TrainerRoad's 28-day AI FTP Detection window and the classic 3:1 block rhythm | Power duration curve, ramp/8-min test, TSB trend |

Why not shorter: single-session power outputs vary ±3–5% from fatigue/nutrition/weather; daily re-calibration would thrash zones on noise (TrainerRoad explicitly smooths its FTP jumps so interval watts don't see-saw when the detection updates — ["Why is AI FTP Detecting an FTP Change?" Jan 2026](https://www.trainerroad.com/blog/why-is-ai-ftp-detecting-an-ftp-change)). Why not longer: a monthly-only loop misses real stalls in both weight-loss and load ramping. The 4-week window is also the standard training-block quantum (TrainerRoad's "4 Weeks Per Block" plan naming; [all plans](https://www.trainerroad.com/all-cycling-training-plans)), so re-detection aligns with the natural block boundary rather than interrupting it.

Adoptable rule for the spec: **detect/re-detect on a 28-day cadence (or after a plan-breaking event: missed block ≥1 week, big race, illness); adjust nudges weekly; never adjust two variables in the same week** (single-change discipline keeps attribution clean when the signal is noisy).

## How the products structure it (per-product notes)

- **TrainerRoad**: either/or at plan creation — "To Prepare for an Event" (A/B/C priorities) or "General Fitness Goals" (choose plan length 1–3 months, choose primary discipline, choose primary goal). A events: full taper + recovery week, "ideally 12 weeks apart." B: mini-taper. C: no plan impact. ([Plan Builder Overview](https://support.trainerroad.com/hc/en-us/articles/29263741820955-Plan-Builder-Overview-for-Triathlon), [Season Planning Basics](https://www.trainerroad.com/blog/season-planning-basics))
- **TrainingPeaks**: ATP wizard with forced A/B/C per event; ≥1 A race required for auto-periodization; A races must be ≥32 weeks apart, ≤48 weeks from ATP start. "C" events don't affect ATP at all. Plus target CTL per A/B race as a *numeric season goal* alongside event goals. ([Comprehensive Guide](https://www.trainingpeaks.com/learn/articles/the-comprehensive-guide-to-creating-an-annual-training-plan), [Prioritizing](https://www.trainingpeaks.com/blog/prioritizing-cycling-races-for-peak-performance))
- **Wahoo SYSTM**: one "goal" → plan derived from athlete's 4DP profile (NM/AC/MAP/TP) and rider type (Sprinter/Attacker/Pursuiter/Time Trialist/Climber/Rouleur). Limiter-first framing: the system identifies your *weakest* dimension relative to your goal and builds toward it; 4DP shows the MAP-to-FTP relationship determines *which* training focus applies even at identical FTP. ([SYSTM](https://www.wahoofitness.com/systm), [4DP blog](https://www.wahoofitness.com/blog/going-beyond-threshold-power-the-systm-4dp-profile))
- **None of these three model a body-composition goal natively** — this is the open slot where TrainingDash can add value while carrying the physiological guardrails from Part 3.