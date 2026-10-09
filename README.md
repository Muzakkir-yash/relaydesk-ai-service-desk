# RelayDesk — AI IT Service Desk

> **An AI helpdesk where the AI→human handover is a first-class feature.** When the AI can't resolve a ticket, the technician gets a pre-assembled briefing — problem summary, what was tried, likely causes, suggested steps, and similar past tickets — so nobody ever has to restate their issue.

---

## Tech Stack

| Layer | Tech |
|-------|------|
| Frontend | Pure HTML5 + CSS3 + Vanilla JavaScript (Zero Build Step / No Node needed) |
| Backend | FastAPI (Python) + SQLAlchemy |
| Database | SQLite (dev) / MySQL (prod) |
| AI | **Free built-in engine (default)** — rule-based chatbot, BM25 knowledge search, learning loop. Paid Claude API support exists but is **switched off** (`ENABLE_PAID_AI=false`) and never called |
| Auth | JWT in an httpOnly session cookie (python-jose + bcrypt), rate-limited sign-in |
| Migrations | Alembic (applied automatically on startup) |

---

## Quick Start (Single Server — Zero Node.js Required)

### 1. Start the System

```bash
cd backend
venv\Scripts\activate          # Windows (or: source venv/bin/activate on Mac/Linux)
pip install -r requirements.txt
copy .env.example .env         # (cp on Mac/Linux) then set SECRET_KEY / ANTHROPIC_API_KEY
python seed.py                 # Applies migrations, then seeds demo users, KB articles & tickets
python main.py                 # Starts server on http://localhost:8000
```

### 2. Open Your Browser
Navigate directly to:
👉 **`http://localhost:8000`**

FastAPI directly serves the entire HTML/CSS/JS frontend without requiring `npm`, Node.js, or any compilation steps!

The HTML pages in `frontend/` are the whole UI — no Node.js, npm or build step.

---

## Demo Credentials (after seeding)

| Role | Email | Password |
|------|-------|----------|
| End User | alice@company.com | password123 |
| Technician | charlie@company.com | password123 |
| Admin | admin@company.com | password123 |

---

## Core Flow

```
User submits ticket
      │
      ▼
[AI Job 1] Classify → category, priority, SLA, team, mood
      │
      ▼
[AI Job 2] Deflect → search KB, try to resolve now
      │
      ├── Fixed? → User confirms → DEFLECTED (auto-closed)
      │
      └── Still broken → Escalate
                  │
                  ▼
      [AI Job 3] Handover Briefing ⭐
                  │
                  ▼
      Technician queue with full briefing attached
```

---

## Features

### End User Portal
- Submit ticket with AI classification + deflection attempt
- "Yes, it's fixed ✅ / Still broken ❌" buttons
- Chat-style ticket thread with live polling
- Star rating (1–5 ⭐) after resolution
- My tickets list with status badges

### Technician Dashboard
- Priority-sorted ticket queue with SLA timers
- **Handover Briefing Panel** (the star feature) — shown first on every escalated ticket
  - Problem summary
  - What user tried
  - What AI tried  
  - Ranked likely root causes
  - Recommended resolution steps
  - Related past tickets
- User Mood indicator (calm / neutral / frustrated)
- Auto-assignment by problem weight + support tier (L1/L2/L3)

### Admin Panel
- Knowledge Base CRUD (full-text search)
- Metrics dashboard: deflection rate, 7-day trend, avg resolution time, SLA breaches, category/status charts
- **User Management** — create, edit (name, role, tier, team) and delete users
- **Knowledge Base editing** — edit or delete articles, approve AI-learned drafts
- **Audit Log page** — searchable, filterable history of every sign-in, ticket change and admin action

---

## API Endpoints

```
POST   /auth/register     (rate-limited per IP)
POST   /auth/login        → sets httpOnly session cookie (rate-limited on failures)
POST   /auth/logout
GET    /auth/me

POST   /tickets              → AI Job 1 + 2 triggered
GET    /tickets
GET    /tickets/{id}
PATCH  /tickets/{id}
POST   /tickets/{id}/messages
POST   /tickets/{id}/escalate   → AI Job 3 triggered
POST   /tickets/{id}/resolve
POST   /tickets/{id}/confirm-resolved
POST   /tickets/{id}/rate

GET    /kb
POST   /kb            (admin)
PATCH  /kb/{id}       (admin)
DELETE /kb/{id}       (admin)
POST   /kb/{id}/feedback ("was this helpful?" — feeds chatbot ranking)

GET    /metrics
GET    /metrics/audit-log   (admin — filter by actor_type, action, q; paged)
GET    /metrics/audit-log/actions (admin)

GET    /users         (admin)
PATCH  /users/{id}    (admin — name, role, tier, team)
DELETE /users/{id}    (admin — refused for users with ticket history)

GET    /health
```

Interactive docs: http://localhost:8000/docs

---

## Run Tests

```bash
cd backend
pip install -r requirements-dev.txt
python -m pytest     # isolated: temp SQLite DB, AI in offline mode — never touches relaydesk.db
```

The suite covers the full ticket lifecycle (create → classify → deflect → escalate → briefing → resolve → rate), role/ownership checks, input validation, cookie sessions/CSRF/rate limits, AI-output parsing, and the exact shape of Claude requests (via a fake client, so no API key is needed).

The older scripts `test_suite.py` and `qa_chat_test_suite.py` run against the **live** `relaydesk.db` and write to it — point `DATABASE_URL` at a copy before running them.

---

## The Support Chatbot — and how it learns

Users chat with the assistant first; a technician is only involved if it can't help.

- **Conversation:** the free built-in engine runs the chat by default. (Optional, paid and OFF: only with `ENABLE_PAID_AI=true` plus a key would Claude run it instead.) The assistant runs the chat turn by turn: it asks one clarifying question when the problem is vague, gives numbered steps grounded in your knowledge base, and decides when to end — `resolved` (user confirmed the fix) or `escalate` (user asked for a person, fix needs admin rights/hardware/approval, two approaches failed, or a security incident). Every AI job works fully offline at no cost.
- **Company knowledge:** each turn searches the published KB with BM25 ranking (`ai/knowledge.py`), using the user's whole description, not just the last line.
- **Learns from technicians:** when a technician resolves an escalated ticket, the AI drafts a KB article from the fix (`ai/learning.py`), stripped of personal details. It appears on the Knowledge Base page as **"Learned by the AI — awaiting approval"**. Once staff approve it, the chatbot uses it for every future user with that problem. Drafts are never shown to users or the bot before approval.
- **Learns from outcomes:** every chat that ends "fixed" or "escalated" counts for or against the articles the bot used, and that track record boosts or demotes them in future searches.
- **Trained machine-learning model (free):** two text classifiers built with scikit-learn (BSD licence, runs offline — no account, no key, no cost) are trained from the example sentences in `backend/ai/training/` — `intents.json` (problem, fixed, still broken, wants a person, security incident, request, outage, greeting, vague) and `categories.json`. They combine word and character n-grams, so typos and new phrasings are understood, and they report a confidence: below 50% the bot falls back to its hand-written rules. Training takes under a second at start-up. **To make it smarter, add real user messages to those JSON files and restart.**
- **Measured:**
  ```bash
  python evals/train_report.py                      # cross-validated accuracy of each model
  python evals/run_chatbot_eval.py --set fresh4     # honest score (written after training was frozen)
  ```
  | Test set | Keyword rules only | Trained model |
  |---|---|---|
  | `main`, `holdout`, `fresh`–`fresh3` (seen while improving the training data) | 40–100% | 95–100% |
  | **`fresh4` — 25 conversations written after the latest training was frozen** | **40%** | **84%** (honest score) |

  Training uses augmentation: every example also gets misspelled copies, and `templates.json` generates sentences like "{everyone in finance} can't {get emails}" or "every {desk phone} in the {building} {has gone dead}". Cross-validated accuracy: intent ≈ **85%**, category 79% → **85%**. Intents: problem, fixed, still broken, wants a person, security incident, request, outage, policy question, greeting, vague. The trained model is cached in `ai/training/.model_cache/` and rebuilt automatically when the training files change; the server loads it in the background at start-up.

  Safety-critical cases (security incidents, lost/stolen devices, found USB sticks) are caught by **both** the model and the rules, so one layer failing doesn't miss them. Remaining misses on `fresh4` (next training round): a suspicious file sent over Teams posing as a payslip (not flagged as security), "signal is terrible near the kitchen" (wrongly treated as an outage), "none of our laptops boot after the update" (not marked critical), and one category. **Never copy test sentences into the training files** — it makes the scores meaningless; write a new test set after each round of training instead.

---

## Database Migrations

The schema is managed with Alembic (`backend/migrations/`). The server and `seed.py` run `alembic upgrade head` automatically on startup. A database created before migrations existed is detected, brought up to the baseline, stamped, and upgraded — no data is touched.

```bash
cd backend
alembic current                                   # show the database's revision
alembic revision --autogenerate -m "add x column" # after changing models.py — review the file!
alembic upgrade head                              # apply (also happens on startup)
alembic check                                     # fails if models.py and the DB have drifted
```

---

## Cost: strictly free

This project uses **no paid services** and no free-trial services that later charge. Everything runs locally on open-source software. The only paid integration in the code — the Claude API — is **switched off** by `ENABLE_PAID_AI=false` (the default): while it is off, no request is ever sent, even if an API key is filled in. `tests/test_no_paid_services.py` fails the build if that guarantee is ever broken.

---

## Security Notes

- **Sessions:** login sets an **httpOnly, SameSite=Lax** cookie (`Secure` in production), so page scripts can never read the token. Cookie-authenticated writes must send `X-Requested-With: XMLHttpRequest` (CSRF guard). API clients can still use `Authorization: Bearer <token>` from the login response.
- **Rate limits:** 5 failed sign-ins per IP+email and 20 per IP per 15 minutes; 10 sign-ups per IP per hour (all configurable). Limits are kept in memory per server process — with several workers or instances, move them to a shared store such as Redis.
- Public sign-up (`/auth/register`) always creates an **end user**; technician/admin accounts are created by an admin via `POST /users`.
- All request bodies are validated (enum statuses/priorities/roles, length limits, password ≥ 8 chars, attachment count/size and URL scheme).
- The frontend renders every server value through `js/utils.js` (`escapeHtml`, `safeUrl`).
- The static mount refuses `node_modules/`, `src/`, `dist/`, dotfiles and build config.
- With `ENVIRONMENT=production` the app refuses to start with a default `SECRET_KEY`, never silently falls back from MySQL to SQLite, and only allows the configured CORS origins.
- Technician playbooks and device ping are **simulations** for the demo and are labelled as such in the UI and ticket thread.

---

## Deploy

### Backend (Railway / Render)
- Set environment variables from `backend/.env.example` (`ENVIRONMENT=production`, a strong `SECRET_KEY`, `DATABASE_URL`, `CORS_ORIGINS`)
- Uses `Procfile`: `web: cd backend && uvicorn main:app --host 0.0.0.0 --port $PORT --proxy-headers --forwarded-allow-ips="*"` (proxy headers give the rate limiter the real client IP behind the platform's load balancer)
- Migrations run automatically on boot.
- The backend serves the frontend too, so a single service is enough.

### Switch to MySQL (production)
```env
DATABASE_URL=mysql+pymysql://user:password@host:3306/relaydesk
```

---

## CV Metrics to Highlight

- **Deflection rate** — % of tickets AI resolves with no human (target: 20–40%)
- **Handover context time** — drops toward 0 with pre-assembled briefings
- **AI Jobs** — 3 separate Claude calls: classify, deflect, brief

> *Built with vanilla JS, FastAPI, SQLite/MySQL, Anthropic Claude API*
