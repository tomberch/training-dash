# Structured-output reliability for plan generation on Ollama Cloud

> Purpose: feed the plan-schema grilling ticket (#715). How reliably the shortlisted Ollama Cloud models (glm-5.3-flash default, deepseek-v4.1-flash off-peak, kimi-k3 escalation) emit large, schema-valid plan JSON **without native schema-constrained decoding**, and which prompting/repair patterns work. Closes #712 (research; parent #706, builds on #707's model audit).
> Date: Sep 30 2026
> Ticket: tomberch/training-dash#712
> Prior context: `docs/research/ollama-cloud-model-audit.md` (cloud `format` unsupported, tool calling supported)

## Summary (verdicts)

- **(a) `submit_plan` tool call: nudge, not enforcement — but a strong one for these models.** Ollama's tool-calling API has **no `strict: true` flag** (docs.ollama.com/capabilities/tool-calling — tool schemas are passed, never token-constrained), and cloud `format` is documented unsupported. So the tool schema is training-based adherence ("the model is fine-tuned to follow schemas as instructions"), not a hard guarantee. That is still the best available lever: adherence via tool schema in published evals is far better than prompt-only. GLM-5.3-Flash is independently benchmarked at the top of large tool catalogs (Toolathlon-Verified pass@1 **78.4%**, K3 76.5%, Claude Opus 4.8 76.2% — fleeceai.app/blog/best-llm-for-function-calling-tool-use-2026); K3, on Moonshot's own API, additionally ships a native strict `json_schema` response_format (platform.kimi.ai) which signals strong instruction-tuning for schema adherence. All three candidates have explicit tool-calling tracks in their training (GLM-5.3 repo: agentic focus; DeepSeek-V4.1 tool-call parsers; Kimi K3 native).
- **(b) Prompt-anchored JSON alone: expect 2–12% failure per call for schemas like ours; retries recover most.** Documented rates: prompt-only JSON 5–20% (rising with schema complexity), JSON-mode-class 2–5% parse failures but silent schema mismatches beyond that. The dominant long-output killers in our shape are **silent truncation at output budget** (finish_reason=length with unclosed braces — looks like success until parse) and **hallucinated/renamed keys** (a provider silently rolling models). A validate-retry loop with the Zod error serialized into the retry prompt recovers "most correctable mistakes", converging within 2–3 attempts; production baselines are 0.5–2% steady-state retry, 5–10% after model updates.
- **(c) Chunked (week-by-week) generation: our default.** It converts one 20k-token bet into 4–8 small schema-valid calls, each individually parseable/repairable/retryable, sidesteps truncation, and lets us fail/retry one week instead of the whole plan. Cost: K sequential round trips (latency ∝ weeks, but each is short; the off-peak window and a background job make this an acceptable tradeoff for batch) and **cross-week consistency** must be re-anchored by carrying a plan-level header + prior weeks' summary in each request (the known consistency risk of multi-call plans).
- **Recommended strategy: tool-call wrapper (`submit_plan` per week, full week schema in the tool def) + Zod validation + max 3 attempts per week (2 repair-retries, error-embedded) + jsonrepair as a pre-parse buffer + `finish_reason` gate. Escalate only after 3-week-sequential failures, kimi-k3 single-shot for the whole plan (its 10× cost is fine as the rare path).** Budgeted expectation on glm-5.3-flash: ~5% of week-chunks need ≥1 retry, ~1% need a second retry, <0.5% of plans irrecoverable before escalation.

## (a) `submit_plan(plan)` tool call — does Ollama Cloud enforce or merely nudge?

### The mechanism, verified against primary docs

- **Ollama Cloud exposes tool calling on cloud models** ("models trained to support tools are tested for tool calling and real agent workflows" — pricing FAQ) but its tool API takes a JSON-schema `parameters` object with **no enforcement flag** (docs.ollama.com/capabilities/tool-calling — verified read, Sep 30 2026). No `strict`, no grammar masking. The `format` parameter that *does* do constrained decoding is local-only ("Ollama's Cloud currently does not support structured outputs" — docs.ollama.com/capabilities/structured-outputs).
- **So: nudge.** Adherence comes from the model's instruction/tool training, not from inference-time decoding. Practically: expect it to behave like "JSON mode era" — parse-failures rare, schema mismatches (missing fields, string-typed numbers, invented keys) the thing that slips through. Zod stays mandatory regardless of approach.
- **Why it still beats plain prompting:** schema-in-tool-def is read by the model as a *first-class instruction*, not system-prompt prose. Published eval evidence: OpenAI's own history shows function-arguments adherence jumps "dramatically" with schemas-in-tools (best-effort era <40% → strict/constrained 100% — the constrained half we don't get, but the fine-tuned-adherence half is what our models have); tool catalogs as instructions also help because `description` fields act as field-level instructions.
- **Model-specific signal we can lean on:** GLM-5.3-Flash is the top open-weights model on Toolathlon-Verified (78.4% pass@1, huge tool catalog), K3 right behind at 76.5%. DeepSeek-V4.1 ships dedicated `deepseek_v41` tool-call parsers in vLLM/SGLang (i.e., its tool-call wire format is well-specified and parseable: DSML tag blocks, not JSON fences — recipes.vllm.ai/deepseek-ai/DeepSeek-V4.1-Flash). Kimi-K3's first-party API offers **strict** json_schema response_format → strong schema-adherence tuning; on Ollama Cloud we only lose that enforcement, not the training.

### Caveats specific to Ollama Cloud

- **No `strict` flag** → the tool `parameters` schema is advisory. Zod (or equivalent) validates the decoded `arguments`.
- **Truncation still applies to tool calls.** Arguments are a JSON string; if generation is cut by output budget mid-arguments you get partial JSON. Check `finish_reason` before trusting `arguments` for any large call.
- **Reasoning budget eats output budget on thinking models.** On DeepSeek-V4.1-Flash the do-nothing config is thinking at effort 50: "a request with a small max_tokens spends its budget on the trace and returns empty content with finish_reason=length" (vLLM recipe). Under Ollama Cloud's `think: true` behavior, same class of risk. Set thinking low and explicitly budget output tokens per plan-chunk call (`num_ctx`/max-token options — audit notes Ollama Cloud exposes `think` and options; exact output caps need a live probe, see ollama-cloud-model-audit.md open questions).
- Tool-call reliability anecdotes exist for Ollama Cloud (5–60s timeouts, broken tool calls; gopenai post, low trust) — recheck on our own eval.

### Verdict (a)

**Use it, as the primary emission channel, but treat the schema as a nudge with client-side Zod as the actual gate.** The expected benefit over prompt-anchored JSON is (i) schema-as-instruction adherence, (ii) clean separation of "model emits arguments" from prose, (iii) trivially reusable repair loop: on Zod failure, return the error as tool result and ask for corrected re-call.

## (b) Validation + bounded retries — documented failure rates for this class

### Where failures come from, ranked by expected prevalence for a 30–60-day plan schema

1. **Silent truncation** (budget exhaustion mid-JSON; finish_reason=length, unclosed braces) — the top long-output killer, and the reason the whole-plan-in-one-call is fragile at ~20k output tokens. Mitigated structurally by chunking (c) and a `finish_reason` gate.
2. **Schema drift keys** — `"ticket_category"` vs `"category"`, type drift (`"42"` for `42`) — these pass JSON-mode but fail Zod; recovered by error-embedded retry in most cases.
3. **Invalid/omitted enums and required fields** — models often omit rather than emit null; Zod `strict` + explicit enums catch; enum violations are among the most retry-recoverable because the valid set is enumerable in the retry prompt.
4. **Reasoning-mode degradation** — the "Let Me Speak Freely?" finding (EMNLP 2024): strict format constraining hurts *reasoning* accuracy (GSM8K −27pp on GPT-3.5, −63pp Claude-3-Haiku in JSON mode). Plan JSON is reasoning-adjacent (block structure, load ramp): prefer thinking *separated* from emission — planning prose/thinking in request 1, schema emission in request 2 — or a schema that carries a short `rationale` field *before* the day objects so ordering supports the reasoning (tam et al.; also tianpan production guidance "put reasoning fields before answer fields").
5. **Semantic garbage inside valid syntax** — structurally valid values that are physiologically wrong (load ramp 40%/wk). No decoding constraint fixes this; the plan-schema ticket should split *shape* validation (Zod) from *content* validation (deterministic engine checks, mirrors our nutrition-engine #711 floors pattern).

### Documented rates (from production postmortems and benchmarks)

| Metric | Source | Value |
|---|---|---|
| Prompt-only JSON failure | production writeups (tianpan.co 2025/2026; multiple) | **5–20%**, rising with schema complexity |
| JSON-mode parse failure | same | **2–5%** syntax fails, silent schema mismatch on top |
| Strict (constrained) failure | provider docs, postmortems | <0.3% (not available to us on cloud) |
| Validate-retry steady-state retry rate | production KPI guidance | **0.5–2%** baseline; 5–10% signals drift/schema too hard |
| Retry convergence | production pattern | "most models self-correct on the 2nd attempt; **3 retries sufficient**, beyond that unlikely to recover" |
| Constrained-decoding coverage collapse on complex schemas | 10,000-schema benchmark | Outlines 3% vs Guidance 96% — complexity kills enforcement too, not just prompting |

### Verdict (b)

**Zod + bounded retries is the load-bearing layer regardless of (a)/(c) choice.** Budget: **3 attempts per call (1 initial + 2 error-embedded retries)**, `jsonrepair` buffer before parse (catches trailing commas/unclosed-brace salvage — significant fraction without a full retry), `finish_reason === 'length'` → not a Zod retry but a *budget fix* (raise cap or reduce chunk size), track per-branch retry rates as the KPI. Expected: most failures recover at retry 1; >2 retries on same field = schema/prompt design bug, not stochastic bad luck.

## (c) Chunked generation — fallback or default?

### The mechanics

- **One shot, whole plan (~20k output tokens):** maximum intra-plan coherence in one context, but the truncation blast radius is the entire plan; a single unbalanced brace at token 19,600 discards the whole request; retry is another 20k-token bet at full price. For glm-5.3-flash at ~$0.012/request this is fine cost-wise; the risk is variance, not cost.
- **Chunked (per-week sequential calls, 4–8 calls):** each call ~2–5k output tokens, inside every candidate's comfortable envelope; failure is localized (re-emit one week, not the plan); repair cheap; truncation nearly eliminated; supports parallelization later if the plan header is the only shared context (still keep sequential for context-carry).
- **Consistency risk of chunking:** per-week calls may drift on shared structure (weekend ride lengths, ramp shape across weeks). Fix: **plan header contract** — first call emits block-level metadata (goal, block length, weekly load ramp targets, weekly theme mapping), each subsequent week-call receives the header + a compact summary of completed weeks and must not contradict it (Zod cross-checks week TSS against the header's ramp table — deterministic, no extra LLM call).
- **Latency tradeoff:** K sequential round-trips ≈ K × per-call latency. At flash-tier inference (~5–30s/call, unverified — audit open question on queue depth) a 4-week plan ≈ 30–120s job; at deepseek off-peak, batch regen is cheap and slow-but-acceptable. This is a background generation task, not interactive, so latency tolerance is high. MVP: sequential, off-peak scheduling free.

### Verdict (c)

**Chunk-by-week as the default path, not a fallback.** Keep whole-plan single-shot as the *kimi-k3 escalation* mode (when flash-tier repeatedly fails on the same plan; the $2.81T model is the strongest single-shot long-JSON bet and its cost is tolerable when it's the rare path). Never chunk *mid-week* (a day-level chunk creates 30–60 contexts that all need the full plan context re-prompted, worse consistency with better robustness — a bad tradeoff; week is the right granularity).

## Recommended generation strategy (deliverable)

For a 4-week (MVP) plan, on `glm-5.3-flash:cloud`:

1. **Call 1 (planning, thinking on):** produce block header: goal, weeks, per-week load targets, themes, constraints. Deterministic validation against nutrition/energy engine bounds (#711) and goal semantics (#708) in code — reject-and-retry this call with error context (max 2 retries).
2. **Calls 2..N (per week, thinking low/off, `submit_week_plan(plan)` tool-call wrapper with a *per-week* schema):** tool def carries exactly the week object shape from the plan schema (ticket #715). Zod parse of `arguments` (+jsonrepair salvage). Error-embedded retry ×2. `finish_reason` gate before parse.
3. **Assembly & cross-checks (no LLM):** sum week TSS vs header ramp; day-sequence validity; enum canonicality; protein/EA floors re-checked deterministically. Failures here route back as a *week-chunk* retry, not whole-plan.
4. **Escalation path:** 2 consecutive week-failures on the same week → one `kimi-k3` single-shot request for that week (not the whole plan) at $0.19–$3.00 per 1M in/15 out — cost trivial at this size, quality ceiling for the rare hard chunk.
5. **Retry/latency budget:** per attempt ~5–30s (unverified — probe on eval run); worst case 4 weeks × 3 attempts × 2 model-classes ≈ 12–24 model calls per plan; at flash pricing ≈ **$0.05–$0.15/plan worst case**, seconds-to-minutes wall time in a background job scheduled off-peak (batch regen on deepseek-v4.1-flash off-peak).

### Expected failure profile per model

| Model | Strengths | Weaknesses | Expected profile (per week-chunk, budgeted) |
|---|---|---|---|
| **glm-5.3-flash** (default) | Best-ratio flash; 1M ctx; top open-weights tool-emission (Toolathlon 78.4%); $0.15/$0.50 | Thinking mode consumes budget if unset; unverified Ollama-Cloud queue depth | ~5% chunks need ≥1 retry; ~1% need 2; <0.5% plans irrecoverable |
| **deepseek-v4.1-flash** (off-peak batch) | Cheapest 1M/vision+tools; explicit tool-call wire format (DSML); off-peak 50% | Thinking-at-effort-50 default eats budget → empty content + finish_reason=length if budget small; needs explicit thinking control | Same shape as glm; add budget-failure class; retries likely recover |
| **kimi-k3** (escalation) | Most capable; strict-mode tuned; 1M ctx | 10× cost — reserved for escalation/hard-chunk | Expect ≥glm adherence on hard chunks; use as chunk- or plan-level escalation, not default |

### What #715 (plan-schema grilling) should size the MVP cut to

- **Shallow: 2 levels, ≤8 fields at block level; day objects flat.** Deep nesting is where errors cluster (depth >3–4) under prompting and constrained settings alike; 5+ levels should be flattened client-side.
- **≤8–10 fields per object; 30–60 days is a *count*, not width** — decompose: header call + week calls each carry ≤10 fields/day-object.
- **Enums aggressive over free text** for day-type, session-type, discipline; put **`rationale` before day objects** in field order;
- **All fields required explicitly** (with explicit `"unknown"`/rest enum member rather than optional) and `additionalProperties: false` everywhere — models invent keys when allowed; optional fields are missed-field failures.
- **Deterministic `maxLength`/`maxItems` bounds in our Zod** — the DigitalOcean pilot's 37%-truncation pilot dropped to 0.00 truncation once explicit short values were enforced — plus a **length budget per chunk** so a week's JSON fits in the output cap even in thinking mode.
- **Two-layer validation from day one:** Zod (shape) + deterministic engine checks (ramp/enum/energy floors, mirrors #711 pattern) — the 15% "unsafe acceptance" figure (arxiv 2607.18261) shows even 100%-schema-valid outputs carry semantic garbage.
- **Two-step emission:** reasoning/planning in call 1, schema emission in calls 2..N — do not run block-structure reasoning *inside* JSON-constrained emission (reasoning-degradation finding), which our tool-call wrapper already gives us for free.
- **`format`-flip watch:** cloud structured outputs are "currently not supported"; if the flag flips, `submit_plan`-wrapper + Zod collapses into native `format` for free. Keep the emission path behind one adapter so the swap is cheap.

## Method

Websearch + webfetch of primary docs (Ollama Cloud tool-calling & structured-outputs pages, vLLM DeepSeek-V4.1-Flash recipe, Moonshot K3 API docs, Z.ai GLM-5 repo/docs) + production failure-mode writeups (tianpan.co 2025/2026 postmortem series, DigitalOcean structured-output-at-scale, mangiucugna/json_repair & josdejong/jsonrepair READMEs). Cross-checked against prior audit #707. No Ollama Cloud probes were run live in this ticket — output-token caps, image tokenization, queue depth, and the tool-call reliability anecdotes all need the eval run (audit #707 open questions 1–3).

## Sources

- Ollama tool calling (API shape, no strict flag): https://docs.ollama.com/capabilities/tool-calling
- Ollama structured outputs cloud caveat: https://docs.ollama.com/capabilities/structured-outputs
- Production failure taxonomy + retry-loop guidance: https://tianpan.co/blog/2025/10/29/structured-outputs-llm-production · https://tianpan.co/blog/2026/04/18/structured-output-json-mode-failure-modes
- OpenAI strict-vs-best-effort function calling history (~40% → 100%): https://www.kommunicate.io/blog/openai-function-calling/ · https://developers.openai.com/api/docs/guides/function-calling
- Open-model tool-use benchmarks (Toolathlon-Verified: GLM-5.3-Flash 78.4%, K3 76.5%): https://fleeceai.app/blog/best-llm-for-function-calling-tool-use-2026
- Kimi K3 strict json_schema on first-party API: https://platform.kimi.ai/docs/guide/kimi-k3-quickstart
- DeepSeek-V4.1-Flash reasoning-budget/tool-call wire format: https://recipes.vllm.ai/deepseek-ai/DeepSeek-V4.1-Flash
- Semantic-garbage-in-valid-JSON rates (15% unsafe acceptance): https://arxiv.org/html/2607.18261v1
- Constrained-decoding coverage collapse on complex schemas (Outlines 3%/Guidance 96%): https://www.digitalocean.com/community/tutorials/structured-output-reliability-at-scale
- JSON repair tooling (jsonrepair streaming, json_repair): https://www.npmjs.com/package/jsonrepair · https://github.com/mangiucugna/json_repair
- Reasoning degradation under format restriction (Tam et al., EMNLP 2024): https://arxiv.org/abs/2408.02442 (counterpoint on prompting quality: https://blog.dottxt.ai/say-what-you-mean.html)

## Open questions

1. Actual output-token cap per Ollama Cloud request per model — hard cap vs context-bound? Live probe needed; caps whether a whole-plan single-shot is even possible as the kimi-k3 escalation shape.
2. Ollama Cloud tool-call argument parsing on glm-5.3-flash: does the platform ever return malformed `arguments` (the gopenai anecdote claims broken tool calls)? Needs a probe in the eval run.
3. Empirical chunk-vs-whole-plan failure comparison on glm-5.3-flash vs deepseek-v4.1-flash with our actual plan schema — the eval run in the audit's open question 5 can piggyback this protocol: emit 50 plans per model per strategy, measure Zod-failure rate, retry distribution, cross-week ramp drift.
4. Do Ollama Cloud thinking models stream `thinking` separately from `content` reliably (needed for our two-step emission)? Unverified.