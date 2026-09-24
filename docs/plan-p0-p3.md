# PaperTrail — Implementation Plan, Phases 0.5–3

> Status: **approved with changes** (2026-09-23). This revision applies the four requested changes and
> the answers to the rebuild-risk questions. It supersedes the draft at `plan.md`.
> Inputs: `PAPERTRAIL_MASTER_CONTEXT.md` (spec) and `CLAUDE.md` (operating manual; wins on conflict).
> Verification: both files read in full, plus four read-only web searches (sources at the end).
> No live provider console was read. Every throughput figure below is an **estimate** until measured.

## Changelog from the draft

| # | Change | Where |
|---|---|---|
| 1 | Spike rewritten: 10 papers, extraction via the API in a throwaway notebook, label only the neighbours of ~20 chosen anchor claims | Phase 0.5 |
| 2 | Explicit linking-cost levers with a trigger defined in advance. P2's gate is now N=30; scaling to the target N happens in P3, **after** the projection, so a cut to 60 papers wastes no ingestion quota | P2, P3 |
| 3 | ADR-0004 (soft delete via `status`) assigned to P2, with a supersede-on-re-extraction flow | P2 |
| 4 | Platform: the placeholder in the approval message was not filled in. This session runs on **Windows 11**, so WSL2 applies | P0, Part D |
| — | Answers to (a)1–(a)6 applied throughout; recorded in Part D | all |

---

## Part A — The three verifications

### 1. Model names

> **Superseded 2026-09-24.** This section originally recorded a proposal from secondary sources,
> confidence-rated, pending a live console read. That read has now happened — see `docs/costs.md`
> for the full console output. The verdict below is the resolution, not another proposal.

**What the live consoles actually said (`docs/costs.md`, read 2026-09-24):**

- Groq free tier confirms three usable chat models, each its own bucket: `openai/gpt-oss-120b`,
  `openai/gpt-oss-20b`, `qwen/qwen3.8-27b`. All three: ~30 RPM / 1K RPD / **8K TPM** / 200K TPD,
  **per model**, not pooled — **~600K tokens/day total** across the three.
- **Google AI Studio is unavailable for this project.** Configuring the project returns *"L'accès à
  l'API de ce projet est limité. Veuillez configurer la facturation pour continuer."* — billing is
  required before any free-tier access is granted at all, so there is no Gemini fallback to design
  around. **The system is Groq-only.** This resolves decision (a)3 below and removes the
  cross-provider fallback design from every phase.

| Env var | Resolved value | Role |
|---|---|---|
| `MODEL_LARGE` | `openai/gpt-oss-120b` | EXTRACTION (pinned, no fallback), SYNTHESIZE, CRITIQUE |
| `MODEL_SMALL` | `openai/gpt-oss-20b` | REWRITE, PLAN, GRADE, ADJUDICATE (primary) |
| `MODEL_JUDGE` | `qwen/qwen3.8-27b` | EVAL_JUDGE only — pinned, temp 0, **never used for generation** |
| `MODEL_FALLBACK` | `qwen/qwen3.8-27b` | Third bucket; ADJUDICATE only, records `adjudicated_by` |

Reasoning effort per task (`low`/`medium`) is still a guess until `make audit-budgets` runs in P1 —
that part of the original uncertainty stands.

**Judge independence, a documented compromise (not a gap to quietly work around):** MODEL_JUDGE and
MODEL_FALLBACK are the same model. With Gemini gone, judge/generator separation rests on
`qwen3.8-27b` being a different vendor and training lineage from the `gpt-oss` family — weaker than
cross-provider independence. Non-negotiable consequences, carried into P5/P6 even though those
phases aren't detailed in this document: eval runs assert **generator ≠ judge per item**, and any
item where ADJUDICATE's fallback resolved to `qwen3.8-27b` mid-eval-construction is excluded and
counted separately, never silently scored. The README's limitations section says this plainly.

> ⚠ The **8k TPM** limit binds before RPM or TPD does. One extraction call is ~3–5k tokens including
> reasoning, so Groq allows about 2 extraction calls per minute per bucket. The spec's
> `max_concurrency=4` buys nothing on Groq — set concurrency to 1–2.

### 2. Are they reasoning models? Yes, both gpt-oss models are. Gemini Flash can also "think".

Groq counts hidden reasoning tokens against `max_completion_tokens`. This is the Lore incident. What changes:

- **`max_tokens` is set per task in `config.py`** (`MAX_TOKENS_EXTRACTION`, `MAX_TOKENS_ADJUDICATE`, …).
  Each value is reasoning headroom plus output, not output alone. Initial values come from
  `scripts/audit_token_budgets.py`: p95(reasoning + output) × a safety factor, measured on real
  prompts. There is no global default, and nothing is sized by instinct.
- **`reasoning_effort` is set per task in config.** Small tasks run at `low`. It is the biggest lever
  on both empty completions and TPD use.
- **The non-empty assert checks content, not HTTP success or token count.** After every call,
  `llm/client.py` classifies the result:
  - `content.strip()` is empty and `finish_reason == "length"` → **`ReasoningBudgetExhaustedError`**
    (a subclass of `EmptyCompletionError`). This is a **sizing bug, not a transient error**. Retrying
    with the same parameters spends the same tokens and fails the same way, so it is **never retried
    as-is**. It gets exactly one escalation (`max_tokens × REASONING_ESCALATION_FACTOR`, bounded in
    config) and then raises.
  - Empty content with any other finish reason → `EmptyCompletionError`, which may fall back to the
    other **model** (single-provider system; not a cross-provider fallback) **where the task allows
    it** (not EXTRACTION; see (a)3). It is logged loudly because it always means something is wrong.
  - Non-empty content that fails to parse → the structured repair path (one attempt).
- **Reasoning tokens count against the 200k TPD.** The rate limiter and budget read
  `usage.completion_tokens_details.reasoning_tokens` when present and record it separately. It feeds
  the list-price cost column and throughput sizing.
- ⚠ **Knock-on problem in the spec:** `BUDGET_MAX_OUTPUT_TOKENS=1800` per *request* was sized for
  non-reasoning models. With gpt-oss, a single synthesis call could use most of it, and every request
  would degrade. The audit must re-derive the budget envelope too. The envelope stays in config; its
  defaults change.
- The same applies to Gemini: thinking budgets are set explicitly per task, and the same assert runs
  on both providers.

### 3. Is `AsyncSqliteSaver` the right API? Yes, with two caveats.

`langgraph.checkpoint.sqlite.aio.AsyncSqliteSaver.from_conn_string(path)` exists (since v1.0 of the
package). It is an **async context manager** built on `aiosqlite`, and it is the right choice for
`astream`.

- **Consequence:** the graph cannot be compiled at import time as in spec §5.5. It is compiled inside
  `async with` in the FastAPI lifespan or in the harness, and the connection must be closed. The docs
  warn that otherwise the graph "hangs".
- The docs call it unsuitable for production writes. That's fine here: with
  `thread_id = f"{session_id}:{request_id}"` (correction #3), checkpoints are only for debugging.
- **In P0**, pin `langgraph` and `langgraph-checkpoint-sqlite` in `uv.lock`, and add one test that
  opens the saver on `:memory:`. It checks the API against the installed version, so a break isn't
  first found in P7.

---

## Part B — Cross-cutting design decisions (decided now, ADR'd in P1)

### B1. How the Budget reaches `llm/client.py` (correction #6): a `contextvar`, failing closed

- `domain/budget.py`: a pure `Budget` model (limits, counters, arithmetic; no I/O).
- `llm/budget.py`: `_current_budget: ContextVar[BudgetLedger | None]`, a `budget_scope()` context
  manager, and an `asyncio.Lock`-guarded `reserve` / `commit`.
- The client calls `current_budget().reserve(est_input, max_tokens)` **before** any network call.
  With no scope set, it raises `BudgetScopeMissingError`. There is no silent unbudgeted mode.
- **Why not `RunnableConfig`:** every call site would have to thread `config=` through by hand. One
  forgotten site means an unbudgeted call, which is Lore's lesson about resilience at one call site
  not extending to the next. A contextvar fails closed at the one place every call passes through.
- **Caveats:**
  - asyncio tasks copy the context, so the var holds a **mutable ledger reference**. Children mutate
    the shared ledger and never re-`set` the var.
  - Sync LangGraph nodes run in executors, so agent nodes will be `async`.
  - The ledger's lock makes `abatch` concurrency safe.
- **Who opens the scope:** the harness does it per request (P7); ingestion does it per paper (P2);
  linking does it per anchor claim (P3).

### B2. The LLM call pipeline

Each call goes through:

```
budget.reserve → cache.lookup → ratelimit.acquire → provider call → header ingest
  → classify (empty / length / ok) → cache.store → budget.commit → callback
```

A **per-provider guarded runnable** wraps each model, and `RunnableWithFallbacks` spans the guarded
runnables. Fallback is **enabled per task in config** (`FALLBACK_ENABLED_<TASK>`), and EXTRACTION's
is off (decision (a)3).

### B3. Rate limiting — `llm/ratelimit.py` (first-class)

- Sliding windows for RPM and TPM, plus day counters for RPD and TPD, keyed by `(provider, model)`.
  Day counters **persist in SQLite**, so a multi-day ingest survives restarts.
- Before each call, the limiter **waits** if the estimated tokens would breach TPM or RPM.
- It raises `QuotaExhaustedError` (no wait) when RPD or TPD are exhausted. The router falls back only
  where the task allows it; otherwise the error propagates, and `ingest.py` exits 0 with a resume hint.
- On a 429 it honours `retry-after`:
  - wait ≤ `RATELIMIT_MAX_INLINE_WAIT_S` → sleep and retry. This counts toward the cap of 3 and is
    **not** tenacity's exponential backoff;
  - longer wait → `QuotaExhaustedError`, and **no retry is spent**.
- Tenacity handles only 5xx and network errors.
- Response headers (`x-ratelimit-remaining-*`, `retry-after`) are captured through a custom
  `httpx.AsyncClient` with a response event hook, passed to `ChatGroq(http_async_client=...)`.
  **Uncertain:** that ChatGroq honours this parameter in the installed version. Test it in P1 before
  relying on it. Gemini does not expose these headers through LangChain, so it uses local accounting
  plus 429 parsing.

### B4. Cache — `llm/cache.py`

- **Key:** sha256 of (provider, model, params including `reasoning_effort` and `max_tokens`,
  messages, schema, `prompt_version`).
- **Value:** raw response, usage, `served_by`, timestamp. Stored in SQLite under `var/`.
- **Modes:**
  - `read_write`: dev and ingest.
  - `replay_only`: CI. A miss raises `CacheMissError("re-record locally")` (correction #14).
  - `off`.
- **The cache doubles as the Aura backup.** If AuraDB Free is deleted, rebuilding the graph from cache
  spends zero quota.

---

## Part C — Phases

### Phase 0.5 — Contradiction spike (before Phase 0, run by the project owner)

**Purpose:** test whether cosine top-5 candidate generation surfaces real contradictions, the
premise behind the whole product, before any repo code exists. It also gives P3's levers the data
they need.

**Rules for the spike**
- A throwaway notebook **outside the repo**. Rule 4 governs repo code, so calling a provider SDK
  directly is fine here.
- $0: a free-tier Groq key, no card, local embeddings.
- Even here, check for the Lore trap: give `max_tokens` generous headroom, and **assert non-empty
  content** on every extraction call. Record `usage`, including reasoning tokens.
- **Write the go/no-go thresholds down before looking at any neighbours.** Thresholds fixed after
  seeing the data aren't a test.

**Steps (~90 min)**

| Step | Time | What |
|---|---|---|
| 1. Pick 10 papers | 15 min | ~6 anchors forming ≥3 known contested pairs across ≥2 topics, plus ~4 same-topic non-anchor papers as distractors, so neighbours aren't all anchors. Candidate anchor pairs (**verify the arXiv IDs yourself**): Wei et al. 2022 *Emergent Abilities of LLMs* ↔ Schaeffer et al. 2023 *Are Emergent Abilities a Mirage?*; Wei et al. 2022 *Chain-of-Thought Prompting* ↔ Turpin et al. 2023 *Language Models Don't Always Say What They Think* / Lanham et al. 2023 *Measuring Faithfulness in CoT*; Xu et al. 2023 *Retrieval Meets Long Context LLMs* ↔ Li et al. 2024 *RAG or Long-Context LLMs?* |
| 2. Fetch text | 10 min | arXiv API abstract; add the conclusion if `arxiv.org/html/{id}` is easy to parse. Record which papers are abstract-only |
| 3. Extract via API | 10 min | ~10 calls (one per paper) on the likely extraction model, e.g. `gpt-oss-120b` at `low`. Use a draft of the spec §5.3 prompt **with a concepts field**, since (a)4 folds concepts into extraction. Record tokens per call: this is the first real sizing data point |
| 4. Embed + neighbours | 10 min | bge-small-en-v1.5 locally; for each claim, top-5 cross-paper neighbours by cosine, keeping the score and rank |
| 5. Choose ~20 anchor claims | 5 min | ~12 **expected-counterpart** claims (from the contested pairs, where you expect an opposing claim in the partner paper) and ~8 **controls** (claims you expect to have no contradiction) |
| 6. Label | 40 min | Only the top-5 neighbours of the ~20 anchors (~100 pairs): CONTRADICTS / SUPPORTS / NEITHER. For each expected-counterpart anchor, record the **rank and cosine** of the real counterpart if it appears |

**Outputs, carried into the repo** (written to `docs/spike-contradictions.md` in P0, so the evidence
is committed):

| Output | Used by |
|---|---|
| Go / no-go verdict | Whether P2 proceeds with the current candidate design |
| **Recall:** expected-counterpart anchors whose real counterpart is in the top-5 | Go/no-go |
| Distinct real CONTRADICTS pairs found | Go/no-go |
| **Rank distribution** of found counterparts | Guard for P3 lever L1 (5 → 3 candidates) |
| **Lowest cosine** at which a real contradiction appeared | Initial `LINK_MIN_SIM`, and `LINK_MIN_SIM_CEILING` for lever L2 |
| Tokens per extraction call, incl. reasoning; any empty completions | Early sizing; P1 audit baseline |
| False-positive feel from the controls | Adjudicator prompt design in P3 |

**Proposed go/no-go** (the project owner may change the numbers, **before** running):

- **GO** if ≥ 8 of ~12 expected-counterpart anchors have a real contradiction in the top-5, **and**
  ≥ 5 distinct real CONTRADICTS pairs are labelled.
- **NO-GO, low recall:** redesign candidate generation (e.g. concept-bucketed candidates, or a
  second fulltext leg) before P2 locks the schema.
- **NO-GO, recall fine but few real contradictions:** a corpus/section problem. Widen the sections
  or revisit the topics before P2.

**What the spike cannot tell you:** the corpus-wide contradiction rate. Anchors are chosen to be
contested, so the count is biased upward and does not extrapolate linearly to 100 papers. It tests
whether the mechanism can find contradictions, not how many a random corpus has. The curated
manifest (anchors first) is what makes P3's ≥15 plausible.

---

### Phase 0 — Scaffold (native Windows, no WSL — superseded from the original WSL2 plan, see (a)1)

**Environment steps (before any file is created)**
- Project stays at its current Windows path (`C:\Users\...\Desktop\Documents\work\PaperTrail`); no
  filesystem move.
- Claude Code runs natively on Windows (Git Bash + PowerShell tool access), not from inside WSL.
  `make` and `uv` must resolve in that environment — `uv` installed via the official Windows
  installer; `make` availability verified explicitly rather than assumed (Git Bash does not ship it).
- Docker: **Docker Desktop for Windows**, confirmed working (`docker compose version` succeeds).
  No WSL-integration-specific path-translation risk here since the Neo4j service needs no
  host bind-mounts (see the CI-divergence list in the approval message for the full risk rundown).
- CI still runs `ubuntu-latest`. Parity is no longer "same OS," so divergence risks (case
  sensitivity, line endings, `make` version skew) are tracked explicitly rather than assumed away.

**Files**

| File | Purpose |
|---|---|
| `pyproject.toml` / `uv.lock` | Python 3.12, pinned deps (no `ragas`, per correction #16), ruff, mypy strict, pytest-asyncio config |
| `Makefile` | `dev check test test-int` now; other targets fail loudly with "not yet implemented (Pn)" |
| `.gitattributes` | `* text=auto eol=lf`, so no CRLF reaches the Makefile or shell scripts |
| `docker-compose.yml` | `neo4j:5` with a healthcheck, for dev and integration tests |
| `.github/workflows/ci.yml` | ruff → mypy → unit → integration (Neo4j service container); no secrets |
| `.pre-commit-config.yaml` | ruff, mypy, and a secret-pattern check |
| `.env.example` | Every config key, no values |
| `.gitignore` | `.env`, `var/`, caches |
| `src/papertrail/**/__init__.py` | Package skeleton per spec §7.3, one-line module docstrings |
| `src/papertrail/config.py` | `Settings(BaseSettings)` skeleton; no model defaults, so an unset model fails at startup |
| `tests/unit/test_import_boundaries.py` | AST import-lint (see tests) |
| `tests/unit/test_checkpointer_api.py` | Opens `AsyncSqliteSaver` on `:memory:` |
| `tests/integration/test_neo4j_up.py` | Runs `RETURN 1` against the container |
| `docs/adr/template.md`, `docs/incidents.md`, `docs/costs.md` | `costs.md` records the console readings, dated |
| `docs/spike-contradictions.md` | Phase 0.5 results, written by the project owner |
| `README.md` | Stub with non-goals |

**Interfaces**

```python
class Settings(BaseSettings): ...          # fields only
def get_settings() -> Settings: ...
# test helper
def imports_of(path: Path) -> set[str]: ...
```

**Tests, and what each would fail to catch**

| Test | Proves | Would fail to catch |
|---|---|---|
| `test_domain_imports_allowlist` | Every `domain/*.py` import is stdlib, `pydantic`, `typing_extensions` or `papertrail.domain`. It uses an **allowlist, not a denylist**, so a new infra dependency can't slip in unlisted. It also bans `importlib` inside `domain/` | Dynamic imports built from strings outside the banned `importlib` path |
| `test_provider_sdks_only_in_llm` | `groq`, `google.genai`, `google.generativeai`, `langchain_groq` and `langchain_google_genai` appear only under `llm/` | The same dynamic-import hole |
| `test_import_lint_detects_violation` | Runs the checker on a planted bad fixture, so the lint is not vacuously green | — |
| `test_checkpointer_api` | The saver API matches the installed version | Concurrency behaviour under `astream` (P7) |
| `test_neo4j_up` | Container reachable | Aura-specific behaviour |

**Acceptance gate**

- From a fresh clone **inside WSL**, `make check` and `make test` pass.
- `make test-int` passes against dockerized Neo4j.
- The public GitHub repo shows a green CI run on `main`.
- Planting `import neo4j` in `domain/` turns `make test` red.
- The spike results are committed in `docs/spike-contradictions.md`.

**Estimate:** 2.5h (the spec says 1.5).
**Least sure:** whether `make` (installed separately by the project owner, not by this session)
actually resolves in the same shell environment Claude Code's tools use — flagged explicitly rather
than assumed; and whether the Chocolatey-distributed GNU Make has any behavioural gaps against
Ubuntu's for the constructs used here.

---

### Phase 1 — LLM core

**Files**

| File | Purpose |
|---|---|
| `domain/failures.py` | `PaperTrailError` hierarchy |
| `domain/budget.py` | Pure `Budget` and `Usage` models plus arithmetic |
| `domain/tasks.py` | `Task` enum (REWRITE, PLAN, GRADE, ADJUDICATE, EXTRACTION, SYNTHESIZE, CRITIQUE, EVAL_JUDGE) |
| `llm/ratelimit.py` | Windows, persisted day counters, header ingest, wait-vs-raise |
| `llm/cache.py` | Record/replay store |
| `llm/budget.py` | Contextvar ledger, reserve/commit |
| `llm/client.py` | Guarded runnable implementing the B2 pipeline |
| `llm/router.py` | `Task` → `ModelSpec` per provider (from config) → `RunnableWithFallbacks`, with fallback toggled per task |
| `llm/structured.py` | `call_structured[T]` with exactly one repair attempt |
| `llm/callbacks.py` | Records model, `served_by`, tokens (incl. reasoning), latency, list-price-equivalent cost |
| `llm/tokens.py` | Cheap input-token estimate for `reserve` (char heuristic, reconciled with real usage at commit) |
| `scripts/audit_token_budgets.py` | Runs each audited task's prompt on N samples live, on **every candidate provider**; prints p50/p95 reasoning+output tokens, empty-completion count, and the recommended `max_tokens` and envelope |
| `tests/unit/llm/fakes.py` | `FakeChatModel` scripted with responses, usage, headers and exceptions |
| `docs/adr/0008-budget-propagation-contextvar.md` | Decision B1 |
| `docs/adr/0009-rate-limit-wait-not-retry.md` | Decision B3 |
| `docs/adr/0010-reasoning-model-token-sizing.md` | Part A §2 |
| `docs/adr/0012-extraction-sizing-and-concepts.md` | Whether concepts stay folded into extraction, decided from audit output. (Renamed from "extraction-provider-pin" — that question is closed, see below) |
| `docs/adr/0014-single-provider-with-retained-abstraction.md` | Why P1 still builds and unit-tests `RunnableWithFallbacks` against a `FakeChatModel` even though only Groq is live: it's a learning goal for this project and the concrete defense against Groq itself deprecating a model line (as it already did to Llama), not dead weight. Ships wired to one provider; the seam is proven, not exercised, against a second one |

**What the P1 audit must answer** (from decision (a)4; (a)3 — provider pin — is now closed, see
Part A §1)

Only EXTRACTION and ADJUDICATE are audited now; they are the only tasks P0–P3 use. The other tasks
are audited when their prompts exist (P7/P8). The prompts are drafts at this point, so the audit is
**re-run at the start of P2** once the extraction prompt is final.

1. **Extraction sizing on the pinned model.** Run the same N papers (reuse the spike's 10) through
   `MODEL_LARGE` (`gpt-oss-120b`, the only candidate — no provider comparison needed now). Record:
   - tokens per paper, including reasoning;
   - empty-completion and parse-failure counts;
   - the claim count and a quick look at claim quality;
   - **days to extract 100 papers under Groq's measured 200K TPD for this model's bucket**, cross-checked against `docs/costs.md`'s projection.

   Feeds `MAX_TOKENS_EXTRACTION` and the reasoning-effort choice in config, recorded in ADR-0012.
2. **Concepts cost.** Run the extraction prompt with and without the concepts field. Record the p95
   output+reasoning delta. **Decision rule:** if the with-concepts p95 fits inside
   `MAX_TOKENS_EXTRACTION` and the per-paper envelope, keep concepts folded in. Otherwise split
   concepts into their own call, recorded in ADR-0012.
3. **ADJUDICATE tokens per call** with 5 candidates and with 3 candidates, on `MODEL_SMALL`. This
   feeds the P3 projection and lever L1.

**Interfaces**

```python
# domain/failures.py
class PaperTrailError(Exception): ...
class RetriableLLMError(PaperTrailError): ...
class QuotaExhaustedError(PaperTrailError):  provider: str; model: str; resets_at: datetime | None
class EmptyCompletionError(PaperTrailError): finish_reason: str | None
class ReasoningBudgetExhaustedError(EmptyCompletionError): ...
class StructuredParseError(PaperTrailError): ...
class BudgetExceeded(PaperTrailError): ...
class BudgetScopeMissingError(PaperTrailError): ...
class CacheMissError(PaperTrailError): ...

# domain/budget.py
class Usage(BaseModel): input_tokens: int; output_tokens: int; reasoning_tokens: int = 0
class Budget(BaseModel):
    def would_exceed(self, est_input: int, max_output: int) -> str | None: ...
    def add(self, usage: Usage, list_cost_usd: float) -> "Budget": ...

# llm/budget.py
@contextmanager
def budget_scope(budget: Budget) -> Iterator[BudgetLedger]: ...
def current_budget() -> BudgetLedger: ...                      # raises BudgetScopeMissingError
class BudgetLedger:
    async def reserve(self, est_input: int, max_output: int) -> Reservation: ...  # raises BudgetExceeded
    async def commit(self, r: Reservation, usage: Usage) -> None: ...

# llm/ratelimit.py
class RateLimiter:
    def __init__(self, store_path: Path, limits: Mapping[ModelKey, Limits]) -> None: ...
    async def acquire(self, key: ModelKey, est_tokens: int) -> None: ...   # waits or raises QuotaExhaustedError
    def observe_headers(self, key: ModelKey, headers: Mapping[str, str]) -> None: ...
    def record(self, key: ModelKey, usage: Usage) -> None: ...
    def on_429(self, key: ModelKey, retry_after_s: float | None) -> float: ...  # wait, or raises QuotaExhaustedError

# llm/cache.py
class CacheMode(StrEnum): READ_WRITE = ...; REPLAY_ONLY = ...; OFF = ...
class LLMCache:
    def key(self, spec: ModelSpec, messages: Sequence[BaseMessage],
            schema: type | None, prompt_version: str) -> str: ...
    def get(self, key: str) -> CachedResponse | None: ...
    def put(self, key: str, resp: CachedResponse) -> None: ...

# llm/client.py
class GuardedChatModel(Runnable[LanguageModelInput, AIMessage]): ...   # one per provider/model

# llm/router.py
def get_model(task: Task) -> Runnable[LanguageModelInput, AIMessage]: ...   # guarded; fallbacks iff enabled for task

# llm/structured.py
async def call_structured(task: Task, prompt: ChatPromptTemplate, inputs: Mapping[str, Any],
                          schema: type[T], *, prompt_version: str) -> T: ...
```

**Tests** (fake model, no network)

| Test | Would fail to catch |
|---|---|
| 429 with `retry-after: 2` → one wait, then success; fake clock shows ≥2s and exactly 2 calls | Real Groq header formats if they differ from the fixture (covered by one live check in the audit script) |
| 429 with `retry-after: 3600` → `QuotaExhaustedError`, **zero** retries, fallback provider called (for a fallback-enabled task) | Whether real Gemini 429s parse the same way |
| Same, for EXTRACTION → `QuotaExhaustedError` propagates, **fallback never called** | — |
| TPM window full → `acquire` waits instead of calling | Clock skew against Groq's server-side window |
| Day counters persist: a new `RateLimiter` on the same file still refuses | Groq's actual reset semantics (rolling vs UTC midnight) |
| Bad JSON → one repair call with the error fed back → success; bad twice → `StructuredParseError` | Semantic garbage that is valid JSON |
| Budget near the limit → `BudgetExceeded` raised and the **fake's call count is 0** (proves before-call) | Estimate error: a reservation passes but actual use overshoots. `commit` logs the overshoot |
| No `budget_scope` → `BudgetScopeMissingError` | — |
| Budget visible and shared inside `abatch(max_concurrency=4)` through `RunnableWithFallbacks`; counters sum correctly | Propagation through LangGraph executors (P7 test) |
| Empty content + `finish_reason=length` → exactly one escalation, then `ReasoningBudgetExhaustedError`; **never** a same-parameter retry | Whether real empty outputs always carry `length` (the audit checks this live) |
| Empty content otherwise → `EmptyCompletionError` → fallback where enabled | — |
| Cache hit → zero provider calls; `REPLAY_ONLY` miss → `CacheMissError` | A key missing an output-changing parameter (a property test asserts every `ModelSpec` field changes the key) |
| `served_by` recorded on fallback | — |
| No model-name literal in `src/` (grep test for `gpt-oss`, `gemini-`, `llama`) | Names built by string concatenation |

**Acceptance gate**

- The spec's four: retry on 429, repair on bad JSON, `BudgetExceeded`, empty completion raises.
- Also: the rate limiter waits instead of retrying, cache replay misses fail, EXTRACTION never falls
  back, and the import-lint and model-name grep tests are green.
- `make check` is green.
- **`make audit-budgets` has been run live once.** Its output is committed to `docs/costs.md` with
  the date: per task and provider, reasoning-token p95, recommended `max_tokens`, recommended
  envelope, concepts delta, and ADJUDICATE tokens at 5 and 3 candidates.
- ADR-0012 is written: the extraction pin chosen from the audit table, and the concepts decision.

**Estimate:** 7.5h (the spec says 3; +0.5 for the two-provider audit).

**Least sure:**
- whether `ChatGroq` accepts an injected `httpx.AsyncClient` and returns `reasoning_tokens` in
  `usage_metadata` in the installed version. If it doesn't, fall back to local accounting only (a
  documented limitation, not a rewrite);
- whether `with_structured_output` on gpt-oss via Groq uses JSON-schema mode or tool calling, and how
  that interacts with reasoning.

---

### Phase 2 — Ingestion (resumable; gate at N=30)

**Sequencing change:** P2 is accepted at **N=30**. Scaling to the target corpus (100, or 60 if lever
L3 fires) happens in P3, after the linking-cost projection. That way a cut to 60 papers wastes no
ingestion quota on papers 61–100.

**Deliberate deviation from the spec:** the embedder (`retrieval/embedder.py`: local bge-small on
CPU, free, with `CacheBackedEmbeddings`) and schema/index creation move forward from P3/P4 into P2.
P3's candidate search needs both. This pulls scope forward; it is not a refactor.

**Files**

| File | Purpose |
|---|---|
| `data/corpus_manifest.jsonl` | **Curated, committed** (decision (a)6). arXiv IDs, topic tag and an `anchor: bool` flag. **Ordered anchors first**, so any prefix cut (lever L3) keeps the contested papers. Seeded from the spike's 10 papers |
| `domain/models.py` | `PaperMeta`, `Section`, `ClaimDraft` (with `concepts: list[str]`, unless ADR-0012 split them), `ClaimDraftList`, `Claim`, `Concept`, `ClaimStatus` (pure) |
| `domain/hashing.py` | `normalize_claim_text`, `claim_content_hash(arxiv_id, text)` (correction #1) |
| `ingestion/arxiv_client.py` | Metadata via the arXiv API, ≥3s between requests per arXiv's terms, httpx |
| `ingestion/fetch_cache.py` | Raw HTML/XML on disk under `var/raw/`, so nothing is fetched twice |
| `ingestion/parser.py` | Tries `arxiv.org/html/{id}` → ar5iv → abstract-only; pulls title, abstract, intro and conclusion; splits with `RecursiveCharacterTextSplitter` |
| `ingestion/claim_extractor.py` | LCEL chain via `call_structured`, pinned to `MODEL_LARGE` (no fallback). Records `extracted_by` (model) and `extraction_prompt_version` on every claim (decision (a)3) |
| `ingestion/schema.py` | Constraints and indexes, idempotent (`IF NOT EXISTS`); uniqueness on `content_hash` |
| `ingestion/writer.py` | One transaction per paper: MERGE Paper, Claims by `content_hash` with `status='active'`, HAS_CLAIM. Re-extraction under a new prompt version marks the paper's old claims **`superseded`** instead of deleting them (ADR-0004). **Then re-reads the counts to verify** (Lore lesson: a 200 is not a write) |
| `ingestion/ledger.py` | Per-paper stage (`fetched → parsed → extracted → written`) and `extraction_prompt_version`, stored on the Paper node |
| `ingestion/pipeline.py` | Runs per paper under `budget_scope(per_paper_budget)`; skips done papers; stops cleanly on `QuotaExhaustedError` |
| `retrieval/embedder.py` | `HuggingFaceEmbeddings` + `CacheBackedEmbeddings(LocalFileStore)` |
| `scripts/ingest.py` | `--limit N --stage {fetch,extract,write,all} --dry-run`; prints a run report (papers done, remaining, tokens by provider, estimated days left) |
| `scripts/rekey_gold.py` | **Stub, per decision (a)2**: a dry-run matcher (below) |
| `scripts/sample_claims.py` | Prints 10 random claims for hand review |
| `docs/reviews/p2_claims.md` | Hand-review verdicts (written by the human, not by Claude) |
| `docs/adr/0001-claims-as-unit.md` | Spec ADR |
| `docs/adr/0002-vectors-in-neo4j.md` | Spec ADR |
| `docs/adr/0003-content-hash.md` | Hash of `arxiv_id + normalized_text` |
| `docs/adr/0004-soft-delete-via-status.md` | **Assigned here.** Claims are never deleted; re-extraction supersedes. Retrieval filters `active` in one place (P4) |
| `docs/adr/0013-extraction-freeze.md` | Decision (a)2: the extraction prompt version and pinned model freeze together with the gold set in P5; any later change requires `rekey_gold.py` + an ADR |

**The re-keying stub, defined so it is not a disguised TODO.** No gold set exists until P5, so the
stub **never writes**. It is working, tested code that proposes a mapping:

```python
class RekeyProposal(BaseModel):
    arxiv_id: str; old_hash: str; new_hash: str | None; similarity: float | None

def propose_rekey(old: Sequence[Claim], new: Sequence[Claim],
                  min_similarity: float) -> list[RekeyProposal]: ...
```

For each paper, it matches each `superseded` claim to its most similar `active` claim from the same
paper by embedding cosine (≥ `REKEY_MIN_SIMILARITY` in config). Unmatched claims get
`new_hash=None`: those gold items would need hand repair. P5 extends it to rewrite
`evals/dataset.jsonl`.

**Interfaces**

```python
def normalize_claim_text(text: str) -> str: ...        # NFKC, casefold, whitespace, trailing punct
def claim_content_hash(arxiv_id: str, text: str) -> str: ...

class ArxivClient:
    async def fetch_metadata(self, ids: Sequence[str]) -> list[PaperMeta]: ...
    async def search(self, query: str, max_results: int) -> list[PaperMeta]: ...

def parse_sections(html: str | None, meta: PaperMeta) -> list[Section]: ...
async def extract_claims(meta: PaperMeta, sections: Sequence[Section]) -> ClaimDraftList: ...

class GraphWriter:
    async def ensure_schema(self) -> None: ...
    async def write_paper(self, meta: PaperMeta, claims: Sequence[Claim]) -> WriteResult: ...  # verifies counts
    async def supersede_claims(self, arxiv_id: str, keep_prompt_version: str) -> int: ...
    async def paper_stage(self, arxiv_id: str) -> PaperStage | None: ...

async def ingest(manifest: Path, limit: int, settings: Settings) -> IngestReport: ...   # returns; never loops on quota
```

**How it resumes, caches, and waits**

- **Target:** local Docker Neo4j is the ingest target (decision (a)5). Aura receives snapshots only.
- **Resume:** `paper_stage == written` with a matching `extraction_prompt_version` → skip, with no
  fetch and no LLM call.
- **Cache:** fetches cache to disk; LLM responses cache by key; embeddings cache by `content_hash`.
- **Wait:** the rate limiter waits within a day. When the pinned extraction provider runs out of
  quota, there is **no fallback**. `ingest.py` prints e.g. `Quota exhausted on <provider>; 43/100
  papers done. Resume: make ingest N=100 (resets ~HH:MM UTC)` and exits 0.
- **Measure first:** re-run the audit on the final extraction prompt, run the first 10 papers, then
  N=30.
- **Estimate (not a measurement):** ~4–6k tokens per paper → 100 papers ≈ 400–600k tokens ≈ 2–3 days
  on one provider's 200k TPD. Pinning extraction to one provider (no fallback) makes this the floor,
  not an optimistic case.

**Tests**

| Test | Would fail to catch |
|---|---|
| Unit: hashing — same text in two papers → two hashes; whitespace/case variants → same hash | Semantically identical claims worded differently (intended) |
| Unit: parser on 3 committed HTML fixtures (arxiv html, ar5iv, missing → abstract-only) | Layout drift on papers unlike the fixtures. The ingest report counts `abstract_only` papers so it's visible |
| Unit: pipeline with a fake LLM that raises `QuotaExhaustedError` at paper 4 → report says 3 done, clean exit; re-run finishes 4–N with **no repeated calls** | Real multi-process races (single process only) |
| Unit: extractor with a fake model — empty list OK; malformed → repair; `extracted_by` set on every claim | Extraction *quality* (only the hand review catches that) |
| Unit: `propose_rekey` — exact match, reworded match above the threshold, no match → `None` | Whether the threshold is right for real re-extractions (unknowable until one happens) |
| Integration (docker Neo4j): `write_paper` twice → identical counts; write verified by an independent `MATCH` count | Aura-specific behaviour |
| Integration: a transaction failing mid-paper leaves no partial claims (paper stays not-`written`) | — |
| Integration: re-extract a paper with a bumped prompt version → old claims `superseded` (still present), new ones `active`; the active count equals the new extraction's count | Downstream consumers forgetting the `active` filter (P4 centralises it) |

**Acceptance gate**

1. The audit has been re-run on the final extraction prompt and committed.
2. `make ingest N=30` run twice → identical `(:Paper)`, `(:Claim)` and `[:HAS_CLAIM]` counts.
3. **The second run makes 0 LLM calls and 0 HTTP fetches**, asserted from the run report.
4. A run killed mid-way and resumed completes without duplicates.
5. Every claim has `extracted_by`, and all values equal the pinned provider.
6. 10 sampled claims hand-reviewed in `docs/reviews/p2_claims.md`.
7. Measured tokens/paper and the projected full-corpus ingest duration recorded in `docs/costs.md`.

**Estimate:** 8h of build time (+0.5 for ADR-0004, supersede and the re-key stub).

**Least sure:**
- section parsing for 2024–26 papers (ar5iv lags; arXiv HTML varies);
- whether ~4–6k tokens/paper holds once reasoning tokens are counted for real.

---

### Phase 3 — Concepts, relation linking, projection, scale-up

**Order of work**

1. Build concept linking and relation linking against the **N=30 graph**.
2. Run the **linking-cost projection** and evaluate the trigger (below). Apply levers if it fires.
3. Scale ingest to the target N (100, or 60 under L3).
4. Link the full corpus.
5. Snapshot to Aura.
6. Gate.

**Files**

| File | Purpose |
|---|---|
| `domain/relations.py` | `Relation` enum (SUPPORTS, CONTRADICTS, NEITHER), `PairVerdict`, `canonical_pair(h1, h2)`, ordered by **`content_hash`**, not UUID (it survives re-extraction; ties to corrections #8 and #9) |
| `domain/concepts.py` | `normalize_concept_name` |
| `domain/projection.py` | Pure linking-cost projection math (below) |
| `ingestion/concept_linker.py` | MERGE Concept and ABOUT from extraction output; `RELATED_TO` by embedding similarity, no LLM |
| `ingestion/candidates.py` | Per claim: vector top-K, **other papers only**, `status=active` post-filtered with overfetch (correction #11), above `LINK_MIN_SIM`, capped at `LINK_CANDIDATES_K` (default 5), **minus pairs already in the pair ledger** |
| `ingestion/relation_linker.py` | One call per claim with all candidates (`MODEL_SMALL`; fallback to `MODEL_FALLBACK` allowed per (a)3, records `adjudicated_by`). Writes one canonical direction; claims shown under neutral labels |
| `ingestion/pair_ledger.py` | Adjudicated unordered pairs (by hash), so B→A is never re-asked after A→B |
| `scripts/project_linking.py` | Evaluates the trigger (below). Makes **zero LLM calls** except an optional `--sample 20` measured adjudication run |
| `scripts/review_relations.py` | Prints N CONTRADICTS pairs with rationale and papers |
| `scripts/audit_adjudicator_order.py` | *Optional, costs quota:* re-asks 20 pairs in reversed order and reports agreement |
| `scripts/snapshot_graph.py` | Exports the local graph to a versioned file and imports it into Aura (and, later, the CI container, per correction #14) |
| `docs/reviews/p3_contradictions.md` | Hand-review verdicts |
| `docs/adr/0005-contradictions-at-write-time.md` | Spec ADR |
| `docs/adr/0011-candidate-generation.md` | Candidate filter, pair ledger, canonical ordering, **the lever policy and which levers fired** |

**Interfaces**

```python
def canonical_pair(a_hash: str, b_hash: str) -> tuple[str, str]: ...

class AdjudicationBatch(BaseModel):
    verdicts: list[PairVerdict]                      # one per candidate index

async def find_candidates(claim: Claim, k: int, min_sim: float) -> list[Claim]: ...
async def adjudicate(anchor: Claim, candidates: Sequence[Claim]) -> AdjudicationBatch: ...
async def link_relations(limit: int | None, settings: Settings) -> LinkReport: ...
async def link_concepts(settings: Settings) -> ConceptReport: ...

# domain/projection.py
class ProviderQuota(BaseModel): tpd: int; rpd: int
class LinkingInputs(BaseModel):
    claims_per_paper: float; target_papers: int; frac_with_candidates: float
    tokens_per_call: float; quotas: list[ProviderQuota]; utilisation: float
class LinkingProjection(BaseModel):
    calls: int; tokens: int; days_token_bound: float; days_request_bound: float
    @property
    def days(self) -> float: ...                     # max of the two bounds
    @property
    def binding(self) -> Literal["tokens", "requests"]: ...
def project_linking(inputs: LinkingInputs) -> LinkingProjection: ...
```

**Pushback on a spec default:** "parse failure → NEITHER" is fail-open, which is exactly the Lore
failure pattern. NEITHER is kept so the pipeline progresses, but:

- the pair is marked `adjudication_failed`, not `adjudicated`, so it is retried on the next run;
- the count shows in `LinkReport`;
- if the failure rate exceeds `LINK_MAX_FAILURE_RATE`, the run aborts.

#### Linking-cost levers (defined now, evaluated once at a fixed checkpoint)

**Why:** worst case ~800 anchors × ~1–1.5k tokens ≈ 1M tokens ≈ **~5 days on Groq alone** (estimate).
The response is decided now, not mid-ingest.

**Checkpoint:** step 2 of P3's order of work, i.e. after linking code works on the N=30 graph and
**before** scaling ingest. That is the only point where every lever, including the 60-paper cut, is
still free to apply.

**Projection inputs:** all measured, none assumed.

| Input | Source | LLM cost |
|---|---|---|
| `claims_per_paper` | N=30 graph | 0 |
| `frac_with_candidates` | `find_candidates` run over the whole N=30 graph (vector-only) | 0 |
| `tokens_per_call` | 20 real adjudications (`--sample 20`), cross-checked against the P1 audit | ~20 calls |
| `quotas` | `docs/costs.md` console readings for the providers allowed for ADJUDICATE | 0 |
| `utilisation` | config `LINK_QUOTA_UTILISATION` (proposed 0.8, leaving headroom for dev work) | 0 |

Caveat: `frac_with_candidates` grows as the corpus grows (more neighbours clear the threshold). The
projection therefore uses `max(measured, LINK_FRAC_FLOOR)`, proposed 0.8, so it errs pessimistic.

**Trigger:** `projection.days > LINK_MAX_PROJECTED_DAYS`, proposed **3**. That's the project owner's
call; set it in config before the checkpoint.

**Levers, applied in order, re-projecting after each, stopping as soon as the projection is under the
trigger:**

| Lever | Change | Reduces | Guard (from spike data) | Skip when |
|---|---|---|---|---|
| **L1** | `LINK_CANDIDATES_K` 5 → 3 | Tokens per call (input + reasoning) | Only if the spike showed real counterparts **mostly at rank ≤ 3** | The projection is **request-bound**: L1 doesn't change the call count |
| **L2** | Raise `LINK_MIN_SIM` in steps of `LINK_MIN_SIM_STEP` | Call count (anchors with no candidate above the threshold make no call) | Never above `LINK_MIN_SIM_CEILING` = the **lowest cosine at which the spike found a real contradiction** | The ceiling is already reached |
| **L3** | v0.5 corpus = `manifest[:60]` (anchors first) | Anchors, and ingestion too | Anchors are ordered first, so contested papers survive the cut | — |

- **If still over the trigger after L3:** stop and ask the project owner. There is no invented L4.
- **Record every lever that fired**, with before/after projections, in `docs/costs.md` and ADR-0011.
  A lever that cut recall is a candidate "what didn't work" entry for the README.

#### Tests

| Test | Would fail to catch |
|---|---|
| Unit: `canonical_pair` is order-invariant and uses hash, not UUID | — |
| Unit: candidates exclude same-paper and already-ledgered pairs; respect `k` and `min_sim` (fake store) | Cypher bugs (integration covers them) |
| Unit: adjudicator prompt rendering is **byte-identical** whichever claim of a pair is the anchor, apart from the anchor slot | **Whether the real LLM is position-invariant.** Only the optional live audit measures that |
| Unit: wrong verdict count or parse failure → `adjudication_failed` and retryable, not silent NEITHER | — |
| Unit: `project_linking` — token-bound vs request-bound cases; the `binding` property picks the max; the frac floor applies | Whether the inputs are right (they are measured, not tested) |
| Unit: lever policy — L1 skipped when request-bound; L2 stops at the ceiling; after L3, a still-over result returns "ask", not a further change | — |
| Integration: CONTRADICTS written once in canonical direction; `MATCH (a)-[:CONTRADICTS]-(b)` finds it from both ends; re-run creates 0 new edges | — |
| Integration: vector query with `status='superseded'` claims present returns only active ones after overfetch (**local Neo4j**) | Aura's behaviour. **Verified on Aura in P4**, not P11 (decision (a)5) |
| Integration: snapshot export → import into a fresh container → identical node/edge counts | Aura-specific import limits (checked once manually on the real push) |

**Acceptance gate** — after scale-up and full linking:

1. The projection output and the lever decisions (fired or not) are committed in `docs/costs.md`.
2. `MATCH ()-[r:CONTRADICTS]-() RETURN count(DISTINCT r)` ≥ 15.
3. **5 pairs hand-reviewed**, with precision on those 5 reported as-is. If 2 of 5 are false, that is
   recorded, not hidden.
4. Link re-run adds 0 edges and makes 0 LLM calls.
5. `LinkReport` failure rate below threshold.
6. The snapshot is pushed to Aura, and node/edge counts on Aura match local.

**Estimate:** 5.5h of build time (+1.5 for projection, levers and snapshot); days of wall clock.

**Least sure:** whether `frac_with_candidates` measured at 30 papers is a usable predictor at
60–100. That's the reason for the pessimistic floor.

---

### Totals

| Phase | Spec hours | Planned hours |
|---|---|---|
| P0.5 Spike (project owner) | — | 1.5 |
| P0 Scaffold | 1.5 | 2.5 |
| P1 LLM core | 3 | 7.5 |
| P2 Ingestion | 4 | 8 (+ days wall clock) |
| P3 Linking | 2 | 5.5 (+ days wall clock) |
| **Total** | **10.5** | **~25** |

---

## Part D — Decisions recorded

| # | Question | Decision | Lands in |
|---|---|---|---|
| (a)1 | Windows toolchain | **Superseded 2026-09-24: native Windows, not WSL2.** No Ubuntu-on-WSL was installed on this machine (only Docker Desktop's internal distro), and the project owner chose to stay native rather than set one up. The project lives at its original Windows path; `.gitattributes` forces LF; Makefile targets are written to run under Git Bash | P0 |
| (a)2 | Freeze extraction at gold freeze | **Yes.** Prompt version + pinned model freeze with the gold set. `scripts/rekey_gold.py` is a working dry-run stub in P2 | P2 (ADR-0013), P5 |
| (a)3 | Mixed-provider extraction | **Closed 2026-09-24 — moot, not just decided.** Google AI Studio is unavailable for this project (billing required for any free-tier access; see `docs/costs.md`), so there is no second provider to mix. EXTRACTION pins to `MODEL_LARGE` (`gpt-oss-120b`) and waits out quota rather than falling back. ADJUDICATE may fall back to `MODEL_FALLBACK` (`qwen/qwen3.8-27b`) and records `adjudicated_by`. `extracted_by` always recorded. P1 still builds and unit-tests the fallback abstraction against a `FakeChatModel` (ADR-0014) — a defense against Groq itself deprecating a model, and a stated learning goal — but ships wired to one live provider | P1 (ADR-0012, ADR-0014), P2 |
| (a)4 | Concepts folded into extraction | **Yes**, subject to the audit's output-token delta. If it breaks the envelope, split | P1 (ADR-0012) |
| (a)5 | Neo4j source of truth | **Local Docker** as ingest target; Aura is a snapshot. Aura vector post-filter verified in **P4** | P2, P3, P4 |
| (a)6 | Corpus selection | **Curated manifest**, anchors first | P2 |
| (c) | Spike timing | **Before Phase 0**, run by the project owner | P0.5 |

### Still open (small; answer before the phase that needs them)

1. **`LINK_MAX_PROJECTED_DAYS`** (proposed 3) and **`LINK_QUOTA_UTILISATION`** (proposed 0.8). Needed
   by the P3 checkpoint.
2. **Spike thresholds** (proposed: ≥8/12 recall, ≥5 real pairs). Fix them before running the spike.
3. ~~**Platform confirmation.**~~ **Resolved 2026-09-24** — see (a)1: native Windows, no WSL.

## Part E — Riskiest assumption (unchanged)

**That claim-level extraction + top-5 cosine candidates + a *small* reasoning model at low effort
yields ≥15 contradictions that are *real*.**

- The spike (P0.5) tests the candidate half.
- The 5-pair precision in the P3 gate tests the adjudicator half.
- The lever policy guards the cost of finding out.

---

## Sources

- [Groq Free Tier 2026: 1,000 Requests a Day, Llama Is Gone](https://klymentiev.com/blog/groq-pricing)
- [Groq Rate Limits — GroqDocs](https://console.groq.com/docs/rate-limits)
- [Groq Free Tier 2026 — Price Per Token](https://pricepertoken.com/endpoints/groq/free)
- [Groq API Free Tier Limits in 2026 — Grizzly Peak Software](https://www.grizzlypeaksoftware.com/articles/p/groq-api-free-tier-limits-in-2026-what-you-actually-get-uwysd6mb)
- [Reasoning — GroqDocs](https://console.groq.com/docs/reasoning)
- [OpenAI GPT-OSS 120B — GroqDocs](https://console.groq.com/docs/model/openai/gpt-oss-120b)
- [Fix Groq gpt-oss empty completions (GitHub PR)](https://github.com/musatarar/Agentic-Outreach-Planner/pull/143)
- [Make the token budget fit reasoning models (GitHub PR)](https://github.com/andreyshindler/tuya-telegram-control/pull/5)
- [AsyncSqliteSaver — LangChain Reference](https://reference.langchain.com/python/langgraph.checkpoint.sqlite/aio/AsyncSqliteSaver)
- [AsyncSqliteSaver.from_conn_string — LangChain Reference](https://reference.langchain.com/python/langgraph.checkpoint.sqlite/aio/AsyncSqliteSaver/from_conn_string)
- [Gemini API Free Tier Limits — scriptbyai](https://www.scriptbyai.com/gemini-api-free-tier-limits/)
- [Gemini API Free Tier 2026 — pecollective](https://pecollective.com/tools/gemini-free-tier-guide/)
