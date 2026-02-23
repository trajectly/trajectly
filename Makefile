.PHONY: check test test-fast test-cov test-determinism demo

check: test-fast test-determinism

test: check

test-fast:
	uv run ruff check .
	uv run mypy src
	uv run pytest -q

test-determinism:
	uv run pytest -q tests/integration/test_determinism_replay.py

test-cov:
	uv run pytest --cov=src/trajectly --cov-report=term-missing -q

demo:
	@if [ -d ../trajectly-examples ]; then \
		cd ../trajectly-examples && \
		uv run --with-editable ../trajectly trajectly run specs/trt-search-buy-regression.agent.yaml specs/trt-support-triage-regression.agent.yaml || true; \
	else \
		echo "trajectly-examples repo not found at ../trajectly-examples"; \
	fi
