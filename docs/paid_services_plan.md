# Paid Services Implementation Plan (Open-Core)

This plan defines the SaaS layer built on top of the OSS repos.

## OSS vs SaaS Boundary

OSS remains fully useful offline:

- CLI record/replay/diff/report
- Trace schema + fixture format
- Plugin interfaces
- GitHub Action support

SaaS adds hosted coordination:

- Team workspaces and RBAC
- Historical run storage and trend analytics
- Managed semantic diff and flaky-run intelligence
- Alert routing and incident workflows

## SaaS Product Surfaces

1. Ingestion API:
- Accept run metadata, trace references, diff findings, and report summaries.

2. Web Dashboard:
- Run timeline, regression drilldown, baseline management, and trend views.

3. Notifications:
- Slack, email, and webhook alerting on regressions/budget breaches.

4. Governance:
- Audit logs, retention controls, SSO/SAML (enterprise tier).

## Technical Architecture

- Control API: auth, workspace/project models, run index.
- Object storage: trace/report artifacts.
- Queue + workers: ingestion enrichment, semantic diff jobs, flaky analysis.
- Analytics store: queryable run/finding metrics.
- UI service: dashboard and report views.

## Phased Delivery

### Phase A: SaaS Alpha

- API key auth.
- Single-workspace ingestion endpoint.
- Basic run listing + report rendering.

### Phase B: Team Beta

- Multi-project workspaces.
- GitHub App integration for PR status and deep links.
- Alerts and baseline promotion workflow.

### Phase C: GA

- SSO/SAML + enterprise controls.
- Advanced analytics and flaky-run probability scoring.
- Billing, quotas, and usage dashboards.

## Implementation Backlog (Prioritized)

1. Define stable ingestion payload schema versioning.
2. Build `RunHookPlugin` reference exporter package.
3. Implement auth and workspace model.
4. Build ingestion pipeline and durable storage.
5. Ship dashboard MVP with run and finding views.
6. Add alert rules and integrations.
7. Add billing/entitlement service.

## Monetization Model

- Free OSS core (MIT).
- Paid SaaS per-seat + usage tiers.
- Enterprise add-ons: SSO/SAML, private networking, extended retention, premium support.
