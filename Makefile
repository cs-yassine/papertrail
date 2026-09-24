# PaperTrail — Phase 0 scaffold.
#
# Explicit SHELL: GNU Make on Windows sometimes defaults to cmd.exe, which
# breaks the POSIX recipe syntax below. Forcing bash makes recipes behave
# identically under Git Bash (Windows) and CI (ubuntu-latest).
SHELL := bash
.SHELLFLAGS := -eu -o pipefail -c

NEO4J_TEST_USER := neo4j
NEO4J_TEST_PASSWORD := localtestpass123
NEO4J_TEST_URI := bolt://localhost:7687

.PHONY: dev check test test-int \
        ingest eval-smoke eval-full run-api run-ui demo audit-budgets snapshot-graph

## --- Implemented (Phase 0) ---

dev:
	uv sync --all-groups
	uv run pre-commit install

check:
	uv run ruff check src tests
	uv run ruff format --check src tests
	uv run mypy

test:
	uv run pytest tests/unit -q

test-int:
	docker compose up -d neo4j
	@echo "Waiting for Neo4j to become healthy..."
	@i=0; \
	cid="$$(docker compose ps -q neo4j)"; \
	until [ "$$(docker inspect -f '{{.State.Health.Status}}' "$$cid" 2>/dev/null)" = "healthy" ]; do \
		i=$$((i + 1)); \
		if [ "$$i" -ge 60 ]; then \
			echo "Neo4j did not become healthy in time" >&2; \
			exit 1; \
		fi; \
		sleep 2; \
	done
	NEO4J_URI=$(NEO4J_TEST_URI) NEO4J_USER=$(NEO4J_TEST_USER) NEO4J_PASSWORD=$(NEO4J_TEST_PASSWORD) \
		uv run pytest tests/integration -q

## --- Not yet implemented (fail loudly, don't pretend to succeed) ---

ingest:
	@echo "not yet implemented (P2)"; exit 1

eval-smoke:
	@echo "not yet implemented (P5)"; exit 1

eval-full:
	@echo "not yet implemented (P5)"; exit 1

run-api:
	@echo "not yet implemented (P9)"; exit 1

run-ui:
	@echo "not yet implemented (P9)"; exit 1

demo:
	@echo "not yet implemented (P9)"; exit 1

audit-budgets:
	@echo "not yet implemented (P1)"; exit 1

snapshot-graph:
	@echo "not yet implemented (P3)"; exit 1
