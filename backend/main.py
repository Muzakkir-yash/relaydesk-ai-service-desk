"""
RelayDesk — FastAPI main entry point.
"""

import logging
import os
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from config import settings
from database import SessionLocal, run_migrations
import models
from kb_library import sync_kb_library
from ai.article_matcher import article_matcher
from ai.intent_model import warm_up

from routers import auth, tickets, kb, metrics, users, announcements, notifications

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

# ── Bring the database schema up to date (Alembic) ───────────────
run_migrations()

# Add any built-in knowledge-base articles this database doesn't have yet
# (never overwrites articles staff have edited)
with SessionLocal() as _db:
    sync_kb_library(_db, models)


def _warm_up_chatbot() -> None:
    warm_up()
    with SessionLocal() as db:
        matcher = article_matcher(tickets._published_articles(db))
    if matcher:
        matcher.ranking("warm up")  # loads the meaning model (first run: one-time download)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Load the chatbot's ML models in the background so the server is up
    # immediately and the first chat doesn't wait for training.
    threading.Thread(target=_warm_up_chatbot, name="model-warm-up", daemon=True).start()
    yield


# ── App ──────────────────────────────────────────────────────────
app = FastAPI(
    title="RelayDesk API",
    description="AI IT Service Desk with context-preserving handover",
    version="1.1.0",
    lifespan=lifespan,
)

# ── CORS ─────────────────────────────────────────────────────────
# Any localhost port is allowed in development only (Vite, live-server, ...).
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_origin_regex=None if settings.is_production else r"http://(localhost|127\.0\.0\.1)(:\d+)?",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_security_headers(request, call_next):
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    if request.url.path.endswith((".js", ".css", ".html")) or request.url.path == "/":
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    return response

# ── Routers ───────────────────────────────────────────────────────
app.include_router(auth.router)
app.include_router(tickets.router)
app.include_router(kb.router)
app.include_router(metrics.router)
app.include_router(users.router)
app.include_router(announcements.router)
app.include_router(notifications.router)


@app.get("/health")
def health():
    return {"status": "ok", "app": "RelayDesk"}


class PublicStaticFiles(StaticFiles):
    """Serves the plain HTML/CSS/JS frontend while refusing build tooling,
    dependencies, dotfiles and the legacy React sources in the same folder."""

    BLOCKED_PREFIXES = ("node_modules", "src", "dist", "public")
    BLOCKED_FILES = {"package.json", "package-lock.json", "vite.config.js", "postcss.config.js",
                     "tailwind.config.js", "README.md"}

    async def get_response(self, path, scope):
        parts = [p for p in path.replace("\\", "/").split("/") if p and p != "."]
        if parts and (
            parts[0] in self.BLOCKED_PREFIXES
            or parts[-1] in self.BLOCKED_FILES
            or any(p.startswith(".") for p in parts)
        ):
            raise StarletteHTTPException(status_code=404)
        return await super().get_response(path, scope)


# ── Mount Static Frontend (Pure HTML, CSS, JS) ─────────────────────
frontend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend"))
if os.path.isdir(frontend_dir):
    app.mount("/", PublicStaticFiles(directory=frontend_dir, html=True), name="frontend")


if __name__ == "__main__":
    import uvicorn
    # Auto-reload restarts the server when code changes — handy while developing,
    # but it doubles start-up time. start.bat turns it off (RELAYDESK_RELOAD=0).
    reload = not settings.is_production and os.environ.get("RELAYDESK_RELOAD", "1") != "0"
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=reload)
