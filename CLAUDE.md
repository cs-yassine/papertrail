# PaperTrail — operating manual

> This file is loaded into every Claude Code session. Read it before proposing a plan.
> The full specification lives in `PAPERTRAIL_MASTER_CONTEXT.md` (same directory / repo root).
> Where this file and the spec disagree, **this file wins** — it carries corrections to the spec.

---

## What this is

Contradiction-aware GraphRAG research agent over ~300 arXiv papers (cs.CL + cs.LG) on three
contested topics: RAG vs long-context, chain-of-thought faithfulness, emergent abilities.

Claims (not chunks) stored in Neo4j with `SUPPORTS` / `CONTRADICTS` edges between papers.
Hybrid retrieval (vector ∪ fulltext → RRF → bounded 1-hop graph expansion).
Bounded LangGraph agent: rewrite → plan → retrieve → grade → [expand] → synthesize → critique.
Answers carry citations to specific claims, an explicit confidence state, and honest refusals.
Every change is measured against a committed naive-RAG baseline on a frozen 40-item gold set.

The repository **is** the deliverable. The delta table, the ADRs, and `docs/incidents.md` matter
as much as the running app.

---

## Rule 0 — ZERO COST IS A HARD CONSTRAINT

This project must cost **$0.00**. Not "cheap". Zero. Treat any step that could produce a charge
as a blocking question for the human, not a judgement call.

**Never, without explicit approval:**
- Deploy with `min-instances >= 1` (an always-on Cloud Run instance is billed; the spec's
  `--min-instances 1` advice is **overridden** — see "Deployment" below).
- Add a credit card to a provider to lift a rate limit, or upgrade any tier.
- Call a paid-only model, a hosted embedding API, a hosted reranker, or a paid vector DB.
- Add a dependency that requires a paid account to run.
- Provision GPU hardware anywhere.

**Design consequence:** free tiers are bounded by *rate*, not by money. So every pipeline that
makes LLM calls must be **resumable, cached, and rate-limit-aware**, because it will span days.
Slow is acceptable. Paying is not. Losing work to a 429 is not.

If a task cannot be completed for free, say so and stop. Do not quietly downgrade quality or
silently skip papers.

---

## Non-negotiable rules

1. **EVAL-FIRST.** Never claim an improvement without running `make eval-smoke` and reporting the
   delta. **Never write a number into a table, summary, or README that did not come from a run
   whose output you can point at.** Fabricated metrics are the single worst failure mode here.
2. **One phase per session.** Do not refactor outside the task's blast radius.
3. All LLM boundaries return Pydantic models via `llm/structured.py`. Never parse JSON ad hoc.
4. Every LLM call goes through `llm/client.py` (rate limiter → retries → fallbacks → non-empty
   assert) and `llm/budget.py` (envelope checked **before** the call). **No direct provider SDK
   calls anywhere.** No `import groq`, no `import google.generativeai` outside `llm/`.
5. `domain/` imports nothing from infra — no langchain, langgraph, neo4j, httpx. There is an
   import-lint test enforcing this; do not weaken it.
6. `make check` (ruff + mypy strict) must pass. Fix the cause; do not add `# type: ignore`.
7. New code without tests is unfinished. Unit tests use a fake model and no network;
   integration tests use dockerized Neo4j.
8. Loops must **provably terminate**: step caps, revision caps, expansion caps, no-progress guard.
   Bounds live in code, never in prompt text or comments.
9. All thresholds live in `config.py`. No magic numbers elsewhere. **No model name is ever
   hardcoded** — free-tier model availability changes month to month.
10. Non-obvious decisions get a 10-line ADR in `docs/adr/`. Ask before architectural changes.
11. **Ask, don't assume, on anything that costs money, deletes data, or freezes the gold set.**

---

## Corrections to the spec (apply these; the spec text is stale)

The master context file was written before these issues were caught. Implement the fix, not the
original text.

| # | Spec says | Do this instead |
|---|---|---|
| 1 | `content_hash` = sha256 of claim text, globally unique | Hash **`arxiv_id + normalized_text`**. Two papers making the same claim must stay two nodes, or provenance breaks. |
| 2 | `route_after_grade` → sufficient / expand / refuse | Add a **`hedge`** route. 1 relevant doc after expansion → synthesize with `confidence="hedged"`. Without it the three confidence states never occur. |
| 3 | `thread_id = session_id` | `thread_id = f"{session_id}:{request_id}"`. A reused thread resumes the previous checkpoint, so turn 2 inherits `steps`, `docs` and `expansions_used` and hits caps immediately. Conversation history comes from `query_log`, not from the checkpointer. |
| 4 | `SqliteSaver.from_conn_string(...)` | `AsyncSqliteSaver` — the sync saver does not work with `astream`. |
| 5 | Stream answer tokens during synthesis | Stream **status events only** until critique passes, then stream the answer. Never show the user a draft that critique is about to reject. |
| 6 | "Budget checked before every call" | Budget is not visible inside `llm/client.py`. Propagate it explicitly via `RunnableConfig` or a `contextvar` set by the harness. Decide in P1 and write it down. |
| 7 | `used_ids: list[int]` | Keep an explicit `card_number → claim_id` map in state. Citation precision/recall are scored on claim IDs, not card numbers. |
| 8 | `CONTRADICTS` stored directed | Write one canonical direction (lower id → higher id); **query undirected** `-[:CONTRADICTS]-`. Also send both orderings' claims to the adjudicator in a stable order so the verdict is not position-dependent. |
| 9 | Gold set keyed by claim UUIDs | Key gold items by **`content_hash`**. UUIDs regenerate on re-extraction and would silently break every item. |
| 10 | LLM drafts the gold set from the graph | LLM may draft `direct` and `multi_hop` only. **Write the 6 `paraphrase` items and the 4 in-domain traps by hand** — graph-derived questions are biased toward what is already retrievable. |
| 11 | Vector search filtered `status='active'` | Post-filter with overfetch; Aura's vector index post-filters. Verify behaviour on your instance before relying on it. |
| 12 | Cost column in the delta table | Free tiers make real cost $0. Compute **list-price equivalent** in the callback and label the column that way. Never present $0 as an achievement. |
| 13 | `--min-instances 1`; SQLite for logs | See Deployment below. `min-instances 0`. SQLite on a scale-to-zero host is **ephemeral** — either accept that and document it, or move `query_log` into Neo4j. Decide in P9, not P11. |
| 14 | CI eval with "cached fixtures" | Record/replay keyed by (model, prompt_hash). A cache miss in CI **fails** with "re-record locally"; CI never holds live API keys. Load a committed graph snapshot into the Neo4j service container. |
| 15 | 10-item smoke slice | Stratify it: ≥2 unanswerable, ≥2 conflict, ≥2 paraphrase. "False-answer rate > 0 fails" is meaningless if the slice contains nothing refusable. |
| 16 | `ragas` in the stack | Drop from v1 dependencies — it is only used in stretch goals. |

Also: **metric definitions are ambiguous in the spec.** Fix them in `docs/evaluation.md` in P5 and
never change them afterwards:
- `hit@5` = top 5 of **retriever output, before grading**, for every system including the baseline.
- `conflict surfaced` = the answer cites claims from **both sides of a gold CONTRADICTS pair**
  (deterministic, works for the baseline which has no `is_conflicted` field).

---

## Free-tier operating reality (verified Sept 2026 — re-verify in your own console)

Provider limits change frequently and the public numbers conflict. **Always read the live limits
page in the console before sizing a job**, and record what you saw in `docs/costs.md` with a date.

- **Groq free**: organization-level, not per key. Roughly 30 RPM / 1,000 RPD / 200k **tokens per
  day** on current models. Llama 3.1-8B and 3.3-70B were removed from the free tier in Aug 2026 —
  the spec's model names are dead. Current free models are the `gpt-oss` family.
- **`gpt-oss` models are reasoning models.** This is exactly the Lore incident: they spend the
  output budget on internal reasoning and return **empty content** when `max_tokens` is sized for a
  non-reasoning model. The non-empty assert in `llm/client.py` is not optional, and
  `scripts/audit_token_budgets.py` must run before the full ingest.
- **Gemini free (AI Studio)**: per **project**, not per key. Flash-Lite models carry far higher RPD
  than Flash. Pro models are paid-only. Numbers move; check AI Studio.
- **Neo4j AuraDB Free**: one instance, pauses after **3 days** of inactivity, **deleted after 30
  days**. A paused instance's hostname does not even resolve. Keep-alive ping is mandatory.
  Node/relationship caps are well above this corpus either way.
- **GitHub Actions**: free for public repos. Keep the repo public from day one.
- **Langfuse**: free hobby tier. Tracing must be **optional via env** — a Langfuse outage or quota
  exhaustion must never fail a request or a CI run.

**Consequence for ingestion (P2/P3):** a 200k token/day ceiling will not ingest 300 papers in one
sitting. Therefore:
- `scripts/ingest.py` is **resumable by default** — re-running skips completed papers via
  `content_hash`, and it exits cleanly on quota exhaustion with a resume hint, never a crash loop.
- `llm/ratelimit.py` tracks RPM / TPM / RPD locally and **waits rather than burning retries**.
  Honour the `retry-after` header on 429. Read `x-ratelimit-remaining-*` headers when present.
- Every raw LLM response is written to the on-disk cache (P1) so nothing is ever spent twice —
  including across re-runs, prompt-identical retries, and CI.
- Relation linking in P3 sends **one call per claim carrying all 5 candidates**, not five calls.
- **Start with 100 papers.** Ship v0.5 on 100. Extend to 300 only if quota allows.

---

## Deployment (free)

- **API**: Cloud Run, `--min-instances 0`, request-based billing, a US free-tier region, 512 MiB.
  Stays inside Always Free (2M req/mo, 180k vCPU-s, 360k GiB-s). Cold starts are the price of free.
- **Warm-up instead of min-instances**: a `/health` ping before demoing, plus a GitHub Actions cron
  that pings `/health/deep` (which also keeps AuraDB awake). Never leave an instance running.
- **UI**: static build on GitHub Pages or a Static HF Space (both free), calling the Cloud Run API.
  Note: HF *compute* Spaces (Docker/Gradio) may now require a paid plan — verify before choosing.
- **Budget guard**: set a GCP billing budget alert at $1 the day the project is created.
- If Cloud Run cannot be made free without a card on file, raise it with the human rather than
  proceeding.

---

## Architecture map

```
llm/ (ratelimit → client → router → budget → structured → callbacks → cache)
  → ingestion/ → retrieval/ → agent/ (nodes are pure functions on AgentState)
  → evals/ → api/ → mcp_server/
```

LangChain for chains, the custom retriever, and parsers. LangGraph for the state machine.
Framework types must not leak into `domain/`.

**Where LangChain is deliberately NOT used** (be ready to defend this): no legacy pre-built chains,
no LangChain memory classes, no `AgentExecutor`, no vector-store wrapper for retrieval.

---

## Model routing

All model names come from `config.py` env vars. Never hardcode one; never change routing without
an eval delta.

| Task | Tier |
|---|---|
| `REWRITE`, `PLAN`, `GRADE`, `ADJUDICATE` | small |
| `EXTRACTION`, `SYNTHESIZE`, `CRITIQUE` | large |
| `EVAL_JUDGE` | large, **pinned, different from the generator**, temp 0 |

`RunnableWithFallbacks` spans providers (Groq ⇄ Gemini) so one provider's daily quota exhaustion
degrades to the other instead of failing. Log which provider actually served each call.

---

## Known traps — learned in production, design against them

- **Reasoning models spend the output budget on internal reasoning**: a `max_tokens` sized for
  another model yields **empty output**, and fail-open defaults hide it as normal operation.
  Assert non-empty on every structured call → `EmptyCompletionError`.
- **A successful HTTP response does not guarantee a successful DB write.** A foreign-key rollback
  once discarded logs *after* a 200 was returned. Verify persisted state independently; integration
  tests assert rows, not status codes.
- **Resilience verified at one call site does not extend to a neighbouring one.** Audit each.
- **Similarity thresholds cannot judge semantic relevance.** Measured overlap: answerable questions
  scored 0.827–0.911, unanswerable 0.798–0.855. No cut point separates them. The gate is an LLM
  judgement; similarity is only a cheap pre-filter. (ADR-0007)
- **Judging completeness instead of relevance** made the gate over-strict and cost 22 points of
  correctness. The gate prompt judges **relevance only**.
- **Dedup did not improve hit@5** — a null result. Report negative results in the README; they are
  more credible than a table of only wins.
- **Free-tier congestion blocks evals at the worst time.** Never run a live eval right before a demo.

Each of these gets an entry in `docs/incidents.md`.

---

## Security posture

Retrieved claim text is **untrusted data** and never goes in the system role. The synthesis prompt
states that context is data, not instructions. Output is schema-validated before rendering. No tool
has side effects in v1, so the blast radius is bounded — say this explicitly in the README.
Secrets via env only; never commit a key, never print one in a log or a trace.

---

## Commands

```
make dev · make check · make test · make test-int · make ingest N=30
make eval-smoke · make eval-full · make run-api · make run-ui · make demo
make audit-budgets · make snapshot-graph
```

---

## Session workflow

One phase = one branch = one session. Start in **Plan Mode**:
*"Read CLAUDE.md, docs/adr/ and the spec for Phase N. Propose a plan: files, interfaces, tests.
Wait for approval."* → implement → `/review` → `make check && make test && make eval-smoke` →
human reads the full diff → conventional commit → merge → `/clear`.

---

## Definition of done (every task)

- [ ] `make check` green
- [ ] tests added and passing
- [ ] `make eval-smoke` delta reported **from an actual run**
- [ ] no TODOs left behind
- [ ] module docstrings present
- [ ] ADR written if a decision was made
- [ ] nothing added that can incur a charge

---

## What you will get wrong — watch for it

- Direct provider SDK calls bypassing the router (grep for provider imports before committing).
- Tests that mock so much they assert nothing — ask "what would this fail to catch?"
- Over-abstraction for two implementations — YAGNI, simplify.
- **Fabricated eval numbers in summaries.** Run it or do not report it.
- Unbounded loops with a reassuring comment instead of a counter.
- LangGraph / LangChain types leaking into `domain/`.
- Retrying into a rate limit instead of waiting it out, and burning the daily quota on retries.
- Hardcoding a model name that will be deprecated next month.

---

## Working agreement

Ship over polish — this project serves a job search, and a public v0.5 beats a perfect unpublished
v1.0. Never fabricate eval numbers. Bounds in code, not comments. Typed LLM boundaries. All
thresholds in `config.py`. When a decision is non-obvious, write the ADR. Honest negative results
are features of this project, not failures.
