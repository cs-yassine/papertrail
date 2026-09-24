# Free-tier limits and token budgets — measured, not assumed

> Every number here was read from a live provider console, with the date it was read.
> Nothing in this file is copied from documentation, blog posts, or an LLM's recollection.
> Provider free tiers change without notice — **re-read the consoles before sizing any large job.**

---

## Groq — read from console.groq.com (Settings → Limits) on 2026-09-24

Chat completion models, free tier:

| Model ID | RPM | RPD | TPM | TPD | Usable here |
|---|---|---|---|---|---|
| `openai/gpt-oss-120b` | 30 | 1K | 8K | 200K | **Yes — MODEL_LARGE** |
| `openai/gpt-oss-20b` | 30 | 1K | 8K | 200K | **Yes — MODEL_SMALL** |
| `qwen/qwen3.8-27b` | 30 | 1K | 8K | 200K | **Yes — MODEL_JUDGE + fallback** |
| `openai/gpt-oss-safeguard-20b` | 30 | 1K | 8K | 200K | No — safety-tuned variant |
| `allam-2-7b` | 30 | 7K | 6K | 500K | No — Arabic-focused 7B; wrong fit for English claim extraction despite the generous TPD |
| `meta-llama/llama-prompt-guard-2-22m` | 30 | 14.4K | 15K | 500K | No — prompt-injection classifier, not a chat model |
| `meta-llama/llama-prompt-guard-2-86m` | 30 | 14.4K | 15K | 500K | No — same |

Speech and TTS models are listed in the console but unused by this project.

### What these numbers mean for the build

**Quotas are per model, not pooled.** Each row has its own daily bucket. Routing small tasks
to `gpt-oss-20b` and large tasks to `gpt-oss-120b` therefore buys throughput, not just cost:
**~600K tokens/day across the three usable models.** `llm/ratelimit.py` must key its counters
by `(provider, model)` for this to hold. This is now the project's entire LLM capacity — see
the Gemini section below.

**8K TPM is the binding constraint, not TPD.** 200K ÷ 8K ≈ 25 minutes of continuous
full-rate use exhausts a day's quota. Consequences:

- Ingestion is bursty by nature: roughly half an hour of work per day per bucket, then a
  clean stop until reset. Jobs must resume, not restart.
- `max_concurrency=4` (spec §5.3) buys nothing. At ~3–5K tokens per extraction call, TPM
  allows about 2 calls/minute regardless of concurrency. Set concurrency to 1–2.
- The rate limiter must **wait** on TPM rather than retry into it; retries spend quota and
  return 429s.

**gpt-oss models are reasoning models.** Hidden reasoning tokens count against
`max_completion_tokens` and against TPD. This is the empty-completion failure mode from
`docs/incidents.md`: a `max_tokens` sized for a non-reasoning model yields empty content with
`finish_reason="length"`. Sizing comes from `make audit-budgets`, never from instinct.

**TPD reset time: UNKNOWN.** Observe whether it resets at midnight UTC or on a rolling
window, and record it here — `scripts/ingest.py`'s resume hint depends on it.

```
Observed reset behaviour:  (fill in after the first exhaustion)
```

**8K TPM confirmed the hard way, 2026-09-25 (Phase 0.5 spike).** Firing 8 extraction
calls back-to-back with no pacing (average ~950 total tokens/call, so cumulative ~7.6K
within well under a minute) tripped a 429 on the 9th call. This is exactly the warning
above, now observed directly rather than inferred from the console's published numbers:
**TPM binds even when individual calls are small**, because it's cumulative-per-minute,
not a per-call ceiling. Adding a fixed ~25s pause between live calls (skipped entirely on
cache hits) let the remaining calls complete with zero further 429s. `llm/ratelimit.py`
must do this properly (sliding window, not a fixed sleep) — the fixed pause was a
spike-only shortcut, not a design worth carrying into P1.

---

## Google AI Studio (Gemini) — UNAVAILABLE, checked 2026-09-24

AI Studio reports for project `paperTrail`:

> *"L'accès à l'API de ce projet est limité. Veuillez configurer la facturation pour continuer."*
> (API access for this project is limited. Configure billing to continue.)

**No free-tier API access without a billing account, so Gemini is out under Rule 0.**
Usage history is empty, so this is not a quota the project burned through — the free tier is
simply not offered here. Possibly regional; not worth chasing, since a second Google account
would likely behave the same.

Recorded because the dead end is as useful as the limits: it explains why the system runs on
one provider, and it is the reason the judge is what it is.

**If Groq's ~600K/day proves too tight in P2, candidate free second providers, in order:**
Cerebras · GitHub Models (free with a GitHub account) · Cloudflare Workers AI.
**Do not add one speculatively.** Add it when a measurement says the corpus cannot be built
without it.

---

## Chosen routing

Set in `.env`; read by `config.py`. No model name appears anywhere else in the codebase.

```
MODEL_LARGE     = openai/gpt-oss-120b    # extraction, synthesize, critique
MODEL_SMALL     = openai/gpt-oss-20b     # rewrite, plan, grade, adjudicate
MODEL_JUDGE     = qwen/qwen3.8-27b       # pinned, temp 0, never used for generation
MODEL_FALLBACK  = qwen/qwen3.8-27b       # third bucket when 120b or 20b exhausts
```

### Judge independence — a documented compromise

The eval judge must not grade its own output. With Gemini unavailable, generator and judge
both live on Groq, so independence rests on `qwen3.8-27b` being a different vendor and a
different training lineage from the `gpt-oss` family rather than a different provider.
That is weaker than cross-provider independence.

Consequences, all non-optional:

- `MODEL_JUDGE` is **never** used for generation, and `MODEL_FALLBACK` must never resolve to
  the judge model **during an eval run**. If the fallback fires mid-eval, the affected items
  are excluded and counted separately — never silently scored.
- Every call logs `served_by`. Eval runs assert generator ≠ judge per item.
- The README's limitations section states this plainly. It is a real constraint of building
  for free, not something to gloss.

### Extraction is pinned (decision (a)3)

Originally about not mixing Groq and Gemini mid-ingest. With one provider it means:
extraction runs on `MODEL_LARGE` only and **waits out quota rather than falling back**, so
the corpus is extracted by a single model with consistent claim granularity.
`extracted_by` is recorded on every claim regardless. Adjudication *may* fall back to
`MODEL_FALLBACK` and records `adjudicated_by`.

---

## Token budgets — mostly NOT YET MEASURED; EXTRACTION has preliminary spike data

Full sizing is filled by `make audit-budgets` in Phase 1. Until then every figure below is
an estimate and must be labelled as such wherever it appears.

**EXTRACTION has one preliminary data point from the Phase 0.5 spike (2026-09-25, 10
calls, `gpt-oss-120b`, `reasoning_effort=low`, `max_completion_tokens=2000`,
`temperature=0`). This is not the P1 audit** — one model, one reasoning-effort setting,
one prompt version, n=10 (too small for a real p95), and critically: **input was
abstract+conclusion only** (9 of 10 papers; 1 of 10 abstract-only fallback — see below),
**not the full title/intro/conclusion sections P2's real pipeline will send.** Treat this
as a measured lower bound on EXTRACTION's cost, not a sizing decision.

| Task | Measured avg completion (reasoning+visible output) | Measured avg reasoning | Reasoning share of completion | Empty completions | `reasoning_effort` used |
|---|---|---|---|---|---|
| EXTRACTION (spike, n=10, abstract+conclusion) | 468 tokens | 199 tokens | 42.5% | **0 / 10** | `low` |
| ADJUDICATE | | | | | |
| GRADE | | | | | |
| REWRITE | | | | | |
| PLAN | | | | | |
| SYNTHESIZE | | | | | |
| CRITIQUE | | | | | |

**`max_completion_tokens=2000` at `reasoning_effort=low` yielded zero empty completions
across all 10 calls** — the highest single completion observed was 598 tokens (reasoning
209 + visible ~389), leaving comfortable headroom under 2000. This is the first real
evidence against the Lore failure mode for this specific (model, effort, section-length)
combination — it says nothing about `medium`/`high` effort, other tasks, or longer inputs.

⚠ The spec's `BUDGET_MAX_OUTPUT_TOKENS=1800` per request was sized for non-reasoning models.
The audit must re-derive the whole per-request envelope, not just per-task `max_tokens`.

---

## Throughput projections

### Measured: extraction cost per paper (Phase 0.5 spike, 2026-09-25, n=10)

| Section fetched | n papers | Avg input | Avg completion | Avg claims/paper |
|---|---|---|---|---|
| Abstract + conclusion | 9 | 742 tokens | 477 tokens | 7.1 |
| Abstract only (fallback — ar5iv/arxiv.org/html both failed) | 1 | 389 tokens | 382 tokens | 7.0 |
| **All 10, mixed** | 10 | **707 tokens** | **468 tokens** | **7.1** |

**1 of 10 papers (`2001.08361`, Kaplan et al., "Scaling Laws for Neural Language
Models") fell back to abstract-only** — both `arxiv.org/html/{id}` and
`ar5iv.labs.arxiv.org/html/{id}` failed to return usable HTML for it. The other 9 got a
real conclusion section, not just the abstract. Total across all 10 calls: 7,070 input +
4,677 completion (1,989 of that reasoning) = **11,747 tokens, zero empty completions.**

**This measured ~1.15K tokens/call/paper is markedly lower than the spec's original
~3–5K/call estimate** — but it is **abstract+conclusion only, one call per paper**, not
P2's real design (spec §5.3 batches one call **per section** — title, intro, conclusion,
etc. — so a real paper likely costs *more* than one of these calls, not the same). Do not
carry the ~1.15K figure into a P2 sizing decision without re-measuring on real
per-section calls; it's a lower bound, not the number.

### Revised projections, using the measured (lower-bound) extraction cost

| Job | Volume | Tokens (measured basis) | Bucket | Projected wall clock |
|---|---|---|---|---|
| Extraction, 100 papers, **at the spike's measured rate** | ~100 calls | ~115–122K (100 × ~1.15–1.22K) | `gpt-oss-120b` @ 200K TPD, 8K TPM | **≥~17 min of TPM-paced calls, single day** — a big drop from the prior 2–3 day estimate, *if* P2's real per-paper cost holds near the spike's. It almost certainly won't, since P2 extracts more than abstract+conclusion. Treat as optimistic, not planned |
| Extraction, 100 papers, **at the spec's original per-call estimate (unmeasured, for contrast)** | ~100 calls | ~400–600K | `gpt-oss-120b` @ 200K/day | 2–3 days |
| Adjudication, ~800 anchors (still unmeasured — spike did not test ADJUDICATE) | ~800 calls | ~1M | `gpt-oss-20b` @ 200K/day | ~5 days |
| Adjudication, split 20b + qwen | ~800 calls | ~1M | 400K/day | 2–3 days |

**The honest takeaway is not "100 papers now takes 17 minutes."** It's that the spike's
abstract+conclusion, single-call-per-paper measurement undercounts P2's real design, so
the true number sits somewhere between the two extraction rows above — re-measure on
P2's actual per-section calls before trusting either one for a schedule.

Splitting adjudication across two buckets competes with judge availability, since qwen is
also `MODEL_JUDGE`. Adjudication is P3 and evals start in P5, so they do not overlap in
practice — but never run an eval on a day adjudication has drained the qwen bucket.

Levers if the measured rate confirms these, in order of preference:

1. Candidates per anchor 5 → 3 (cuts adjudication tokens ~40%)
2. Raise `LINK_MIN_SIM` so fewer pairs qualify
3. Cut the v0.5 corpus to 60 papers (~480 anchors)
4. Add a second free provider (see the Gemini section) — last resort, not first

**Measure P2's actual per-section extraction calls before sizing 100 papers for real.**
Replace the extraction rows above with P2's real numbers as soon as they exist, and
delete the word "estimate"/"measured (lower-bound)" once they do. Adjudication rows are
still entirely unmeasured — the spike only tested EXTRACTION.

---

## Other free-tier constraints

| Service | Limit | Mitigation |
|---|---|---|
| Neo4j AuraDB Free | Pauses after 3 days idle; **deleted after 30** | Local Docker Neo4j is the ingest target; Aura receives snapshots. Scheduled `/health/deep` ping keeps it awake |
| Cloud Run | 2M req, 180K vCPU-s, 360K GiB-s per month (US free-tier regions) | `--min-instances 0`. Warm-up ping before demos. **Never** min-instances ≥ 1 |
| GitHub Actions | Free for public repos | Repo stays public |
| Langfuse | Hobby tier | Tracing optional via env; an outage or quota exhaustion must never fail a request or CI run |

GCP billing alert set at $1: **[ ] not yet done**

---

## Cost column in the delta table

Free tiers make actual spend $0.00, so a "$/query" column of zeros says nothing. The callback
computes a **list-price equivalent** from published per-token rates and the column is labelled
as such. $0 is a consequence of the tier, not an engineering achievement, and the README says so.