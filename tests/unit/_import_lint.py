"""Reusable AST-based import checker, shared by the real boundary tests and the
planted-fixture test that proves the checker itself isn't vacuously green.

Deliberately allowlist-based, not denylist-based: anything not explicitly
permitted is a violation, so a new infra dependency can't slip into a
boundary-controlled package unnoticed.

Matching is by dotted prefix, not just the top-level module name. A flat
top-level check can't tell ``papertrail.domain.x`` apart from
``papertrail.llm.x`` — both would reduce to the single root ``papertrail``.
Allowlist entries are matched against the *full* dotted import path: an entry
``e`` matches an import ``m`` when ``m == e`` or ``m`` starts with ``e + "."``.

Known limitation (not silently overclaimed): this only sees static
``import`` / ``from ... import`` statements. A dynamic import built from a
string (``__import__(name)``, ``importlib.import_module(name)`` where
``name`` isn't a literal) is invisible to it. ``importlib`` itself is banned
from the checked packages specifically to close the most obvious version of
that hole.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import NamedTuple


class Violation(NamedTuple):
    file: Path
    module: str
    line: int


def imports_of(path: Path) -> set[str]:
    """Return the full dotted module path of every import in a single .py file.

    Relative imports (``from . import x``) are omitted: they're always
    within the same package and can never cross a boundary.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                modules.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.level > 0 or not node.module:
                continue
            modules.add(node.module)
    return modules


def iter_py_files(root: Path) -> list[Path]:
    return sorted(p for p in root.rglob("*.py") if "__pycache__" not in p.parts)


def _matches(module: str, allowlist: set[str]) -> bool:
    return any(module == entry or module.startswith(entry + ".") for entry in allowlist)


def find_violations(
    root: Path,
    allowlist: set[str],
    *,
    ban: frozenset[str] = frozenset({"importlib"}),
) -> list[Violation]:
    """Flag every import under ``root`` not covered by ``allowlist``.

    ``ban`` entries are removed from the allowlist even if they'd otherwise
    match (e.g. ``importlib`` is stdlib but explicitly excluded).
    """
    effective_allowlist = {entry for entry in allowlist if entry.split(".")[0] not in ban}
    violations: list[Violation] = []
    for file in iter_py_files(root):
        tree = ast.parse(file.read_text(encoding="utf-8"), filename=str(file))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    module = alias.name
                    if module.split(".")[0] in ban or not _matches(module, effective_allowlist):
                        violations.append(Violation(file, module, node.lineno))
            elif isinstance(node, ast.ImportFrom):
                if node.level > 0 or not node.module:
                    continue
                module = node.module
                if module.split(".")[0] in ban or not _matches(module, effective_allowlist):
                    violations.append(Violation(file, module, node.lineno))
    return violations
