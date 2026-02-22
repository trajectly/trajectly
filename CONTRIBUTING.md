# Contributing to Trajectly

## Local Setup

### Recommended (`uv`)

```bash
uv venv
source .venv/bin/activate
uv sync --extra dev
```

### Pip Editable Install (Supported)

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
```

## Quality Gates (`uv`)

```bash
uv run ruff check .
uv run mypy src
uv run pytest
```

## Development Workflow

1. Add or update tests first for behavior changes.
2. Keep trace schema and plugin interfaces backward compatible.
3. Keep CLI errors actionable and deterministic.

## Release Notes

- `trajectly` uses SemVer and starts at `v0.x`.
- Do not break public CLI flags, trace schema, or plugin interfaces in patch releases.
