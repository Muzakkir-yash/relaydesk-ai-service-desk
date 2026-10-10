<p align="center">
  <img src="frontend/assets/logo.jpg" alt="RelayDesk Logo" width="120" />
</p>

<h1 align="center">RelayDesk — AI IT Service Desk</h1>

<p align="center">
  <strong>An intelligent helpdesk where AI → human handover is a first-class feature</strong><br/>
  When the AI cannot resolve a ticket, the technician receives a pre-assembled briefing — problem summary, what was tried, likely root causes, suggested steps, and similar past tickets — so no user ever has to restate their issue.
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10+-3776AB?style=for-the-badge&logo=python&logoColor=white" />
  <img src="https://img.shields.io/badge/FastAPI-0.110+-009688?style=for-the-badge&logo=fastapi&logoColor=white" />
  <img src="https://img.shields.io/badge/Frontend-Vanilla%20JS-F7DF1E?style=for-the-badge&logo=javascript&logoColor=black" />
  <img src="https://img.shields.io/badge/Database-SQLite%20%2F%20MySQL-4479A1?style=for-the-badge&logo=mysql&logoColor=white" />
  <a href="https://github.com/Muzakkir-yash/relaydesk-ai-service-desk/actions/workflows/tests.yml"><img src="https://github.com/Muzakkir-yash/relaydesk-ai-service-desk/actions/workflows/tests.yml/badge.svg" alt="Tests" height="28" /></a>
  <img src="https://img.shields.io/badge/Deploy-Render%20(free)-6C63FF?style=for-the-badge" />
</p>

---

## Table of Contents

- [Overview](#overview)
- [Tech Stack](#tech-stack)
- [Architecture and Core Flow](#architecture-and-core-flow)
- [Features](#features)
- [Quick Start](#quick-start)
- [Demo Credentials](#demo-credentials)
- [Environment Variables](#environment-variables)
- [API Reference](#api-reference)
- [AI Engine and Learning](#ai-engine-and-learning)
- [Testing](#testing)
- [Database Migrations](#database-migrations)
- [Security](#security)
- [Deployment](#deployment)
- [Project Structure](#project-structure)

---

## Overview

RelayDesk is a full-stack AI-powered IT service desk built with **FastAPI** and **Vanilla JavaScript**. It models the complete support lifecycle — from ticket submission and AI-powered self-service deflection, through to intelligent human handover with a fully automated context briefing for technicians.

**Key differentiator:** Most helpdesks treat AI as a chatbot add-on. RelayDesk treats the AI to human transition as the most important moment in the support journey, and optimises for it with a purpose-built **Handover Briefing Panel** that lets technicians pick up any ticket cold — in seconds.

---

## Tech Stack

| Layer | Technology | Notes |
|---|---|---|
| **Frontend** | HTML5 + CSS3 + Vanilla JS | Zero build step — no Node.js required |
| **Backend** | FastAPI (Python) + SQLAlchemy | Serves both API and static frontend |
| **Database** | SQLite (dev) / MySQL (prod) | Auto-detected; zero config for local dev |
| **AI Engine** | scikit-learn + BM25 (built-in, offline) | No API key, no cost, no rate limits |
| **Auth** | JWT in httpOnly cookie (python-jose + bcrypt) | CSRF-guarded, rate-limited login |
| **Migrations** | Alembic | Auto-applied on startup |
| **Testing** | pytest (80 tests) | Isolated temp DB, no network calls |

---

## Architecture and Core Flow

```
+-------------------------------------------------------------+
|                        User Portal                          |
+----------------------------+--------------------------------+
                             |  POST /tickets
                             v
               +---------------------------+
               |   AI Job 1 -- Classify    |
               |   category  priority      |
               |   SLA  team  mood         |
               +------------+--------------+
                            |
                            v
               +---------------------------+
               |   AI Job 2 -- Deflect     |
               |   BM25 KB search          |
               |   Conversational chat     |
               +------------+--------------+
                            |
            +---------------+---------------+
            |                               |
       Resolved                       Still Broken
     User confirms fix              Escalate to human
     Ticket auto-closed                     |
                                            v
                           +------------------------------+
                           |  AI Job 3 -- Handover    *  |
                           |  Problem summary             |
                           |  What user tried             |
                           |  What AI tried               |
                           |  Ranked root causes          |
                           |  Resolution steps            |
                           |  Related past tickets        |
                           +------------+-----------------+
                                        |
                                        v
                           +------------------------------+
                           |  Technician Queue            |
                           |  Full briefing attached      |
                           |  SLA timer  Mood badge       |
                           +------------------------------+
```

---

## Features

### End User Portal
- Submit ticket with instant AI classification and deflection attempt
- Conversational AI chat with step-by-step troubleshooting grounded in the KB
- "Fixed / Still broken" confirmation buttons
- Chat-style ticket thread with live polling
- Star rating (1–5) after resolution
- My Tickets list with real-time status badges
- 🔔 Notifications when IT replies or a ticket is resolved
- "Forgot password?" request and self-service password change

### Technician Dashboard
- Priority-sorted queue with live SLA countdown timers
- **Handover Briefing Panel** — shown first on every escalated ticket:
  - Problem summary (what the user described)
  - What the user already tried
  - What the AI already tried
  - Ranked likely root causes
  - Recommended resolution steps
  - Similar resolved tickets for reference
- User Mood indicator (calm / neutral / frustrated)
- Auto-assignment by problem weight and support tier (L1 / L2 / L3)
- 🔔 Notifications when a ticket is escalated or assigned to you, or the user replies
- Broadcast a Major Incident banner to everyone, and mark it resolved when fixed

### Admin Panel
- **Knowledge Base CRUD** — full-text search, article approval workflow
- **Metrics Dashboard** — deflection rate, 7-day trend chart, avg resolution time, SLA breach count, category/status charts
- **User Management** — create, edit (name, role, tier, team), and delete users
- **AI Draft Approval** — approve or reject articles the AI learned from technician resolutions
- **Audit Log** — searchable, filterable, paginated history of every sign-in, ticket change, and admin action
- **Password resets** — one-time 24-hour reset links for users who asked (no email service needed)

---

## Quick Start

> **Requirements:** Python 3.10+ | No Node.js needed

**Windows, easiest:** double-click **`start.bat`** in the project folder. It uses the project's own Python environment, installs anything missing on the first run, starts the server and opens http://localhost:8000. Close its window to stop the server.

**Manual setup:**

```bash
# 1. Clone the repository
git clone https://github.com/Muzakkir-yash/relaydesk-ai-service-desk.git
cd relaydesk-ai-service-desk/backend

# 2. Create and activate a virtual environment
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # macOS / Linux

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment
copy .env.example .env         # Windows
# cp .env.example .env         # macOS / Linux
# Edit .env and set at minimum: SECRET_KEY

# 5. Seed the database (runs migrations + demo data)
python seed.py

# 6. Start the server
python main.py
```

Then open **http://localhost:8000** in your browser.

> ⚠️ Always run with the virtual environment active (step 2). Plain `python main.py` without it fails with `No module named 'sklearn'`, because the libraries are installed inside `backend\venv`.

FastAPI serves the entire frontend — no `npm install`, no build step, no separate dev server.

---

## Demo Credentials

After running `python seed.py`, the following accounts are ready:

| Role | Email | Password |
|---|---|---|
| End User | alice@company.com | `password123` |
| Technician | charlie@company.com | `password123` |
| Admin | admin@company.com | `password123` |

---

## Environment Variables

Copy `backend/.env.example` to `backend/.env` and configure:

| Variable | Required | Description |
|---|---|---|
| `SECRET_KEY` | Yes | Secret for JWT signing — use a long random string in production |
| `DATABASE_URL` | Optional | Defaults to `sqlite:///relaydesk.db`. Set to MySQL for production |
| `ENVIRONMENT` | Optional | Set to `production` to enable strict mode |
| `CORS_ORIGINS` | Production | Comma-separated allowed origins |
| `ENABLE_PAID_AI` | Optional | `false` by default. Set `true` plus `ANTHROPIC_API_KEY` to enable Claude |
| `ANTHROPIC_API_KEY` | Optional | Only required if `ENABLE_PAID_AI=true` |
| `DEMO_MODE` | Optional | `true` on a public demo: the shared `@company.com` demo accounts can't be changed or deleted, and the login page shows one-click demo accounts |
| `SEED_DEMO_DATA` | Optional | `true` to load the demo data automatically whenever the database is empty |

---

## API Reference

### Authentication

```
POST   /auth/register          Register (rate-limited per IP, creates end user)
POST   /auth/login             Login -> sets httpOnly session cookie
POST   /auth/logout            Clear session cookie
GET    /auth/me                Current user info
POST   /auth/forgot-password   Ask IT for a reset link (same reply whether or not the account exists)
POST   /auth/reset-password    Set a new password with a one-time link (signs out all sessions)
POST   /auth/change-password   Change your own password
```

### Tickets

```
POST   /tickets                Create ticket -> triggers AI Job 1 + Job 2
GET    /tickets                List tickets (filtered by role)
GET    /tickets/{id}           Get single ticket with full thread
PATCH  /tickets/{id}           Update ticket (status, priority, assignee)
POST   /tickets/{id}/messages  Add message to thread
POST   /tickets/{id}/escalate  Escalate -> triggers AI Job 3 (handover briefing)
POST   /tickets/{id}/resolve   Technician marks resolved
POST   /tickets/{id}/confirm-resolved  User confirms fix
POST   /tickets/{id}/rate      Submit star rating (1-5)
```

### Knowledge Base

```
GET    /kb                     List articles (BM25 search via ?q=)
POST   /kb                     Create article (admin)
PATCH  /kb/{id}                Edit article (admin)
DELETE /kb/{id}                Delete article (admin)
POST   /kb/{id}/feedback       Helpfulness feedback — feeds chatbot ranking
```

### Metrics and Admin

```
GET    /metrics                        Dashboard metrics
GET    /metrics/audit-log              Audit log (admin)
GET    /metrics/audit-log/actions      Available audit action types (admin)
GET    /users                          List users (admin)
PATCH  /users/{id}                     Edit user (admin)
DELETE /users/{id}                     Delete user (admin — refused if ticket history exists)
POST   /users/{id}/reset-link          One-time 24-hour password reset link (admin)
GET    /notifications                  Your notifications + unread count
POST   /notifications/{id}/read        Mark one as read
POST   /notifications/read-all         Mark all as read
GET    /health                         Health check
```

Interactive API docs: **http://localhost:8000/docs**

---

## AI Engine and Learning

### How the Chatbot Works

The built-in AI engine runs **fully offline at zero cost** — no API key, no rate limits.

| Component | Implementation |
|---|---|
| **Intent detection** | scikit-learn text classifier (word + char n-grams, confidence threshold) |
| **Category detection** | Second scikit-learn classifier, same architecture |
| **Safety fallback** | Hand-written rule set — catches all safety-critical intents regardless of model confidence |
| **KB search** | BM25 ranking over published articles (`ai/knowledge.py`) |
| **Conversation** | Turn-by-turn state machine: clarify -> suggest -> confirm -> resolve/escalate |

### Model Accuracy

| Test Set | Keyword Rules Only | Trained Model |
|---|---|---|
| `main`, `holdout`, `fresh` to `fresh3` (training-era) | 40–100% | 95–100% |
| **`fresh4` — 25 conversations written after training was frozen** | **40%** | **84%** |

> `fresh4` is the honest score — written after the training data was locked. It reflects real-world generalisation, not overfitting.

### Continuous Learning Loop

```
Technician resolves a ticket
        |
        v
AI drafts a KB article from the fix
Personal details stripped automatically
        |
        v
Article queued as "Learned by AI — awaiting approval"
        |
   Admin reviews
   +----+----+
Approve    Reject
   |
   v
Article published -> used in future chats
        |
        v
Chat outcomes (resolved / escalated) boost or demote
article ranking in future BM25 searches
```

---

## Testing

```bash
cd backend
pip install -r requirements-dev.txt
python -m pytest
```

Runs against an **isolated temporary SQLite database** — never touches `relaydesk.db`. All AI calls use a fake client — no API key required.

**Coverage (80 tests):**
- Full ticket lifecycle: create -> classify -> deflect -> escalate -> briefing -> resolve -> rate
- Role and ownership enforcement
- Input validation (enum values, length limits, password strength)
- Cookie session, CSRF guard, and rate limiting
- AI output parsing and intent model accuracy
- Exact shape of external API requests (via fake client)

### Chatbot Evaluation

```bash
python evals/train_report.py                      # cross-validated accuracy per model
python evals/run_chatbot_eval.py --set fresh4     # honest end-to-end score
```

---

## Database Migrations

Schema changes are managed with **Alembic**. Migrations run automatically on every server startup — including detecting and upgrading databases created before migrations existed.

```bash
cd backend
alembic current                                    # show current database revision
alembic revision --autogenerate -m "add column"   # generate migration from model changes
alembic upgrade head                               # apply all pending migrations
alembic check                                      # verify models.py matches the DB schema
```

---

## Security

| Area | Implementation |
|---|---|
| **Session cookies** | `httpOnly`, `SameSite=Lax`, `Secure` in production — inaccessible to JavaScript |
| **CSRF protection** | Cookie-authenticated writes require `X-Requested-With: XMLHttpRequest` |
| **Rate limiting** | 5 failed logins / IP+email per 15 min; 10 sign-ups / IP / hour (configurable) |
| **Input validation** | Enum fields, length limits, password >= 8 chars, URL scheme checks |
| **XSS prevention** | All server values rendered via `escapeHtml` / `safeUrl` in `js/utils.js` |
| **Static file safety** | Mount refuses `node_modules/`, dotfiles, and build config |
| **Production mode** | Refuses weak `SECRET_KEY`, strict CORS, no MySQL to SQLite fallback |
| **Role isolation** | Public registration creates end users only; admin/technician accounts require admin action |

---

## Deployment

### Free public demo on Render

The repo includes a [`render.yaml`](render.yaml) Blueprint that uses only Render's **free** plan.

1. Sign up at [render.com](https://render.com) with your GitHub account.
2. **New → Blueprint** → choose this repository → **Apply**.
3. Wait for the first build (a few minutes). Your demo is live at `https://relaydesk-demo.onrender.com` (or the name Render assigns).

What to expect on the free plan:
- It **sleeps after 15 minutes without visitors**; the next visit wakes it in about a minute.
- There is **no permanent disk**, so the SQLite database is wiped on every restart. `SEED_DEMO_DATA=true` reloads the demo data, so every visitor gets a clean demo, and `DEMO_MODE=true` protects the shared demo logins.
- For a permanent installation with real data, use a server with a persistent disk or MySQL (below).

### Any other host

`Procfile` start command (migrations run automatically on boot, and the backend serves the frontend — **a single service is all you need**):

```
web: cd backend && uvicorn main:app --host 0.0.0.0 --port $PORT --proxy-headers --forwarded-allow-ips="*"
```

### Switch to MySQL (Production)

```env
DATABASE_URL=mysql+pymysql://user:password@host:3306/relaydesk
ENVIRONMENT=production
```

---

## Project Structure

```
relaydesk-ai-service-desk/
|
+-- backend/
|   +-- ai/
|   |   +-- assistant.py        # Conversational turn-by-turn chat engine
|   |   +-- briefing.py         # AI Job 3 -- handover briefing generator
|   |   +-- classifier.py       # AI Job 1 -- ticket classification
|   |   +-- client.py           # AI client abstraction (built-in / Claude)
|   |   +-- deflector.py        # AI Job 2 -- self-service deflection
|   |   +-- intent_model.py     # scikit-learn intent + category classifiers
|   |   +-- knowledge.py        # BM25 knowledge base search
|   |   +-- learning.py         # Technician-resolution to KB article drafting
|   |   +-- training/           # intents.json, categories.json, templates.json
|   |
|   +-- migrations/             # Alembic migration versions
|   +-- routers/
|   |   +-- auth.py             # Authentication endpoints
|   |   +-- kb.py               # Knowledge base endpoints
|   |   +-- metrics.py          # Metrics + audit log endpoints
|   |   +-- tickets.py          # Ticket lifecycle endpoints
|   |   +-- users.py            # User management endpoints
|   |
|   +-- tests/                  # 80 pytest tests
|   +-- evals/                  # Chatbot evaluation scripts and case files
|   +-- models.py               # SQLAlchemy ORM models
|   +-- schemas.py              # Pydantic request/response schemas
|   +-- auth.py                 # JWT + bcrypt auth utilities
|   +-- audit.py                # Audit logging
|   +-- ratelimit.py            # In-memory rate limiter
|   +-- seed.py                 # Demo data seeder
|   +-- main.py                 # FastAPI app entry point
|
+-- frontend/
    +-- css/style.css           # Global styles
    +-- js/
    |   +-- api.js              # Centralised fetch wrapper
    |   +-- app.js              # App shell and routing
    |   +-- auth.js             # Auth state management
    |   +-- utils.js            # escapeHtml, safeUrl, helpers
    |
    +-- index.html              # Dashboard / redirect
    +-- login.html              # Login and register
    +-- new-ticket.html         # Ticket submission + AI chat
    +-- ticket.html             # Single ticket view
    +-- tickets.html            # My tickets list
    +-- queue.html              # Technician queue
    +-- kb.html                 # Knowledge base (admin)
    +-- metrics.html            # Metrics dashboard (admin)
    +-- users.html              # User management (admin)
    +-- audit.html              # Audit log (admin)
```

---

<p align="center">
  Built by <strong><a href="https://github.com/Muzakkir-yash">Muzakkir Yash</a></strong>
</p>
