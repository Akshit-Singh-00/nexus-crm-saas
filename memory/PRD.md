# NexusCRM — Product Requirements Document

## Original Problem Statement
Multi-tenant SaaS CRM where companies create their own workspace and manage customers, leads, deals, tasks, employees, analytics, notifications, communication, AI insights and subscriptions.

## Stack (chosen with user)
- Backend: FastAPI + MongoDB (motor)
- Auth: JWT-based custom (email + password, bcrypt)
- Frontend: React 19 + React Router + Tailwind + Shadcn UI + Recharts + Lucide
- AI: Claude Sonnet 4.6 via `emergentintegrations` (EMERGENT_LLM_KEY)
- Payments: Stripe (deferred to next phase)
- Design: Cabinet Grotesk + IBM Plex Sans/Mono; palette #0A0A0A sidebar, #0047FF primary, #FF3823 AI accent

## Personas
1. **Owner / founder** — creates workspace, invites team, sees all data, manages billing (future)
2. **Admin** — full CRUD, invites members, cannot delete workspace
3. **Member (sales rep)** — creates/updates customers, leads, deals, tasks
4. **Viewer** — read-only access to workspace data

## Multi-tenancy model
Every entity carries `workspace_id`. Requests require `X-Workspace-Id` header + JWT. Membership lookup enforces role-based access.

## Delivered (2026-02) — Iteration 7 (Customer 360 Upgrade)

### Backend
- **New unified `interactions` collection** — one row per email / call / meeting / file. All rows carry `workspace_id`, optional `customer_id` + `deal_id`, and are validated against the tenant.
- **New routers**
  - `routers/interactions.py` — CRUD for `/emails`, `/calls`, `/meetings` (+ `PATCH /meetings/{id}/status`), `/files` (+ single-file download that returns `data_url`). 5 MB inline-upload cap.
  - `routers/integrations.py` — `/integrations` list (returns not_connected|pending|connected for gmail/outlook/google_calendar), `POST /integrations/connect`, `DELETE /integrations/{provider}`. **No OAuth secrets stored** — connect endpoint marks provider `pending`; a signed OAuth callback would flip to `connected` in a follow-up.
  - `routers/customer360.py` — `GET /customers/{id}/summary` (owner, totals, best lead score, last_activity, next_meeting) and `GET /customers/{id}/timeline` (unified chronological feed merging activities + notes + interactions + deal changes, deduped).
- **New schemas** — `EmailLogIn`, `CallLogIn`, `MeetingIn`, `MeetingStatusIn`, `FileMetaIn`, `IntegrationConnectIn`.
- **New indexes** on `interactions(workspace_id, kind, customer_id | deal_id | scheduled_at)` and `integrations(workspace_id, user_id, provider) unique`.
- All 134 backend tests still pass.

### Frontend — Customer 360 header
- Health dot + name + company + email + phone
- New: **Owner** (auto-derived from top open deal's assignee, falls back to creator)
- New stat quartet: Status · Total value · Lead score · Last activity
- New: **Next meeting** row (only shown if scheduled)
- New: **Quick actions** — Email · Call · Meeting · Task · Note

### Frontend — 10 tabs
Overview · Deals · Tasks · Emails · Meetings · Calls · Tickets · Notes · Files · Activity.
Each tab has an empty state; Emails and Meetings surface a hint card if the relevant provider is not connected.

### Frontend — Unified timeline
- Groups events by day
- Icon per event type (email out/in, call, meeting scheduled/completed, file, note, generic activity)
- Actor · type · description · time — matches the spec 1:1
- Same component reused on the Overview tab (top 10) and Activity tab (all)

### Integration architecture (safe)
- Backend abstraction is real; **no fake emails are marked as "synced"**. Provider status stays `pending` until real OAuth is wired.
- UI shows a "Not connected — logged emails/meetings stay in NexusCRM only" hint. This is honest and matches the spec's "do not pretend emails are synchronized".

### Verified after upgrade
- Signup / login / me / workspace switching
- Customer / deal / lead / task / ticket CRUD still work
- `/customers/{id}/timeline` deduped: 3 interactions → 4 events (customer creation + 3 interactions), no double-counting
- 134/134 backend tests still pass

## Delivered (2026-02) — Iteration 5 (Security Hardening)

### Tenant Isolation
- All CRUD endpoints already scoped via `workspace_query(ctx)`; audited every route
- Added `ensure_customer_in_workspace`, `ensure_deal_in_workspace`, `ensure_lead_in_workspace`, `ensure_related_in_workspace`, `ensure_assignee_in_workspace` helpers
- Every referenced `customer_id` / `assignee_id` / `related_id` in Deal, Task, Ticket, Note create/update is validated against the caller's workspace → cross-tenant reference attacks return 400
- Workflow action `user_id`/`assignee_id` params validated at workflow create/update

### RBAC audit
- `require_perm(resource, action)` enforced at backend for every endpoint (never trust frontend)
- Fixed `/ai/sales-forecast` — was `require_workspace`, now `require_perm("ai", "use")`
- Added `require_perm("customer","edit")` audit logging on customer update/delete
- Added activity + audit log on lead update/delete, deal update/delete, customer update/delete

### Payment security
- `GET /payments/status/{session_id}` was UNAUTHENTICATED → now requires JWT + `X-Workspace-Id` and returns the record ONLY if it belongs to the caller's workspace
- Stripe status re-check gated behind `billing.view` permission

### Search security
- User query fed to `$regex` was UNESCAPED (ReDoS / regex injection risk) → now `re.escape()`
- Search min length ≥ 2, max 100 chars
- Rate-limited to 120/min

### Invitations
- Invites are now single-use — accepting an already-accepted invite returns 400
- JWT-signed invite tokens with 7-day expiry (preserved)

### Rate limiting (slowapi, per-IP)
- Signup: 60/hour · Login: 30/min · Invite: 60/hour · AI copilot: 60/min · AI score: 60/min
- Search: 120/min · Import preview: 120/hour · Import execute: 30/hour
- Toggle via `RATE_LIMIT_ENABLED=0` in env for dev / test isolation

### CORS
- Removed `allow_origins=*`; now uses explicit `CORS_ORIGINS` env (comma-separated). Falls back to `APP_URL + localhost:3000`
- Allowed headers restricted to `Authorization`, `Content-Type`, `X-Workspace-Id`
- Allowed methods restricted to `GET/POST/PUT/PATCH/DELETE/OPTIONS`

### Error handling
- Generic global handler — no more stack traces to clients. All uncaught exceptions return `{"detail":"Internal server error"}` with 500
- Rate-limit exceptions return 429 with a friendly message

### Audit logging
- Added: `login_success`, `login_failed` (email only, no passwords/tokens ever logged)
- Added: customer/lead/deal update+delete activities and customer update/delete audit rows

### Database indexes (created on startup)
- `users(email unique, id unique)` · `memberships(workspace_id, user_id) unique` + `user_id`
- `workspaces.id unique` · `customers(workspace_id, created_at desc)` + `(workspace_id, id)` + `(workspace_id, email)`
- `leads(workspace_id, created_at desc)` + `(workspace_id, id)` + `(workspace_id, status)`
- `deals(workspace_id, stage)` + `(workspace_id, id)` + `(workspace_id, created_at desc)`
- `tasks(workspace_id, status)` + `(workspace_id, assignee_id)`
- `tickets(workspace_id, status)` + `(workspace_id, id)` · `notes(workspace_id, related_type, related_id)`
- `activities(workspace_id, created_at desc)` · `notifications(workspace_id, user_id, read)`
- `audit_logs(workspace_id, created_at desc)` · `workflows(workspace_id, trigger, enabled)`
- `payment_transactions(workspace_id, session_id)` + `session_id unique`
- `invites(workspace_id, email)`

### Pagination
- All list endpoints (`/customers`, `/leads`, `/deals`, `/tasks`, `/tickets`) support `?page=&limit=`; limit hard-capped at 100 (default 100)
- Activities capped at 100, audit-logs at 200, notes at 100

### Tests
- Added `/app/backend/tests/test_security.py` (22 tests) covering all 11 checklist items
- Fixed 3 stale pre-existing tests in `backend_test.py` (`pipeline_stages` length, invite verification, ai `reasons` vs `reason`)
- Added 1 new test in `test_iteration2.py` for payments auth
- **All 134 tests passing (1 rate-limit test skipped when env disables limiter)**


## Delivered (2026-02) — Iteration 4 (Import + Automation)

### CSV Import Wizard
- 3-step wizard: pick entity (lead/customer) → upload CSV → auto-inferred column mapping → confirm & execute
- Backend: `POST /api/import/preview` returns headers, sample rows, target fields, suggested mapping (fuzzy field-name match); `POST /api/import/execute` bulk-creates with per-row error capture
- Client-side CSV parsing via `FileReader` (no extra deps); server-side parsing via stdlib `csv`
- Audit logged as `imported <entity> batch` with row count + error count
- Permission-gated: requires `lead.create` or `customer.create` for the chosen entity
- Verified: 2/2 rows imported end-to-end via curl

### Workflow Automation Engine
- Trigger → Conditions → Actions builder
- Triggers: `lead_created`, `lead_scored`, `customer_created`, `deal_created`, `deal_stage_changed`
- Conditions: field/op/value with ops `eq/neq/gt/gte/lt/lte/contains/in`; **AND** semantics (all must match)
- Actions: `create_task` (with assignee + priority + auto-linked to entity), `assign_user`, `notify_user`, `add_tag`
- Backend `fire_workflows(trigger, workspace_id, record)` dispatch wired into: create_lead, create_customer, create_deal, update_deal_stage, ai_score_lead
- Workflows persist `run_count` and `last_run_at`
- Admin-only page at `/app/workflows`; toggle enable/disable, edit, delete
- Verified end-to-end: created "score > 80 → add hot-lead tag + create high-priority task" workflow → scored a lead 82 → tag added, task auto-created, run_count = 1

## Delivered (2026-02) — Iteration 3 (Professional SaaS polish)

### Enhanced RBAC (6 roles + permission matrix)
- Roles: owner (Super Admin), admin (Org Admin), manager (Sales Manager), member (Sales Rep), support (Support Agent), viewer
- Declarative `PERMISSIONS[resource][action] → set(roles)` + `require_perm(resource, action)` FastAPI dependency
- **All CRUD endpoints wired through `require_perm`** (customers, leads, deals, tasks, notes, tickets, settings, audit_log, member management, ai). Legacy `require_role` fully retired from resource endpoints — the matrix is now the single source of truth.
- Team page allows admins to change teammate role and remove members (owner protected)

### Deal enhancements + custom pipeline stages + risk detection
- Deal: added `probability`, `priority`, `tags`, `description`, `assignee_id`, `expected close_date`
- Workspace `pipeline_stages` (id, label, color, probability). Editable via Settings.
- Kanban cards show assignee, probability chip, priority, tags, close date, risk banner
- `_compute_deal_risk()` flags deals: idle 7+ days, overdue close, stale proposal, low prob + stale
- Deal card highlights risk with left border colour + reasons

### Advanced analytics (upgraded /api/analytics/overview)
- Revenue forecast cards: **Committed / Best case / Pipeline / Weighted forecast**
- Sales KPIs: **Win rate · Avg deal size · Sales cycle days**
- At-risk deals section with click-through to pipeline
- Open tickets KPI included

### AI Sales Copilot (`POST /api/ai/copilot`)
- Slide-out drawer (⌘J) with suggestion prompts + free-form chat
- Backend gathers live CRM snapshot (deals, at-risk, top-scored leads, open tasks) and passes to Claude 4.6
- Answers reference actual deal/lead titles from the workspace

### Enhanced AI lead scoring
- Now returns `{score, classification (hot/warm/cold), reasons[]}` and persists all fields
- Score badge shows both numeric score + classification

### Support Tickets module (new)
- Full CRUD, per-ticket status transitions inline, priority, per-workspace `TKT-#####` numbering
- Stats KPIs: Open · High priority · Resolved · Total
- Assignee notifications on creation
- `/api/tickets`, `/api/tickets/stats/overview`

### Workspace settings + logo
- `GET/PUT /api/workspaces/settings` (permission-gated)
- Settings page: workspace name, industry, logo URL preview, drag-orderable pipeline stages with colour picker + probability
- Sidebar shows logo when set

### Audit log
- `audit_logs` collection with user, action, resource, before/after diff
- Auto-logged on: settings changes, member role changes / removals, ticket create/update/delete
- Admin-only viewer at `/app/audit`

### Customer 360 upgrade
- Tabs: Overview · Deals · Tasks · Notes · Activity
- Health indicator, contact chips, deal count / total value in header
- Cross-linked open deals and tasks per customer

## Delivered (2026-02) — Iteration 2

### Invite Acceptance
- Signed JWT invite tokens (7-day expiry) stored in `invites` collection
- Copyable invite link + optional Resend email delivery
- `/invite/:token` page auto-detects existing vs new users; sets password + attaches membership
- Endpoints: `POST /workspaces/invite`, `GET /invites/{token}`, `POST /invites/{token}/accept`

### Global Search (Cmd+K)
- `GET /api/search?q=` scoped to workspace; searches customers, leads, deals (6 each)
- Shadcn CommandDialog palette with debounced query + keyboard shortcut

### Notifications
- `notifications` collection; auto-created on deal-stage change (broadcast) and task-assignment (targeted)
- Bell in topbar polls every 20s, shows unread badge, mark-single/mark-all read
- Endpoints: `GET /notifications`, `POST /notifications/{id}/read`, `POST /notifications/read-all`

### Stripe Billing (Flow B)
- 3 plans: Starter (free), Pro ($29/mo), Team ($79/mo)
- Emergentintegrations checkout + webhook + status polling
- `/app/billing` page with 3 pricing cards, current-plan highlight, test-card hint
- Endpoints: `GET /billing/plans`, `GET /billing/subscription`, `POST /billing/checkout`, `GET /payments/status/{id}`, `POST /webhook/stripe`

### Dark theme
- Full CSS token overhaul: canvas, surface, hairline, muted; default dark
- Sun/Moon topbar toggle, persisted to localStorage
- All app pages migrated to theme tokens

## Delivered (2026-02) — Iteration 1
### Phase 1 — Foundation ✅
- JWT signup/login/me
- Workspace creation + switcher
- Multi-tenancy via `X-Workspace-Id` header + membership check
- RBAC: owner / admin / member / viewer

### Phase 2 — CRM ✅
- Customers CRUD + search
- Leads CRUD + search + AI score
- Deals CRUD + Kanban board (6 stages) + drag-drop stage update
- Tasks CRUD + priority + status toggle
- Notes attached to any entity (customer/lead/deal)
- Activity log with actor info

### Phase 3 — Real-world ✅ (partial)
- Search/filter on customers & leads
- Dashboard analytics (KPIs, pipeline chart, leads-by-status)
- Sonner toasts for feedback

### Phase 4 — AI ✅
- AI lead scoring (Claude → 0-100 + rationale)
- AI customer executive summary
- AI Q1 sales forecast

## Backend endpoints (all under `/api`)
- Auth: `POST /auth/signup`, `POST /auth/login`, `GET /auth/me`
- Workspaces: `POST /workspaces`, `GET /workspaces/members`, `POST /workspaces/invite`
- Customers/Leads/Deals/Tasks: full CRUD + Deals `PATCH /deals/{id}/stage`
- Notes: `GET /notes?related_type&related_id`, `POST /notes`
- Activities: `GET /activities`
- Analytics: `GET /analytics/overview`
- AI: `POST /ai/score-lead/{id}`, `POST /ai/summarize-customer/{id}`, `GET /ai/sales-forecast`

## Backlog / Next
### P0
- Stripe subscriptions & billing page
- Invite acceptance flow (invited stub users can't log in yet)

### P1
- Global search across entities
- Notifications center (unread bell)
- Real-time updates (WebSocket) for kanban collaboration
- File uploads (attachments on customers/deals)
- Email integration (send emails, log threads)

### P2
- AI sales predictions dashboard widget with historical trend
- Custom fields per workspace
- CSV import/export
- Redis caching layer
- Reports & exportable analytics
- Mobile-optimised layout

## Test credentials
See `/app/memory/test_credentials.md`.
