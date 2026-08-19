# NexusCRM

> **AI-powered, multi-tenant SaaS CRM for modern sales teams.**

NexusCRM is a production-oriented CRM platform designed for organizations that want to manage customers, leads, deals, tasks, support tickets, workflows, analytics, team collaboration, and AI-assisted sales operations from one workspace.

The current implementation focuses on **tenant isolation, backend-enforced RBAC, workflow automation, Customer 360, AI sales intelligence, analytics, auditability, and SaaS-ready architecture**.

---

## Highlights

- **Multi-tenant workspaces** with tenant-isolated data
- **JWT authentication + backend-enforced RBAC**
- Customers, leads, deals, tasks, notes, activities and tickets
- Advanced sales analytics and revenue forecasting
- AI Sales Copilot with workspace-aware CRM context
- AI lead scoring with Hot / Warm / Cold classification
- Deal risk detection
- Workflow automation: triggers → conditions → actions
- CSV import wizard for customers and leads
- Customer 360 with unified activity timeline
- Email, call and meeting interaction architecture
- Notifications and activity tracking
- Audit logs
- Global search with rate limiting and safe regex handling
- Server-side pagination
- Stripe-ready subscription architecture
- Security hardening, rate limiting and explicit CORS configuration
- Modern responsive SaaS UI with dark mode

---

## Product Modules

### Dashboard

Provides an executive overview of:

- Revenue
- Pipeline value
- Weighted forecast
- Committed revenue
- Best-case forecast
- Win rate
- Average deal size
- Sales cycle
- Open tickets
- At-risk deals

### Customers

Manage the complete customer lifecycle:

- Customer profiles
- Company information
- Ownership
- Customer value
- Lead score
- Tasks
- Deals
- Tickets
- Notes
- Activities
- Interactions

### Leads

- Lead management
- Status tracking
- Lead scoring
- Hot / Warm / Cold classification
- AI-generated scoring reasons
- Assignment
- Tags
- CSV import
- Workflow triggers

### Deals

Professional Kanban sales pipeline with:

- Custom pipeline stages
- Deal value
- Probability
- Priority
- Assignee
- Expected close date
- Tags
- Risk detection
- Stage transitions
- Revenue forecasting

### Tasks

- Create and assign tasks
- Priorities
- Status tracking
- Due dates
- CRM-linked tasks
- Workflow-generated tasks

### Support Tickets

- Ticket creation
- Priority
- Status
- Assignee
- Customer association
- Ticket numbering
- Support analytics
- Notifications

### Customer 360

Each customer has a unified workspace containing:

- Overview
- Deals
- Tasks
- Emails
- Meetings
- Calls
- Tickets
- Notes
- Files
- Activity

The unified timeline combines CRM activities and interactions chronologically.

---

# AI Features

## AI Sales Copilot

NexusCRM includes an AI Sales Copilot that receives authorized CRM context and helps users answer questions such as:

> Which leads should I contact today?

> Which deals are at risk?

> Summarize this customer.

> Which deals have been inactive?

> What are my top sales priorities?

The Copilot uses live workspace CRM data rather than acting as a generic chatbot.

### AI Lead Scoring

Leads receive:

- Score from 0–100
- Hot / Warm / Cold classification
- Explainable business reasons


Example:

```text
Score: 87/100
Classification: HOT
Reasons:
- High engagement
- Strong company fit
- Recent activity
- High estimated value


## Live Demo Link
https://workspace-crm-6.preview.emergentagent.com

