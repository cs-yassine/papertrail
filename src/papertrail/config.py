"""Application settings. Every threshold lives here; no magic numbers elsewhere."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Typed, env-driven configuration.

    Model identities (``model_*``) and the provider key have no default: an
    unset value fails at startup via pydantic's validation, rather than
    silently falling back to a hardcoded model name (CLAUDE.md rule 9 — no
    model name is ever hardcoded). Numeric thresholds may default, since the
    rule is specifically about model identities drifting unnoticed, not about
    every field requiring an explicit value.
    """

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="forbid")

    # --- Provider (Groq-only; see docs/costs.md) ---
    groq_api_key: str

    # --- Model routing — no defaults anywhere; real IDs in docs/costs.md ---
    model_large: str
    model_small: str
    model_judge: str
    model_fallback: str

    # --- Embeddings ---
    embedding_model: str
    embedding_dim: int = 384

    # --- Neo4j ---
    neo4j_uri: str
    neo4j_user: str
    neo4j_password: str
    neo4j_database: str = "neo4j"

    # --- Local storage ---
    sqlite_path: Path = Path("var/papertrail.sqlite")
    checkpoint_path: Path = Path("var/checkpoints.sqlite")

    # --- Retrieval ---
    retrieval_k: int = 8
    retrieval_overfetch: int = 4
    rrf_k: int = 60
    expand_enabled: bool = True
    expand_max_hops: int = 1
    expand_min_score: float = 0.60
    gate_min_relevant: int = 2
    prefilter_min_score: float = 0.50

    # --- Agent bounds ---
    max_steps: int = 8
    max_revisions: int = 1
    max_expansions: int = 1

    # --- Budget envelope ---
    # PROVISIONAL: sized for non-reasoning models. Phase 1's live audit
    # (`make audit-budgets`) re-derives the whole envelope against gpt-oss's
    # reasoning-token overhead — do not treat these as final until it has run.
    budget_max_input_tokens: int = 14_000
    budget_max_output_tokens: int = 1_800  # PROVISIONAL — see docstring above
    budget_max_llm_calls: int = 8
    budget_max_cost_usd: float = 0.01
    budget_deadline_s: int = 30

    # --- Observability — optional, never load-bearing ---
    langfuse_public_key: str | None = None
    langfuse_secret_key: str | None = None
    langfuse_host: str | None = None

    # --- Eval ---
    eval_smoke_size: int = 10


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide cached Settings instance.

    Required fields are populated from the environment / ``.env``, not from
    this call site; the pydantic mypy plugin (see pyproject.toml) teaches
    mypy that ``Settings()`` is valid despite the fields having no
    constructor defaults.
    """
    return Settings()
