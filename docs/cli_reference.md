# CLI Reference

## Commands

### `trajectly init [project_root]`

Initializes `.trajectly/` state directories and starter files.

### `trajectly record <targets...> [--project-root PATH]`

Runs specs in record mode and writes:

- baseline traces (`.trajectly/baselines/*.jsonl`)
- fixture bundles (`.trajectly/fixtures/*.json`)

### `trajectly run <targets...> [--project-root PATH] [--baseline-dir PATH] [--fixtures-dir PATH] [--strict|--no-strict]`

Runs specs in replay mode, compares baseline vs current, and writes reports.

### `trajectly diff --baseline FILE --current FILE [--spec-name NAME] [--json-output PATH --markdown-output PATH] [--max-latency-ms N] [--max-tool-calls N] [--max-tokens N]`

Standalone trace diff command.

### `trajectly report [--project-root PATH] [--json]`

Prints latest aggregate report.

## Exit Codes

- `0`: clean run / no regression
- `1`: regression found
- `2`: internal/tooling/spec error
