# Photo-nutrition accuracy: item identification, portion estimation, food-DB cross-check, correction UI

Research ticket: [tomberch/training-dash#710](https://github.com/tomberch/training-dash) · Part of map #706 · Date: 2026-09-30

Builds directly on `docs/research/ollama-cloud-model-audit.md` (#707), which established the key prior: **VLM portion estimates are ±20–50%, so kcal/macros must be computed deterministically in app code from a food DB — never taken from the VLM's own calorie numbers.** This ticket verifies that prior against the literature and answers the remaining design questions.

---

## 1. How accurate are multimodal LLMs on meal photos?

### 1.1 Item *identification* — surprisingly good

- **ChatGPT-4 on 114 meal photos** (547 food items, national-survey meals): precision **93.0%**, recall **84.6%**, F1 **88.6%** for identifying foods. The misses clustered in mixed dishes (false negatives — items it failed to see at all). *Source: "An Evaluation of ChatGPT for Nutrient Content Estimation from Meal Photographs", 2025.*
- **GPT-4V zero-shot on challenging/fine-tune-free conditions**: food detection accuracy up to **87.5%**, including non-Western cuisines when given a cuisine-hinting prompt. *Source: arXiv 2312.08592 (Dietary Assessment with Multimodal ChatGPT, 2023).*
- Commercial tracker dish-recognition rates cluster around **74–84%** (see §4 reliability caveat) — general-purpose VLMs in papers actually test *better* than most shipping apps because apps constrain themselves to dish-level labels.
- Specialized food-CV pipelines (segmentation → classification, non-LLM) report 86–99.85% detection accuracy across the review literature, but only on curated datasets; real-world generalization was the historic weakness that multimodal LLMs largely fixed.

**Expected MVP band: 80–90% per-item identification precision on common, visually distinct foods; recall is the weaker number (~85%) — things the VLM never mentions are the dominant failure, not wrong labels.**

### 1.2 Portion/mass estimation — the actual weak link

- **Gothenburg validation (52 photos, weighed reference, GPT-4o / Claude 3.5 / Gemini 1.5)**: MAPE **36.3–37.3%** (weight) and **35.8%** (energy) for GPT-4o/Claude; Gemini 64–110%. All models showed **systematic underestimation that grew with portion size** (bias slopes −0.23 to −0.50). Notably, MAPE ≈ 36% is comparable to traditional self-reported dietary assessment validated against doubly-labeled water (26.5% ± 16.8%) — i.e., photo-AI is roughly as good as asking a human to remember, not better. *Source: PMC12513282, 2025.*
- **Zero-shot on Nutrition5k**: GPT-4V MAPE **~55%**, GPT-4o **~47%** for single-dish calorie estimation; fine-tuning on food data gets specialized models down to MAPE ~26–40%. *Source: Reasoning-Driven Food Energy Estimation via MLLMs, PMC11990770.*
- **Small vs. large portions asymmetry**: ChatGPT estimates meal weight well for *small* meals but poorly for medium/large (p < 0.001) — it regresses toward recommended serving sizes from food-based dietary guidelines, which are systematically smaller than real portions. Cereals recommended 18–60 g vs. observed 30–70 g; potatoes 50–250 g vs. 180–360 g. So the model is "well-calibrated to what the internet says a serving is." *Source: ChatGPT meal-photo evaluation, 2025.*
- **Without a scale reference, mass estimation from a single 2D image is fundamentally underdetermined**: camera distance, angle (bird's-eye vs. 30° can halve apparent size), and loss of depth all distort. Reference-object anchoring (cutlery, plate, coin) and explicit prompts to use background objects are the known mitigations. Dedicated volume-estimator injection improves GPT-4o MAPE only marginally (~47 → 43%). *Sources: JMIR scoping review 2024; CalorieVoL (2024).*
- Human visual estimation of portions (MAE ~44 g) only slightly beats GPT-4V (~55 g) — the ceiling for photo-only is low for everyone. *Source: arXiv 2312.08592.*
- Portion-specific error across purpose-built food-CV models ranges **1.1% to 85%** depending on food type. *Source: review cited in the 2025 ChatGPT evaluation.*

**Expected MVP band: portion-weight MAPE 30–50% from a single photo; kcal MAPE 25–40% (errors partially cancel across items); consistent underestimation bias at large portions. This confirms #707's ±20–50% — treat VLM portions as a starting estimate for user correction, not a measurement.**

### 1.3 Where VLMs systematically fail

1. **Hidden/invisible calories** — the single dominant error driver: oils and fats used in cooking, dressings, sauces, butter, cheese melted into dishes, nuts under leaves. SnapCalorie's own peer-reviewed framing: user corrections drop error roughly from ±80 kcal to ±30 kcal largely by adding invisible items. Multiple reviews name oil/sauce misestimation as the top failure category. Nothing image-based can fix this; only user confirmation can.
2. **Mixed dishes** — stews, curries, casseroles, stir-fries, composite salads. The 2025 mixed-dish error decomposition (Dietary Assessment Initiative) finds mixed-dish MAPE typically **1.5–3× single-item MAPE** in the same study (in two studies: >40% vs. <15%); worst offenders are bowls/salads (±27% vs. ±13% for single foods in one app validation). Error sources inside mixed dishes: wrong ingredient (6–14% of MAPE), **wrong ingredient proportion (8–22%, the largest slice)**, wrong total volume (5–17%).
3. **Portion depth/size** — a slice of bread or steak cut reads identically from one angle; bowls defeat volume-from-top-view; bird's-eye photos kill depth. Systematic underestimation worsens with portion size.
4. **Portion-size prior contamination** — LLMs anchor on guideline-recommended serving sizes, biasing estimates down for large eaters (an athlete-eating user is exactly the worst case; TrainingDash's coach users will be heavier eaters, so expect the underestimation bias to bite).
5. **Wrong variant selection** — "fried rice" vs. "white rice", "noodle soup" vs. "ramen", mashed cauliflower vs. potato under bad lighting; prep method is rarely visible.
6. **Beverages** — opaque containers, blended contents; almost every mobile pipeline fails here.
7. **Restaurant/regional foods** — dish names ambiguous, chains handled well only when matched to published nutrition data.
8. **Cuisine out-of-distribution** — models recognize rice/bread but miss regional staples until prompted with a cuisine hint (GPT-4V: banku/ugali only after "African cuisine" prompt).

### 1.4 What demonstrably improves accuracy

- **Providing context text with the photo**: ChatGPT-5 across 195 dishes — MAE falls monotonically from image-only → image + non-visual descriptors → image + ingredient list with amounts (e.g., Allrecipes subset: 128 → 96 kcal MAE); dropping the image but keeping ingredients made it worse than Case 3, proving visual cues add real signal beyond arithmetic. *Source: Nutrients 17(22):3613, 2025.* → **A quick clarification prompt ("any oil/butter? what dressing?") before final compute is high-value, cheap, and fits the existing low-confidence-follow-up design.**
- **Prompted portion anchors**: standard plate 25–28 cm, cupped hand 80–120 g dense food, bowl 150–200 g cooked rice, restaurant = 1.5–2× home portion. *Source: Omnio pipeline write-up (industry, unreviewed — use as prompt-engineering guidance only).*
- **Conservative prompting**: better to under- and ask user to adjust up; users spot under-estimates more easily.
- **Asking for household units, not grams**: matches the deterministic density × volume computation downstream and plays to how food DBs index portions.
- **Before/after plate photos** (plate-waste) — improves intake estimation but adds UX burden; post-MVP.
- **Fine-tuning / volume-estimator modules** — gains exist (MAPE ~55 → ~26 best case, Nutrition5k) but are out of reach on Ollama Cloud (no fine-tuning); note as "not available in our stack."

---

## 2. Does food-DB cross-check materially improve accuracy?

**Yes — for identification errors and packaged/branded foods; it does nothing for portion error.**

The pipeline's two error families are separable:

| Error family | Food-DB helps? | Mechanism |
|---|---|---|
| Wrong/missed item identity | Partially | DB matching surfaces "no good match" → confidence signal + prompt for clarification; packaging text/brand resolves variant ambiguity |
| Portion/weight error | **No** | DB is per-100g composition; garbage gram-estimates in → garbage kcal out |
| Packaged/branded food values | **Decisively** | Label data beats any model guess; barcode is near-perfect |
| Common raw/simple foods | Yes (moderately) | FNDDS/USDA per-100g > VLM's internal nutrition priors, removes hallucinated micronutrients |
| Hidden ingredients (oil/sauce) | No | Nothing sees them; user confirmation only |

Key evidence and patterns:

- **Deterministic computation is already the norm**: macroscanner (open-source) runs GPT-4o for items+quantities, then searches a vectorized USDA FDC copy per item; the Omnio pattern searches USDA per item, and when the VLM's kcal/100g deviates >25% from the DB value, it **replaces the LLM macros with the DB-scaled values** and tags provenance (`usda_verified` / `off_matched` / `llm_only`).
- **Item→DB matching is a solved-enough retrieval problem**: the best published strategy is **semantic-embedding retrieval of top-K candidates + LLM rerank**, reaching **90.7%** exact-match accuracy on a large food DB (ASA24→FooDB, K=5 gives 85%, K=10 gives 95%); simple fuzzy matching and raw-LLM-over-the-whole-DB are both worse. *Source: Evaluation of LLMs for Mapping Dietary Data to Food Databases, 2026.* For our scale (per-meal, ≤5 items), "embed VLM item name → top-5 FNDDS/USDA candidates → LLM picks or 'none'" is cheap and robust.
- **Packaging text and brand matter**: VLMs read brand text on packaging reliably in practice; the LLM-maintained-brand-DB literature (npj Food, 2026) shows LLM mapping of ingredient/brand statements to reference DBs at 84–93% exact match. Practically for us: if the photo shows a package, prompt the VLM to also return **brand + product name + any visible barcode**, then resolve via OFF barcode endpoint → USDA branded (GTIN) → fuzzy fallback.
- **Recipe/menu matching** (restaurant chains) materially reduces error but coverage is limited to chains — post-MVP.

**Caveat**: cross-check cannot fix the dominant error (portions, hidden ingredients). The literature's own conclusion is that **user-confirmed ingredient lists hybridized with image input consistently perform best** — the correction UI is not a nice-to-have, it is the main accuracy mechanism.

---

## 3. Architecture verdict: identify-then-compute vs. pipeline vs. single-call

Options for MVP:

| Alternative | Description | Assessment |
|---|---|---|
| A. Single-call VLM | One call returns kcal/macros directly | **Rejected.** GPT-4(V/o) zero-shot kcal MAPE 36–56% *and* it's the only mode where model hallucination directly corrupts stored numbers. Also forfeits editability — the user can't correct what's already merged into a number. |
| B. Two-call pipeline (identify → per-item DB lookup → compute) | VLM returns items + household portions + confidence; app code does retrieval + arithmetic | This is what #707 already prescribed; literature (macroscanner, Omnio, SnapCalorie's USDA-grounded DB) validates it. Downside: two round-trips. |
| C. Single-call identify + in-app compute | **Same VLM call returns photo-only vision data (items, household-unit portions, confidence, packaging text/brand/barcode hints)** — no second LLM call; DB retrieval and kcal/macro arithmetic happen deterministically in app code | Recommended. On Ollama Cloud, prompt-anchored JSON + Zod validation handles the schema (tool-calling is the fallback for validation-retry loops). One VLM call per meal is the cost/latency budget; everything after is free |
| D. Depth/3D/volume-model pipeline | Segmentation + depth map + density | Explicitly out: Ollama Cloud offers no such models; error compounds across pipeline stages; marginal gains (43 vs 47% MAPE) don't justify it |

**Verdict: identify-then-compute in a single VLM call (option C), with deterministic per-100g × portion arithmetic in app code.** This is the #707 recommendation confirmed by the 2024–2026 literature. Concretely per meal:

1. VLM (glm-5.3-flash) → JSON: `items[{name, household_qty, unit, confidence, is_packaged, brand_text?, barcode_visible?}], cuisine_hint, scene_quality_flags`
2. For each item, app code: packaged → OFF barcode/brand search; else embedding top-K → FNDDS/USDA → LLM-free pick-or-none (or cheap rerank); unmatched → `llm_only` estimate from VLM's generic food knowledge, tagged as such. Compute grams = household qty × DB household-unit gram weight (FNDDS ships portion weights; OFF/USDA per-100g + serving sizes).
3. kcal/macros = Σ per-100g × grams/100, in code, plus a ±% band shown to the user.
4. Provenance tag per item (`barcode`, `fndds`, `usda_branded`, `generic_db`, `llm_only`) stored so later analytics can weight trust.
5. Low overall confidence or >1 unmatched item → one clarifying follow-up question (oil? dressing? seconds?) then recompute — the ChatGPT-5 study shows text context yields the largest accuracy jumps available.

---

## 4. Correction UI patterns from shipping photo-food apps

*(Reliability note: peer-reviewed evidence on app UIs is thin; patterns below are from app documentation and reviews, which are promotional-grade sources — treat as design inventory, not accuracy claims. In particular, the "DAI Six-App Validation" MAPE figures for Cal AI ±14.6% / SnapCalorie ±19.8% / "PlateLens ±1.2%" circulating on 2026 review sites are not traceable to a peer-reviewed study and look like SEO content; do not cite them as ground truth.)*

| Pattern | Who uses it | MVP? |
|---|---|---|
| **Per-item list with tap-to-edit** after photo: item card shows label, portion, kcal/macros; tap any card to change label, add a missed item, or delete a false positive | SnapCalorie, Cal AI (one-tap manual override), Foodnoms | **Yes — core** |
| **Portion adjustment control** — slider (household units + grams) rather than free-text; updates totals live | SnapCalorie, Cal AI | **Yes** |
| **Confidence display / uncertainty band** — show estimate as a range, or gray-out low-confidence items pending confirmation | Only "PlateLens" exposes CIs per reviews; most apps don't | **Yes, cheap**: show per-item confidence + total as a band; gray <0.7-confidence items |
| **"Add invisible item" nudges** — prompts like "add dressing?" when a salad looks bare; menu of common add-ons (oil, dressing, cheese, sauce) one tap each | SnapCalorie | **Yes** — directly attacks the dominant error |
| **Low-confidence gate** — ambiguous items don't silently enter the daily total; require confirm/edit | Omnio's stated pipeline design | **Yes — matches #706's low-confidence follow-up** |
| **Photo timeline diary** with thumbnails for re-editing past meals | SnapCalorie 2025 redesign | Later (weight log + meals day view suffices for MVP) |
| **Barcode / label-scan as parallel input** | All trackers; barcode match is the highest-precision path | **Yes for packaged** (PWA: camera + off-the-shelf JS barcode lib, e.g. ZXing/@zxing/library) — cheap, high-value |
| **Quick-add common meals / saved meals + per-user correction learning** | SnapCalorie (claims ±80→±30 kcal after ~10 corrections), MFP | Later — needs correction data accumulation; log corrections from day one (same structured-logging principle as the adaptation loop) |
| **Chain-restaurant DB matching** | Cal AI (MFP 380+ chains) | Later; MVP = search-based manual entry for restaurants |

**MVP vs. later split**: MVP correction UI = per-item cards + portion slider + add-missing-item (with an oil/dressing shortcut) + delete/false-positive + confidence display + barcode scan for packaged items + "confirm or edit" before the meal commits. Later: correction-learning, timeline diary, chain matching, multi-photo (before/after) capture.

---

## 5. Food-DB recommendation

| Criterion | **USDA FDC** | **Open Food Facts** |
|---|---|---|
| Content | Foundation, SR Legacy, **FNDDS** (survey foods w/ portion weights), Global Branded Foods | Crowd-sourced packaged products, keyed by barcode |
| Licensing | **Public domain / CC0** — zero friction | **ODbL + share-alike**: derivable DBs must be attributed and redistributed open; keep OFF-derived rows in a separate provenance-tagged table if other data is combined |
| API cost | Free, key required, **1,000 req/hr/IP** | Free, **15 req/min reads / 10 req/min search per IP** — tight; bulk JSONL export or self-host for anything beyond low volume |
| Barcode | Branded Foods subset supports GTIN/UPC search | **Primary key is barcode — best-in-class** |
| Fit | **Core engine for generic/common foods + household portion weights (FNDDS)** | **Barcode resolution + brand matching for packaged items** |
| Coverage gaps | Packaged/international products thinner than MFP's crowdsourced DB; no per-serving API — per-serving math is on us (documented) | Quality varies (crowd-sourced); macro fields sometimes incomplete — use for identity/barcode, spot-check macros |

**Recommendation: USDA FDC as the primary composition DB (CC0, generous rate limits, FNDDS gives the household-unit→grams mapping the pipeline needs), plus OFF for barcode-first packaged products with provenance separation.** Both free; expected app-level API cost ≈ $0. Keep OFF data in its own table/namespace to respect ODbL share-alike; attribution notice in app credits. If hosted-search rate limits ever bind (single-user PWA won't: one meal ≈ 2–5 lookups), bulk-load an FNDDS+branded subset into Postgres — repo already runs Postgres, so this is the natural fallback that also removes external latency. Commercial aggregator APIs (Edamam, Spoonacular, Nutritionix, FatSecret) buy text-parsing/recipe features we don't need for MVP — skip.

**Item-matching implementation**: (1) barcode if visible/scanned → OFF product endpoint first; (2) brand text from packaging → FDC Branded / GTIN; (3) generic name → embedding top-K (K=5) → deterministic pick or cheap LLM rerank (published top-5 accuracy ~85–96%) → fallback FNDDS "generic/not-specified" code — FNDDS explicitly maintains NFS codes whose composition reflects consumption-weighted averages, which is exactly the right soft landing for unmatched VLM items; (4) nothing matches → `llm_only` generic-food estimate, flagged.

---

## 6. Expected end-to-end accuracy budget for MVP

Composition of typical logged meals determines blended error more than any single number:

| Meal type | Expected kcal MAPE (with correction UI used) | Basis |
|---|---|---|
| Single/simple items (whole foods, standard portions) | **10–15%** | App-review anecdotes (~10–20% on easy foods); single-item AI literature |
| Packaged w/ barcode | **<10%** (portion is exact, label data) | Barcode-lookup precision |
| Home-cooked multi-component | **20–35%** | Portion-estimation band; correct with per-item edit |
| Mixed dishes / bowls / salads | **30–50%** pre-correction; **~20–30%** post per-item correction | Mixed-dish 1.5–3× single-item multiplier |
| Restaurant chains | **15–25%** via DB match; worse otherwise | Chain-matching evidence (post-MVP for us) |
| Anything with hidden oil/sauce uncorrected | +100–300 kcal systematic underestimate | Dominant error driver across all sources |

Blended realistic target for the MVP (photo → per-item confirm/edit → deterministic compute): **kcal MAPE ≈ 20–30% for a typical mixed diet**, aligning with self-report baselines (DLW-validated self-record: ~26.5%) while costing the user 5–15 seconds instead of minutes. That is the honest ceiling of photo-only estimation in 2026 — the app's value is consistency and adherence, and the correction UI + barcode path is what keeps it from being worse.

## 7. Bottom-line verdicts

1. **Identify-then-compute in one VLM call** (items + household portions + confidence + packaging text) with deterministic DB math in app code. Never store VLM kcal numbers. Confirms #707.
2. **Food-DB cross-check is MVP**: USDA FDC primary (CC0, 1000 req/hr, FNDDS portion weights) + OFF for barcodes (ODbL — keep provenance-separated). Both free.
3. **Correction UI is the main accuracy mechanism, not an afterthought**: per-item cards + portion slider + add-invisible-item nudge + confidence gating + barcode scan in MVP; correction-learning, timeline diary, chain matching later.
4. Mixed-dish and hidden-ingredient error cannot be solved by any image pipeline available on Ollama Cloud; design the error budget (±20–30% blended) into the nutrition engine's tolerance, and feed VLM item/portion JSON + corrections into structured logs from day one (keeps later improvement loops open, mirrors #709's approach).
5. Run the 50-photo eval set (already proposed in #707) to calibrate glm-5.3-flash's real per-item precision/portion error on our user's actual diet before trusting the blended numbers above.