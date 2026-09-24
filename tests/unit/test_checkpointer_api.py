"""Smoke-checks the AsyncSqliteSaver API against the installed langgraph
version, so a break in that dependency is caught here in P0 rather than
first discovered while building the agent harness in P7.

AsyncSqliteSaver is an async context manager built on aiosqlite; the graph
that uses it cannot be compiled at import time (see docs/plan-p0-p3.md, Part
A §3) — it must be opened inside `async with` and closed when the request
scope ends.
"""

from __future__ import annotations

from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver


async def test_async_sqlite_saver_opens_on_memory() -> None:
    async with AsyncSqliteSaver.from_conn_string(":memory:") as saver:
        assert saver is not None
        # Minimal checkpointer protocol surface this project relies on.
        assert hasattr(saver, "aput")
        assert hasattr(saver, "aget_tuple")
        assert hasattr(saver, "alist")
