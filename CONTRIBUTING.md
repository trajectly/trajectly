# Contributing to Trajectly

## Local Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
```

## Quality Gates

```bash
ruff check .
mypy src
pytest
```

## Development Workflow

1. Add or update tests first for behavior changes.
2. Keep trace schema and plugin interfaces backward compatible.
3. Keep CLI errors actionable and deterministic.

## Release Notes

- `trajectly` uses SemVer and starts at `v0.x`.
- Do not break public CLI flags, trace schema, or plugin interfaces in patch releases.
