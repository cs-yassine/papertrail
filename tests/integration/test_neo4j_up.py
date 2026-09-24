"""Confirms the dockerized Neo4j container is actually reachable and can run a
query — the lowest bar before anything in ingestion/ or retrieval/ is built.

Deliberately reads NEO4J_URI/NEO4J_USER/NEO4J_PASSWORD straight from the
environment rather than through papertrail.config.Settings: this test must
run standalone (`make test-int`) without requiring every other setting
(GROQ_API_KEY, MODEL_*, ...) to be populated first. The Makefile and CI both
export these three for the fixed, dev-only, non-secret local container
credentials — never real Aura credentials.
"""

from __future__ import annotations

import os

from neo4j import AsyncGraphDatabase


async def test_neo4j_returns_1() -> None:
    uri = os.environ["NEO4J_URI"]
    user = os.environ["NEO4J_USER"]
    password = os.environ["NEO4J_PASSWORD"]

    driver = AsyncGraphDatabase.driver(uri, auth=(user, password))
    try:
        async with driver.session() as session:
            result = await session.run("RETURN 1 AS value")
            record = await result.single()
            assert record is not None
            assert record["value"] == 1
    finally:
        await driver.close()
