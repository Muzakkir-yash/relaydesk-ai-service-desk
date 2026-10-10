"""
Public demo support.

DEMO_MODE=true  — the shared demo logins (@company.com, from seed.py) can't
                  have their password, role or details changed, or be
                  deleted, so one visitor can't lock everyone else out.
SEED_DEMO_DATA=true — on start-up, an empty database is filled with the demo
                  data. On free hosts that wipe files on restart, every
                  restart therefore begins with a clean demo.
"""

import logging
import os
import runpy

from fastapi import HTTPException

from config import settings, BACKEND_DIR

logger = logging.getLogger("relaydesk.demo")

DEMO_EMAIL_DOMAIN = "@company.com"


def is_protected_demo_account(user) -> bool:
    return bool(settings.DEMO_MODE and user and (user.email or "").lower().endswith(DEMO_EMAIL_DOMAIN))


def guard_demo_account(user) -> None:
    if is_protected_demo_account(user):
        raise HTTPException(status_code=403,
                            detail="This is a shared demo account, so it can't be changed on the public demo.")


def seed_if_empty() -> None:
    if not settings.SEED_DEMO_DATA:
        return
    from database import SessionLocal
    import models

    db = SessionLocal()
    try:
        empty = db.query(models.User.id).first() is None
    finally:
        db.close()
    if empty:
        logger.info("Empty database: loading demo data")
        runpy.run_path(os.path.join(BACKEND_DIR, "seed.py"), run_name="demo_seed")
