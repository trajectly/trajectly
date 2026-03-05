# Contributing to Trajectly

Thanks for taking the time to contribute.

Trajectly is an open-source project, and contributions of all sizes are welcome, including docs fixes, bug reports, tests, and code improvements.

## Ways to contribute

You can help by:

1. Reporting bugs with clear reproduction steps.
2. Improving docs and examples.
3. Adding tests for edge cases and regressions.
4. Contributing code for fixes or new capabilities.

## Local setup

```bash
git clone https://github.com/trajectly/trajectly.git
cd trajectly
python -m pip install -e ".[dev]"
```

## Development workflow

1. Create a branch for your change.
2. Keep the scope focused to one topic when possible.
3. Add or update tests and docs with the change.
4. Run local quality checks before opening a PR.

```bash
pytest tests/
ruff check .
mypy src
```

## Pull request checklist

Before opening a PR, please make sure:

1. The change is explained clearly in the PR description.
2. Behavior changes are described with concrete examples.
3. Any new command/docs content includes expected output cues where useful.
4. Tests pass locally for affected areas.

## Docs contribution notes

For documentation updates:

1. Prefer clear, step-by-step instructions.
2. Include expected output snippets for commands that may be confusing.
3. Use `$PROJECT_ROOT` placeholders instead of machine-specific absolute paths.

## Need help?

If you are unsure about an approach, open an issue first and describe the problem and proposed direction. That helps align on scope before implementation.
