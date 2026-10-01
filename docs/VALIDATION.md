# Validation Record

## Completed checks

- **25 backend tests passed** using isolated SQLite fixtures.
- **Frontend TypeScript check passed.**
- **Next.js production build passed.**
- **SQLite migration and synthetic seed completed successfully.**
- **Browser smoke test passed** using installed Edge: administrator context-edit restriction, Account Manager pack creation, client fact approval, template draft generation, Account Manager/client report approvals, and PDF download.
- Desktop and mobile preview captures were created; the dashboard was visually reviewed.
- Frontend dependencies were installed with a generated lockfile; npm reported no known dependency vulnerabilities at installation time.

Automated checks cover authentication, CSRF boundaries, login attempt limits, permissions, agency isolation, client scope, order transitions, CSV validation and atomicity, metric calculations, Account Manager-only context editing, client fact approval, claim tracing, prohibited wording, expiry, report snapshots, sequential approval, numeric-context exclusion, and PDF output.

The test run emitted two dependency/model warnings: a Starlette httpx deprecation and Pydantic's legacy `copy` method name overlap. They did not prevent the checks from passing.

PostgreSQL integration requires a running database service. SQLite checks exercise application behavior but do not establish PostgreSQL operational readiness. Browser review and production deployment are separate from compiler and API tests.

Docker Desktop's database engine was unavailable during this run. No PostgreSQL runtime or production deployment is claimed. No external campaigns or messages were sent.

## PostgreSQL follow-up check (2026-10-01)

Run against a local PostgreSQL 16.13 server (not Docker, not production):

- `alembic upgrade head` created all tables; the synthetic seed succeeded and a second run changed nothing.
- All 25 backend tests passed with the test fixture pointed at PostgreSQL instead of in-memory SQLite (a temporary copy of the fixture; the committed tests still use SQLite).
- Live smoke test: API health, frontend `/api` proxy, administrator sign-in, and dashboard rendering in headless Chromium. Dashboard ratios matched hand calculations (CPL $13, CTR 3%, ROAS 3.84x).

Not covered: the Docker `compose.yaml` service itself, PostgreSQL 17 specifically, the full context-and-report walkthrough on PostgreSQL, and production deployment.

`compose.yaml` now reads `POSTGRES_PORT` (default 5432) so it can coexist with a locally installed PostgreSQL service.
