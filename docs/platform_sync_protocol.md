# Platform Sync Protocol

`trajectly sync` pushes the latest `.trajectly/` run artifacts to an HTTP endpoint that implements the Phase 1 ingestion contract.

## Endpoint

```text
POST /api/v1/sync
Content-Type: application/json
Accept: application/json
Idempotency-Key: <sha256 of canonical sync payload>
X-Trajectly-Project-Slug: <project slug>
X-Trajectly-Protocol-Version: v1
Authorization: Bearer <api key>   # optional
```

## CLI Usage

```bash
python -m trajectly sync \
  --project-root . \
  --endpoint https://platform.example/api/v1/sync \
  --project-slug support-agent \
  --api-key "$TRAJECTLY_API_KEY"
```

Environment variables:
- `TRAJECTLY_SYNC_ENDPOINT`
- `TRAJECTLY_API_KEY`
- `TRAJECTLY_PROJECT_SLUG`

## Request Shape

```json
{
  "schema_version": "v1",
  "protocol_version": "v1",
  "generated_at": "2026-03-18T12:00:00+00:00",
  "idempotency_key": "9cf7...",
  "project": {
    "slug": "support-agent",
    "root_path": "/workspace/support-agent",
    "git_sha": "abc123",
    "trajectly_version": "0.4.2"
  },
  "run": {
    "processed_specs": 1,
    "regressions": 0,
    "errors": [],
    "latest_report_path": ".trajectly/reports/latest.json",
    "latest_report_sha256": "4b7e...",
    "trt_mode": true
  },
  "reports": [
    {
      "spec": "sync-demo",
      "slug": "sync-demo",
      "regression": false,
      "spec_path": "sync.agent.yaml",
      "report_json_path": ".trajectly/reports/sync-demo.json",
      "report_md_path": ".trajectly/reports/sync-demo.md",
      "run_id": "sync-demo-1234abcd",
      "report_payload": {
        "summary": {
          "regression": false
        },
        "findings": []
      },
      "metadata": {
        "baseline_version": "v1"
      }
    }
  ],
  "trajectories": [
    {
      "spec": "sync-demo",
      "slug": "sync-demo",
      "kind": "current",
      "path": ".trajectly/current/sync-demo.run.jsonl",
      "run_id": "sync-demo-1234abcd",
      "baseline_version": "v1",
      "trajectory": {
        "schema_version": "0.4",
        "meta": {
          "schema_version": "0.4",
          "normalizer_version": "1",
          "spec_name": "sync-demo",
          "run_id": "sync-demo-1234abcd",
          "mode": "replay",
          "metadata": {
            "git_sha": "abc123"
          }
        },
        "events": []
      },
      "metadata": {
        "report_json_path": ".trajectly/reports/sync-demo.json"
      }
    }
  ]
}
```

## Response Shape

Recommended `2xx` JSON response:

```json
{
  "accepted": true,
  "sync_id": "sync-123",
  "message": "queued"
}
```

Authentication failures should use `401` or `403`. Validation failures should use `400`. Transient server failures should use `408`, `409`, `425`, `429`, or `5xx` so the CLI can retry safely with the same `Idempotency-Key`.

`Idempotency-Key` is derived from the stable sync payload content, not the request timestamp, so repeating the same logical upload after an uncertain failure reuses the same key.

## Local Metadata

After a successful upload, Trajectly writes `.trajectly/sync/latest.json` with:
- endpoint
- project slug
- idempotency key
- synced timestamp
- latest report path/hash
- processed spec count
- report count
- trajectory count
- optional `sync_id` and server message

Dry runs do not write sync metadata.
