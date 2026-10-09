"""
Shared audit-log writer used by every router.
"""

import logging
from typing import Optional

from sqlalchemy.orm import Session

import models

logger = logging.getLogger("relaydesk.audit")


def actor_type_for(user: Optional[models.User]) -> str:
    """Map a user's role onto the AuditLog.actor_type enum (enduser -> "user")."""
    if user is None:
        return "ai"
    return user.role if user.role in ("technician", "admin") else "user"


def write_audit(
    db: Session,
    actor: Optional[models.User],
    action: str,
    target_type: Optional[str] = None,
    target_id: Optional[int] = None,
    detail: Optional[str] = None,
    actor_type: Optional[str] = None,
) -> None:
    """Persist an audit entry. Never raises — a failed audit write must not
    break the request, but it must not leave the session unusable either.
    Pass actor_type for unauthenticated actions (e.g. a failed sign-in)."""
    try:
        db.add(models.AuditLog(
            actor_type=actor_type or actor_type_for(actor),
            actor_id=actor.id if actor else None,
            action=action,
            target_type=target_type,
            target_id=target_id,
            detail=detail,
        ))
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("AuditLog write failed for action=%s", action)
