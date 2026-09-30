# Ollama Cloud Model Audit — Coach scope (meal-photo estimation + plan JSON)

- **Ticket:** tomberch/training-dash#707 (parent #706)
- **Date:** 2026-09-30
- **Method:** read Ollama Cloud primary sources (pricing page, cloud model catalog, model cards, docs.ollama.com capability pages) via webfetch; supplementary checks against third-party trackers and the OpenCode provider registry (which proxies `ollama-cloud`). All prices verified against https://ollama.com/pricing on 2026-09-30.

## Sources

- Plans & per-token pricing, concurrency, off-peak pricing: https://ollama.com/pricing
- Cloud model catalog (16 models): https://ollama.com/search?c=cloud
- Structured outputs (⚠️ cloud caveat): https://docs.ollama.com/capabilities/structured-outputs
- Tool calling: https://docs.ollama.com/capabilities/tool-calling
- Cloud API basics / OpenAI- & Anthropic-compatible endpoints: https://docs.ollama.com/cloud
- Model cards: glm-5.3-flash, minimax-m3, kimi-k3, kimi-k2.7-code, deepseek-v4.1-flash, mistral-large-3, gemma4, gpt-oss — `ollama.com/library/<name>`
- Limits/deprecation tracker (independent re-read of pricing page daily): https://ollamatps.com/limits/
- Anecdotal reliability complaints: https://blog.gopenai.com/why-you-should-completely-avoid-ollama-in-2026-6135d9e8591e (low-trust, see Open questions)
- OpenCode provider registry (`tools.opencode.models`) — cross-check of prices/context for `ollama-cloud/*` IDs (off-peak rates).

## What Ollama Cloud is (as of Sep 2026)

Hosted inference for open-weight models, no logging/no training/zero data retention, US/EU/SG capacity, NVIDIA NCP hosting. Billed **per-token in usage credits**, per-model rates, with **off-peak pricing** (~50% off) outside 12:00–18:00 UTC on weekdays and all weekend. Plans: Free ($0, starter credits, starter models, 1 concurrent), Pro $20/mo ($60 credits, 3 concurrent), Max $100/mo ($300 credits, 10 concurrent), Team $500/mo ($1,000 shared credits, 10 concurrent). **No published RPM/TPM** — only plan concurrency + credit budget are enforced publicly.

API: `https://ollama.com/api/chat` with `Authorization: Bearer $OLLAMA_API_KEY`, or OpenAI/Anthropic-compatible subsets. Cloud models do **not** need download; identifiers like `glm-5.3-flash:cloud` (app/CLI) or `glm-5.3-flash` (HTTP API).

## Critical constraint: structured outputs are NOT supported on Cloud

> "Ollama's Cloud currently does not support structured outputs."
> — https://docs.ollama.com/capabilities/structured-outputs

The `format` (JSON schema) parameter is documented **local-only right now**. Tool calling **is** supported on cloud models ("models trained to support tools are tested for tool calling and real agent workflows", pricing FAQ).

**Consequences for Coach plan generation:**
1. Large plan-JSON cannot be schema-enforced server-side. We must do prompt-anchored JSON + client-side validation (Zod) + bounded repair/retry loop.
2. A viable substitute: a single tool definition, e.g. `submit_plan(plan: PlanSchema)`, run in a one-shot agent loop — cloud tool-calling is tested by Ollama; the tool schema acts as the "format".
3. Keep plan JSON schemas shallow-ish and chunk generation (per-week) to reduce malformed-JSON blast radius.

## Vision models available on Ollama Cloud (verified `Text, Image` input on model card)

| Model | Params | Context | Input/cached/output $/1M | Tags | Notes for meal photos |
|---|---|---|---|---|---|
| **glm-5.3-flash** | 321B MoE / 18B active | **1M** | 0.15 / 0.03 / 0.50 | vision tools thinking | First natively multimodal GLM; accepts image *and video*; strong vision benchmarks (OfficeQA 62.4, MVBench 77.8) but tuned toward docs/UI, not food |
| **deepseek-v4.1-flash** | 552B MoE (8–16B active) | **1M** | 0.30 / 0.006 / 1.20 peak; **0.15 / 0.003 / 0.60 off-peak** | vision tools thinking | Cheapest vision+1M option; KV-cache compression aimed at long agentic workloads |
| **minimax-m3** | n/a | **512K guaranteed (1M max)** | 0.60 / 0.12 / 2.40 | vision tools thinking | "Native multimodality… not a superficial add-on"; multimodal training from step 0 |
| **kimi-k3** | 2.81T MoE | **1M** | 3.00 / 0.30 / 15.00 | vision tools thinking | Most capable open model; native vision; **10× cost** of glm-5.3-flash — reserve for hard cases |
| **kimi-k2.7-code** | 1.04T | 256K | 0.95 / 0.19 / 4.00 | vision tools thinking | Coding-focused; vision listed but not its strength |
| **kimi-k2.6** | n/a | 256K | 0.95 / 0.16 / 4.00 | vision tools thinking | Older K2 line |
| **gemma4[:31b cloud]** | 31B (also 2b–26b local) | 256K (128K small) | 0.14 / 0.05 / 0.40 | vision tools thinking audio | Cheapest vision; multimodal; good for budget/dev; weaker on hard visual reasoning |
| **mistral-large-3** | 675B | 256K | 0.50 / — / 1.50 | vision tools | "native function calling and JSON outputting"; 10 months old — oldest card, retirement risk |
| ❌ gpt-oss (20b/120b) | 21B/117B | 128K | 0.07–0.15 | tools thinking (**no vision**) | text-only |
| ❌ glm-5.3 / 5.2, deepseek-v4-pro, minimax-m2.7, nemotron-3-* | — | up to 1M | — | tools thinking (no vision) | text-only |

Retired (June 2026) predecessor vision models — evidence of model churn: `qwen3-vl:235b` (→ qwen3.5, which is *local-only* on Ollama), `glm-4.6`, `minimax-m2`.

**No Ollama-hosted model is food-tuned.** Their vision benchmarks cover documents/charts/video, never food benchmarks (FoodX-101, SNAPMe, FPB). Published research on general VLMs reports food-detection accuracy 74–99% but calorie/portion error is commonly ±20–50% from a single photo (systematic review: researchgate.net/publication/376311409). Portion estimation without a reference object is inherently weak regardless of model — treat model output as an estimate needing user correction, not ground truth.

## Ranked shortlist (a) — Vision for meal-photo estimation

1. **glm-5.3-flash** — best ratio: natively multimodal (incl. video — useful if Coach adds meal video), 1M ctx, $0.15/$0.50, tools+thinking, top vision scores among open cloud models. Primary pick.
2. **deepseek-v4.1-flash** — cheapest at 1M/vision, off-peak $0.15/$0.60. Strong #2 / cost fallback; run A/B against glm-5.3-flash on a meal-photo eval set.
3. **minimax-m3** — most explicitly "native multimodality", 512K guaranteed. Pick if glm results are weak on photo semantics.
4. **gemma4:31b** — cheapest ($0.14/$0.40), multimodal with tools+thinking, and runnable locally (e4b–31b sizes) for free dev/CI testing. Pick for budget tier and for identical local/cloud dev experience.
5. **kimi-k3** — most capable; use only for escalation, given $3/$15 per 1M.
6. **mistral-large-3** — only if native JSON outputting proves most reliable for vision+JSON in one call; watch retirement risk.

**Suggested pattern (applies to whichever model):** two-pass — (1) vision pass returns dish inventory + portion in household units + confidence; (2) deterministic kcal/macro calculation against a food DB (USDA FDC). Do not let the VLM emit kcal numbers directly.

## Ranked shortlist (b) — Long structured plan JSON

Contexts here are generous; the real limits are output length and the missing structured-output support.

1. **deepseek-v4.1-flash (off-peak)** — $0.15 in / $0.60 out / 1M ctx; thinking + tools. Best cost for multi-week plan generation with heavy output. Off-peak window = all weekend + weekday nights → schedule generation jobs then.
2. **glm-5.3-flash** — $0.15/$0.50, 1M ctx, frontier-tier coding/agentic competence. Equivalent cost to #1 peak; strongest general quality. Recommended default (`low` effort for cheap, `max` for final pass).
3. **glm-5.3** — flagship quality for the one-shot "final plan polish" if flashes underperform: $1.40/$4.40.
4. **deepseek-v4-pro** — $1.32/$3.96, 256K? (large ctx, 3 reasoning modes); solid mid-tier.
5. **minimax-m3** — $0.60/$2.40, 512K; also multimodal → could do photo+plan-refinement in one model, simplifying the stack.
6. **gpt-oss:120b** — $0.15/$0.60, 128K ctx, text-only, native structured outputs *locally*; cheap fallback but context too small for photo+plan+multiplex in one request, and no vision.
7. **kimi-k3** — quality ceiling, cost ceiling.

Cost modeling for a 4-week plan JSON (~20k output tokens, 15k input incl. chat history): glm-5.3-flash ≈ $0.012/request; kimi-k3 ≈ $0.355/request; at 1k requests/mo, glm-5.3-flash ≈ **$12/mo** — fits inside Pro's $60 credits; kimi-k3 ≈ $355/mo — does not.

## Concrete limits summary

- **Concurrency:** Free 1 / Pro 3 / Max 10 / Team 10. No published RPM/TPM.
- **Credits:** Free starter / Pro $60 / Max $300 / Team $1,000 per month, no rollover, reset monthly on subscription date. Extra credits purchasable on any plan.
- **Off-peak:** all weekend + weekdays outside 12–18 UTC → deepseek-v4.1-flash input/output ~50% off.
- **Context windows:** 1M (glm-5.3-flash, deepseek-v4.1-flash, kimi-k3), 512K guaranteed (minimax-m3), 256K (kimi-k2.6/2.7, gemma4:31b-cloud, mistral-large-3), 128K (gpt-oss).
- **Structured output:** ❌ not supported on cloud (`format` ignored). Tool calling: ✅.
- **Image token billing:** not documented — verify empirically (open question).
- **Deprecation risk:** models are retired with notice (5 models retired Jun 2026). Build model-ID config, not hardcoded model strings. Usage/settings page exposes upcoming retirements for models you've used.

## Recommendation for Coach (meal photos + multi-week plan JSON)

- **Two-model setup, both cheap-flash tier:** `glm-5.3-flash:cloud` as default for *both* photo analysis (vision, 1M ctx) and plan JSON; `deepseek-v4.1-flash:cloud` (off-peak) as cost fallback / batch re-generation. Evaluate both on a 50-photo meal set before lock-in (ticket-blockers #710 / #712).
- **Plan generation:** don't depend on cloud `format`. Use: per-week chunked prompts + Zod parse + max-2 repair retries; or wrap in a single `submit_plan(plan: PlanSchema)` tool call. Validate server-side before persisting.
- **Photo estimation:** vision pass → foods, household-unit portions, confidence ∈ [0,1]; kcal/macro via food-DB lookup in our code; show estimate ± range and an "edit" affordance; treat kimi-k3 as escalation path only.
- **Budget:** Pro ($20/mo, $60 credits) covers dev + early users at glm-5.3-flash pricing; move to Max (10 concurrent) when concurrent Coach sessions matter.
- **Ops:** pin model IDs in config; subscribe to retirement emails; schedule batch generation off-peak.

## Open questions

1. How are image inputs tokenized/billed on the cloud API (no public rate)? Needs a live probe.
2. Actual RPM/TPM/queue depth on Free/Pro — only concurrency is published. Needs a load probe before promising plan latency.
3. Reliability anecdotes of 5–60s timeouts and broken tool calling on Ollama Cloud (gopenai post, hermes-agent #65563 session-limit 429s) — unverified severity on the new credits plans; recheck after our own eval run.
4. Structured-output support on cloud is explicitly "currently not supported" — watch docs for the flag flip; if added, revisit tool-call workaround.
5. Does `glm-5.3-flash` handle food photography well (vs. its doc/UI-strength vision)? Requires empirical meal-photo eval — no public food benchmark on the card.
6. When does `qwen3.5` get a cloud (vision) tag on Ollama? It replaced `qwen3-vl:235b` locally; a cloud vision Qwen would add an option.