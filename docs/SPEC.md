# Paid Growth, Measured — Local MVP Specification

## Goal
A multi-agency workspace for client records, advertising orders, employee assignments, creative approval, and comparable campaign reporting.

## Delivery stages
1. Foundation: Next.js frontend, FastAPI API, PostgreSQL schema, opaque server sessions, agency-scoped authorization.
2. Operations: clients, employees, orders, tasks, creative versions, client decisions, comments, and activity.
3. Measurement: manual campaign records, validated CSV import/export, comparable metric summaries, and scheduling.
3b. Context: versioned Client Context Packs, client fact approval, template drafting with claim tracing, in-app narratives and PDF export with sequential approval.
4. Validation: security and workflow tests, frontend checks, documented local demonstration.

## Assumptions
- New project location: `D:\paid-growth-measured`; no repository cloning or publishing.
- Local development starts with an administrator-created agency and users; no public registration.
- Roles: administrator, account_manager, campaign_specialist, creative, client.
- Client users are linked to exactly one client record and see only that client's campaigns and reviewable creative.
- Staff records are visible only to administrators and account managers.
- Campaign metrics are cumulative per campaign/reporting period. Distinct currency, timezone, attribution, or source groups are never aggregated together.
- Sample records are synthetic and clearly labeled. No live integrations or external messages.
- Only Account Managers may edit Context Packs, including administrators being denied that editing permission. Each version resets fact approvals.
- Client approved-facts views show only facts that user approved. A separate review request view exposes pending facts for explicit approval.
- Narrative numbers come from immutable metric snapshots, labeled with dates, currency, attribution, source, and capture timestamp. Later metric edits require a new report.
- Account Manager approval precedes client report approval. No auto-publication or LLM configuration is enabled.
- Creative assets are validated reference URLs with versioned copy. Binary uploads are deferred and no upload endpoint exists.
- Structured operational tasks are the first-release employee workload measure.

## Acceptance criteria
- API denies cross-agency and cross-client access regardless of frontend behavior.
- Orders follow explicit transitions and retain audit history.
- Approved creative becomes immutable; revisions create a new version.
- Client decisions apply only to submitted deliverables in the user's workspace.
- CSV imports validate all rows before writing and reject duplicates in the batch.
- Dashboard ratios handle zero denominators and show data definitions.
- Logs and API errors do not disclose credentials or password hashes.

## Limits of the local MVP
No payment processing, advertising publishing, email/telecom sending, graphic editor, binary file uploads, or live vendor data. Production deployment requires managed TLS, backup/restore validation, monitoring, rate limiting at the ingress, secret management, and a dedicated security review.
