"""Import boundary enforcement.

``domain/`` must stay pure (no infra: no langchain, no langgraph, no neo4j,
no httpx — CLAUDE.md rule 5). Provider SDKs must be reachable only from
``llm/`` (CLAUDE.md rule 4: no direct provider SDK calls anywhere else).
"""

from __future__ import annotations

import sys
from pathlib import Path

from tests.unit._import_lint import find_violations, imports_of, iter_py_files

SRC = Path(__file__).resolve().parents[2] / "src" / "papertrail"

_STDLIB = set(sys.stdlib_module_names)
DOMAIN_ALLOWLIST = _STDLIB | {"pydantic", "typing_extensions", "papertrail.domain"}

BANNED_PROVIDER_SDKS = {
    "groq",
    "google.genai",
    "google.generativeai",
    "langchain_groq",
    "langchain_google_genai",
}


def _is_banned(module: str) -> bool:
    return any(module == b or module.startswith(b + ".") for b in BANNED_PROVIDER_SDKS)


def test_domain_imports_allowlist() -> None:
    """Every import in src/papertrail/domain/ is stdlib, pydantic,
    typing_extensions, or papertrail.domain itself — nothing from infra.

    This is the live enforcement test: planting `import neo4j` in a real
    file under domain/ makes this fail.
    """
    violations = find_violations(SRC / "domain", DOMAIN_ALLOWLIST)
    assert violations == [], (
        f"domain/ imported something outside its allowlist: {violations}. "
        "domain/ must not import infra (langchain, langgraph, neo4j, httpx, ...)."
    )


def test_provider_sdks_only_in_llm() -> None:
    """groq/google.genai/google.generativeai/langchain_groq/langchain_google_genai
    appear only under src/papertrail/llm/."""
    llm_dir = SRC / "llm"
    offenders: list[tuple[Path, str]] = []
    for file in iter_py_files(SRC):
        if llm_dir in file.parents:
            continue
        for module in imports_of(file):
            if _is_banned(module):
                offenders.append((file, module))
    assert offenders == [], f"Provider SDK imported outside llm/: {offenders}"


def test_import_lint_detects_violation(tmp_path: Path) -> None:
    """The checker itself is exercised against a planted bad fixture, so a
    green `test_domain_imports_allowlist` can't be vacuously green just
    because domain/ currently has almost no code in it."""
    fixture = tmp_path / "bad_module.py"
    fixture.write_text("import neo4j\n", encoding="utf-8")

    violations = find_violations(tmp_path, allowlist=_STDLIB | {"pydantic"})

    assert len(violations) == 1
    assert violations[0].module == "neo4j"
    assert violations[0].file == fixture
