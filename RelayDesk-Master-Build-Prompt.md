# RelayDesk — Master Build Document
### An AI Service Desk with context-preserving handover

> **One-liner:** An IT helpdesk where an AI agent resolves what it can, and when it *can't*, it hands the technician a complete briefing — problem, what was already tried, likely causes, and similar past tickets — so nobody ever has to restate their issue.

> **The differentiator (say this in interviews):** Most helpdesks (and most student projects) build an AI chatbot that answers FAQs. The unsolved 2026 industry gap is the **AI → human handover**: when the AI escalates, the technician gets a stripped-down transcript and the user has to explain everything again. RelayDesk solves *that* — it treats the handoff as a first-class feature, not an afterthought.

You can rename it (RelayDesk / HandoffHQ / BridgeDesk / ContextDesk). "RelayDesk" is used throughout below.

---

## 1. How it works (the core flow)

```
User submits ticket
        │
        ▼
[AI JOB 1] Classify + route  ──►  category, priority, SLA, suggested team
        │
        ▼
[AI JOB 2] Deflection attempt  ──►  searches KB, tries to resolve now
        │
        ├── Resolved? ──► User confirms fixed ──► Ticket auto-closed (DEFLECTED)
        │
        └── Not resolved / user says "still broken"
                    │
                    ▼
        [AI JOB 3] Generate HANDOVER BRIEFING  ◄── the star feature
                    │
                    ▼
        Ticket lands in technician queue WITH full briefing attached
                    │
                    ▼
        Technician resolves fast (zero context loss) ──► RESOLVED
```

The metric you will showcase: **handover context time** (how long a technician spends reconstructing context before they can start working). With RelayDesk that briefing is pre-assembled, so it drops toward zero. Also track **deflection rate** (% closed by AI without a human).

---

## 2. Roles

| Role | What they do |
|------|--------------|
| **End user** | Submits a ticket, chats with the AI, sees status. |
| **Technician (L1/L2)** | Works the queue; opens a ticket and sees the AI's handover briefing front and center. |
| **Admin / Manager** | Manages the knowledge base, sees the metrics dashboard (deflection %, avg handover time, backlog). |

---

## 3. Tech stack (committed)

Chosen to match your skills *and* look modern to a hiring manager. FastAPI is recommended over PHP for the backend because the AI orchestration is cleaner in Python — but PHP/Laravel works if you prefer; the schema and API design don't change.

| Layer | Choice | Why |
|-------|--------|-----|
| Frontend | **React (Vite) + Tailwind CSS** | Fast, clean, your strongest area. |
| Backend | **FastAPI (Python)** | Best fit for calling the Claude API and orchestrating the 3 AI jobs. |
| Database | **MySQL** | Your comfort zone; use `FULLTEXT` search for KB matching in the MVP. |
| AI | **Claude API** (`claude-sonnet-4-6`) | Classification, deflection, and briefing generation. |
| Realtime | **Firebase Firestore listeners** (or simple polling for MVP) | Live ticket status without building a websocket layer. |
| Auth | **Firebase Auth** (or JWT in FastAPI) | Don't overbuild auth — pick one. |
| Deploy | Frontend → Vercel, Backend → Railway/Render, DB → managed MySQL | All have free tiers. |

---

## 4. Database schema

```sql
-- Users
users(
  id PK, name, email UNIQUE, password_hash (or firebase_uid),
  role ENUM('enduser','technician','admin'),
  team VARCHAR,           -- e.g. 'network','hardware','access'
  created_at
)

-- Tickets
tickets(
  id PK, user_id FK,
  subject, description TEXT,
  category ENUM('hardware','software','network','access','account','other'),
  priority ENUM('low','medium','high','critical'),
  status ENUM('new','ai_handling','deflected','escalated','assigned','in_progress','resolved','closed'),
  assigned_to FK NULL,    -- technician user id
  sla_due DATETIME NULL,
  created_at, updated_at, resolved_at NULL
)

-- Every message in the ticket thread (user, AI, or technician)
ticket_messages(
  id PK, ticket_id FK,
  sender_type ENUM('user','ai','technician'),
  sender_id FK NULL,
  body TEXT,
  created_at
)

-- Knowledge base
kb_articles(
  id PK, title, body TEXT, tags VARCHAR,
  created_at, updated_at,
  FULLTEXT(title, body)   -- MySQL full-text search for MVP
)

-- The handover briefing (the star artifact)
handover_briefings(
  id PK, ticket_id FK,
  summary TEXT,             -- one-paragraph problem summary
  user_tried TEXT,          -- what the user already did
  ai_tried TEXT,            -- what the AI already attempted
  likely_causes JSON,       -- ranked list of probable root causes
  suggested_steps JSON,     -- recommended next actions for the tech
  related_ticket_ids JSON,  -- similar resolved tickets
  generated_at
)

-- Audit + metrics: log every AI decision
ai_actions(
  id PK, ticket_id FK,
  action_type ENUM('classify','deflect_attempt','handover'),
  input_snapshot TEXT, output_snapshot TEXT,
  tokens_used INT NULL,
  created_at
)

-- Optional (Phase 5+)
sla_policies(id PK, priority, response_minutes, resolution_minutes)
ticket_ratings(id PK, ticket_id FK, rating INT, comment, created_at)
```

---

## 5. The AI layer — the heart of the project

Three separate Claude calls. Keep them separate (easier to debug, log, and demo). Each returns **strict JSON** so your backend can act on it.

### AI Job 1 — Classify & route
**System prompt:**
```
You are an IT service-desk triage engine. Given a support ticket, classify it.
Respond with ONLY valid JSON, no preamble, no markdown:
{
  "category": "hardware|software|network|access|account|other",
  "priority": "low|medium|high|critical",
  "suggested_team": "short team/skill name",
  "tags": ["keyword1","keyword2"]
}
Priority guidance: critical = many users or business-stopping;
high = one user fully blocked; medium = degraded but working;
low = question or minor.
```
**User content:** the ticket subject + description.

### AI Job 2 — Deflection (try to resolve now)
**System prompt:**
```
You are an IT self-service assistant. You are given a user's problem and a set
of knowledge-base articles. Decide whether the problem can be resolved right now
using those articles.
Respond with ONLY valid JSON:
{
  "can_resolve": true|false,
  "answer": "clear step-by-step fix for the user, or empty if can_resolve is false",
  "used_article_ids": [ids you relied on],
  "confidence": "low|medium|high"
}
Only set can_resolve to true if the articles genuinely cover the issue.
If unsure, set can_resolve to false — never guess at a fix that could make it worse.
```
**User content:** the ticket text + the top-N KB articles retrieved by full-text search.

### AI Job 3 — Handover briefing (THE star feature)
**System prompt:**
```
You are an IT support handover writer. A ticket is being escalated from the AI
assistant to a human technician. Write a briefing so the technician can start
work immediately WITHOUT asking the user to repeat anything.
You are given: the full ticket conversation, what the AI already tried, and
similar past resolved tickets.
Respond with ONLY valid JSON:
{
  "summary": "one tight paragraph: what is wrong, for whom, since when",
  "user_tried": "what the user reported already doing",
  "ai_tried": "what the AI assistant already attempted and the result",
  "likely_causes": ["most probable cause first", "..."],
  "suggested_steps": ["concrete next action for the tech", "..."],
  "related_tickets": ["#id — one line on how it was resolved"]
}
Be specific and factual. Do not invent details not present in the input.
```
**User content:** full `ticket_messages` thread + the `ai_actions` deflect output + top matched past tickets.

> **KB / similar-ticket matching:** MVP = MySQL `FULLTEXT` search on `kb_articles` and on resolved `tickets`. Upgrade later = generate embeddings and store vectors for semantic search. Start simple.

---

## 6. API endpoints (FastAPI)

```
POST   /auth/login                 (or use Firebase Auth on the client)
GET    /me

POST   /tickets                    create ticket → triggers AI Job 1 + 2
GET    /tickets                    list (filter by status/assignee/priority)
GET    /tickets/{id}               detail incl. messages + briefing
PATCH  /tickets/{id}               assign / change status
POST   /tickets/{id}/messages      add a message (user or technician)
POST   /tickets/{id}/escalate      manual escalate → triggers AI Job 3
POST   /tickets/{id}/resolve

GET    /kb                         list / search articles
POST   /kb                         create (admin)
PATCH  /kb/{id}
DELETE /kb/{id}

GET    /metrics                    deflection rate, avg handover time, backlog, SLA breaches
```

---

## 7. Screens

**End-user portal**
- Submit ticket form (subject + description).
- Ticket thread view: chat-style, shows AI's deflection answer, "This fixed it ✅ / Still broken ❌" buttons.
- "My tickets" list with live status.

**Technician dashboard** *(most important screen — this is your demo money shot)*
- Queue: sortable by priority / SLA / category.
- Ticket detail: **the handover briefing panel is the first thing you see** — summary, what was tried, ranked likely causes, suggested steps, links to related tickets. Below it, the full thread. A reply box + "Resolve" button.

**Admin / manager**
- KB article manager (CRUD).
- **Metrics dashboard:** deflection rate %, average handover context time, open backlog count, SLA breach count, tickets by category (chart).

---

## 8. Build roadmap (do it in this order)

| Phase | What you build | Ship when |
|-------|----------------|-----------|
| **0. Setup** | Repo, React+Vite+Tailwind, FastAPI skeleton, MySQL schema, auth. | Login works. |
| **1. Core ticketing (NO AI yet)** | Create ticket, list, detail, add messages, assign, resolve. | You have a working plain helpdesk. |
| **2. AI Job 1 — classify/route** | On ticket create, call Claude → auto-fill category/priority/team. Log to `ai_actions`. | New tickets self-categorize. |
| **3. AI Job 2 — deflection** | KB full-text search + Claude deflection attempt shown to user, with "fixed / still broken" buttons. | AI closes some tickets on its own. |
| **4. AI Job 3 — handover briefing** ⭐ | On escalation, generate + store the briefing; render the technician panel. | **This is the finished differentiator — demo-ready.** |
| **5. Metrics dashboard** | Compute deflection %, handover time, backlog; charts. | You have numbers for your CV. |
| **6. Polish** | SLA timers + breach alerts, ratings, deploy live, seed demo data. | Public demo link + README. |

**Ship Phase 4 first as your "done" milestone.** Phases 5–6 make it look professional but the differentiator is the briefing.

---

## 9. What to measure (put these on your CV)

- **Deflection rate:** % of tickets closed by AI with no human. (Industry target: 20–40%.)
- **Handover context time:** technician time-to-first-action *without* a briefing vs *with* one. Run both modes on the same seed tickets and show the drop.
- **First-contact resolution** and **backlog size** before/after.

CV line example: *"Built an AI service desk that auto-deflected ~X% of L1 tickets and cut technician handover-context time by Y% via auto-generated briefings (React, FastAPI, Claude API, MySQL)."*

---

## 10. ⭐ Ready-to-paste build prompt (for Claude Code / Cursor / any AI IDE)

Copy everything in this block into your AI coding tool to scaffold the project:

```
Build a full-stack web app called "RelayDesk" — an AI IT service desk whose
differentiating feature is a context-preserving handover from AI to human technician.

STACK: React (Vite) + Tailwind frontend; FastAPI (Python) backend; MySQL database;
Anthropic Claude API (model claude-sonnet-4-6) for AI. Use Firebase Auth for login
and Firestore listeners for live ticket status. Never hardcode the API key — read
it from an environment variable.

ROLES: enduser, technician, admin.

CORE FLOW: when a ticket is created, call Claude to (1) classify it into
category/priority/team as strict JSON, then (2) attempt to resolve it from
knowledge-base articles (MySQL FULLTEXT search) and show the answer to the user
with "fixed / still broken" buttons. If the user says still broken, or clicks
escalate, call Claude a third time to generate a HANDOVER BRIEFING (summary,
what the user tried, what the AI tried, ranked likely causes, suggested next
steps, related resolved tickets) and store it. The technician ticket view must
show this briefing panel FIRST, above the message thread.

DATABASE TABLES: users, tickets, ticket_messages, kb_articles (FULLTEXT indexed),
handover_briefings, ai_actions (audit log of every AI call). Use the field
definitions I will paste.

SCREENS: (a) end-user portal — submit ticket, chat-style thread, my-tickets list;
(b) technician dashboard — priority-sorted queue and a ticket detail where the
handover briefing is the first element; (c) admin — knowledge-base CRUD and a
metrics dashboard showing deflection rate, average handover time, backlog, and
tickets-by-category chart.

Build in phases and pause after each so I can test: (0) setup + auth,
(1) plain ticketing with no AI, (2) AI classification, (3) AI deflection,
(4) AI handover briefing, (5) metrics dashboard, (6) SLA timers + deploy.

All Claude calls must return strict JSON (no markdown, no preamble); parse safely
and log input/output to ai_actions. Start with Phase 0 and show me the folder
structure and setup commands.
```

Paste the schema from Section 4 and the three AI prompts from Section 5 when the tool reaches those phases.

---

*Built for Rimzan — start with Phase 0, ship through Phase 4, then add metrics. The briefing is the whole point; make that screen beautiful.*
