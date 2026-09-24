# PaperTrail

A contradiction-aware GraphRAG research agent over ~300 arXiv papers (cs.CL +
cs.LG) on three contested topics: RAG vs long-context, chain-of-thought
faithfulness, and emergent abilities. Claims — not chunks — are stored in
Neo4j with `SUPPORTS`/`CONTRADICTS` edges between papers; a bounded LangGraph
agent retrieves, grades, optionally expands one hop, synthesizes an answer
with citations to specific claims, and states its own confidence honestly,
including refusing when the evidence doesn't support an answer.

**Status: Phase 0 (scaffold).** No business logic yet — see `CLAUDE.md` for
the phase plan and `docs/plan-p0-p3.md` for how phases 0–3 are sequenced.

## Non-goals (v1)

- **No auth.** The API is public, read-only, and rate-limited — not a
  multi-tenant product.
- **No tool has side effects.** Nothing the agent does can mutate external
  state, which bounds the blast radius of anything going wrong, including a
  prompt injection in retrieved claim text.
- **Not built to scale past this corpus.** ~100–300 papers, one Neo4j
  instance, free-tier LLM quotas. Throughput is measured, not assumed, and
  the project accepts multi-day ingestion rather than paying for capacity.
- **Zero cost, not "cheap."** See `CLAUDE.md` Rule 0. Every design choice
  that trades latency or manual effort for staying free is deliberate.

## A known limitation, stated plainly, not glossed over

The system runs on **one LLM provider (Groq)** — Google AI Studio's free
tier is unavailable for this project (billing required for any access; see
`docs/costs.md`). This means the eval judge (`qwen/qwen3.8-27b`) and the
answer generators (`gpt-oss-120b`/`gpt-oss-20b`) share a provider. Judge
independence therefore rests on `qwen3.8-27b` being a different vendor and
training lineage from the `gpt-oss` family, not on a different provider
entirely — a real, weaker guarantee than cross-provider independence would
have been. Every eval run asserts generator ≠ judge per item and excludes
any item where a fallback made them the same.

## Development

See `CLAUDE.md` for the full operating manual (non-negotiable rules, the
per-phase workflow, and the free-tier constraints that shape the whole
design). In short:

```
make dev        # install dependencies, set up pre-commit
make check      # ruff + mypy --strict
make test       # unit tests (no network, no docker)
make test-int   # integration tests against dockerized Neo4j
```

Every other `make` target listed in `CLAUDE.md`'s Commands section exists as
a stub in this phase and fails loudly with which phase implements it,
rather than doing nothing silently.
