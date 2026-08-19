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
