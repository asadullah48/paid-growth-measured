Build **Paid Growth, Measured**, a professional web application that helps advertising agencies manage clients, orders, employees, creative work, and campaign performance from one platform.

Act as a senior product engineer and UX designer. Begin with a clear specification and implementation plan, then build the application in small, validated stages.

## Product Objective

Replace fragmented spreadsheets and manual processes with a centralized agency workspace. Help teams coordinate work, track spending, communicate clearly, and connect campaign activity to measurable business outcomes.

Support digital campaigns and offline advertising activities such as television commercials and banner placements.

## Recommended Technical Stack

- **Frontend:** Next.js, TypeScript, Tailwind CSS, and shadcn/ui.
- **Backend:** FastAPI with documented REST endpoints.
- **Database:** PostgreSQL with SQLAlchemy and versioned migrations.
- **Authentication:** Secure authentication with role-based permissions.
- **Development:** Documented local setup and environment configuration.

Use supported, stable versions and explain significant architectural decisions.

## Core Modules

### 1. Agency Dashboard

Provide an overview of:

- Active clients and campaigns.
- Orders awaiting action.
- Upcoming deadlines and assigned tasks.
- Planned budget, actual spend, leads, and conversions.
- Campaign performance trends and outstanding approvals.

Clearly distinguish actual results from targets and sample data.

### 2. Order Management

- Create advertising orders linked to clients.
- Record services, channels, deliverables, budgets, and deadlines.
- Assign responsible team members.
- Track status: Draft, Confirmed, In Progress, Awaiting Approval, Completed, and Cancelled.
- Maintain attachments, internal notes, and status history.

### 3. Customer Relationship Management

- Store client organizations, contacts, and communication preferences.
- Track opportunities, follow-ups, and account ownership.
- Display related orders, campaigns, documents, and interaction history.
- Support search, filtering, and duplicate detection.

### 4. Employee and Task Management

- Maintain staff profiles, roles, and responsibilities.
- Assign tasks to orders and campaigns.
- Track deadlines, workload, and completion.
- Restrict sensitive employee information to authorized users.
- Use transparent task metrics rather than unsupported performance scores.

### 5. Creative Workflow

- Create campaign briefs and organize creative assets.
- Store copy, images, video references, and version history.
- Support review comments and approval states.
- Provide reusable brief and copy templates.
- Start with asset management and previews; treat advanced graphic editing as a later feature.

### 6. Campaign Planning and Monitoring

- Organize campaigns by client, objective, channel, and reporting period.
- Support paid social, search, display, television, and outdoor advertising.
- Maintain schedules, placements, budgets, and responsible owners.
- Provide a campaign calendar.
- Support manual entry and CSV import of performance data in the first release.
- Prepare integration interfaces for advertising platforms without pretending that live connections already exist.

### 7. Measurement and Reporting

Track:

- Spend, impressions, clicks, leads, conversions, and attributed revenue.
- CTR = clicks ÷ impressions × 100.
- CPC = spend ÷ clicks.
- CPL = spend ÷ leads.
- CPA = spend ÷ conversions.
- ROAS = attributed revenue ÷ spend.

Handle zero denominators as unavailable values. Label currency, date range, timezone, attribution model, and data source. Keep metrics with different attribution definitions separate.

Provide filtered reports and CSV export. Do not infer causation or guaranteed growth from dashboard metrics.

### 8. Collaboration and Client Approvals

- Support comments, mentions, activity history, and in-app notifications.
- Give clients access only to their own approved workspace content.
- Allow clients to approve or request revisions to deliverables.
- Prepare email and telecom notification adapters for future integration.
- Require explicit authorization before sending external messages or publishing advertisements.

## Roles and Access

Implement:

- Agency Administrator.
- Account Manager.
- Campaign Specialist.
- Creative Team Member.
- Client Viewer/Approver.

Enforce permissions on the backend. Scope every business record to its agency and test that users cannot access another agency’s data.

## UX Requirements

- Use a polished, responsive interface with clear navigation.
- Present the brand as **Paid Growth, Measured**.
- Use concise, professional, encouraging language.
- Include useful loading, empty, error, and success states.
- Support accessible forms, keyboard navigation, and readable charts.
- Make important actions and approval status easy to understand.

## Engineering Requirements

- Validate inputs and return actionable errors.
- Protect credentials through environment variables.
- Include audit history for sensitive changes.
- Add pagination and filtering for growing datasets.
- Use synthetic, clearly labeled demonstration data.
- Define file-upload size and type limits.
- Test authentication, permissions, agency isolation, order transitions, campaign calculations, and CSV validation.
- Document implemented features, limitations, and future integrations accurately.

## Four-Stage Execution

1. **Foundation:** Product specification, data model, authentication, agency boundaries, and application shell.
2. **Operations:** CRM, orders, employees, tasks, and creative approvals.
3. **Measurement:** Campaign planning, manual metrics, CSV imports, dashboards, and reports.
4. **Validation:** Meaningful tests, accessibility review, setup documentation, and demonstration walkthrough.

## Deliverables

- A working local application with frontend, backend, and database setup.
- A clear repository structure.
- Database migrations and synthetic sample data.
- API documentation.
- Automated checks for critical workflows.
- README with installation, configuration, launch instructions, and limitations.
- A short demonstration covering client creation → order intake → task assignment → creative approval → campaign reporting.

Prioritize a complete, usable first release. Begin by inspecting the workspace, recording reasonable assumptions, and writing the specification. Proceed with reversible local implementation; ask only about decisions that materially affect scope or require credentials, paid services, deployment, or external actions.