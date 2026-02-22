# Testing Guide

## Prerequisites

- Python 3.11+ installed.
- `uv` installed (`https://docs.astral.sh/uv/`).

## Core Repo (`trajectly`)

```bash
cd trajectly
uv sync --extra dev
uv pip install -e .
./scripts/check_blocked_paths.sh
uv run ruff check .
uv run mypy src
uv run pytest -q
uv run trajectly init
uv run trajectly record tests/*.agent.yaml
uv run trajectly run tests/*.agent.yaml
```

Expected outcomes:

- `pytest` passes.
- `record` exits `0`.
- `run` exits `0` on deterministic examples.

## Action Repo (`trajectly-action`)

```bash
cd trajectly-action
python -m pip install pytest
./scripts/check_blocked_paths.sh
pytest -q
bash -n scripts/run.sh
```

Expected outcomes:

- tests pass
- shell lint (`bash -n`) passes

## Examples Repo (`trajectly-examples`)

```bash
cd trajectly-examples
python -m pip install pytest pyyaml
./scripts/check_blocked_paths.sh
pytest -q
uv run --with "git+https://github.com/trajectly/trajectly.git@main" trajectly init
uv run --with "git+https://github.com/trajectly/trajectly.git@main" trajectly record specs/simple.agent.yaml specs/tool.agent.yaml specs/openai.agent.yaml specs/anthropic.agent.yaml specs/langchain.agent.yaml
uv run --with "git+https://github.com/trajectly/trajectly.git@main" trajectly run specs/simple.agent.yaml specs/tool.agent.yaml specs/openai.agent.yaml specs/anthropic.agent.yaml specs/langchain.agent.yaml
```

Expected outcomes:

- Example tests pass.
- Replay run exits `0` for clean specs.
- `specs/regression.agent.yaml` exits `1` when replayed after baseline capture.
