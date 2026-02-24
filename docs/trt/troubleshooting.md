# Troubleshooting

## `FIXTURE_EXHAUSTED`

Cause:

- replay requested more matching fixtures than recorded.

Fix:

1. re-record baseline for intended behavior
2. verify tool/LLM matcher mode (`args_signature_match` / `signature_match`)
3. check deterministic arguments are not drifting

## `NORMALIZER_VERSION_MISMATCH`

Cause:

- baseline artifact was produced with a different `normalizer_version`.

Fix:

1. re-record baseline with current Trajectly
2. keep repo and CI pinned to same Trajectly version

## Replay Network Blocked

Cause:

- offline mode blocks DNS/socket/http/websocket/subprocess networking.

Fix:

1. keep CI offline and rely on fixtures (recommended)
2. only allowlist explicitly approved domains/tools when necessary

## CI Baseline Write Denied

Cause:

- `TRAJECTLY_CI=1` blocks baseline writes.

Fix:

1. do not update baselines in normal CI checks
2. for intentional update jobs only, use `trajectly record ... --allow-ci-write`

## Shrinker Did Not Reduce

Cause:

- no smaller candidate preserved TRT failure class under bounds.

Fix:

1. increase `--max-seconds` / `--max-iterations`
2. keep original counterexample prefix; it remains valid
