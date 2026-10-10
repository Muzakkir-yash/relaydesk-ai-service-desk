"""
In-app notifications (the bell in the header). Free — no email service.
"""

import logging
from typing import Iterable, Optional

from sqlalchemy.orm import Session

import models

logger = logging.getLogger("relaydesk.notifications")


def notify(
    db: Session,
    user_ids: Iterable[Optional[int]],
    kind: str,
    message: str,
    ticket_id: Optional[int] = None,
    link: Optional[str] = None,
    exclude_user_id: Optional[int] = None,
) -> None:
    """Create a notification for each user. Never raises — a failed
    notification must not break the request that triggered it.
    `exclude_user_id` skips the person who caused the event."""
    recipients = {uid for uid in user_ids if uid and uid != exclude_user_id}
    if not recipients:
        return
    if link is None and ticket_id is not None:
        link = f"/ticket.html?id={ticket_id}"
    try:
        for uid in recipients:
            db.add(models.Notification(user_id=uid, ticket_id=ticket_id, kind=kind,
                                       message=message[:300], link=link))
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("Notification write failed (%s)", kind)


def staff_ids(db: Session, roles=("admin",)) -> list:
    return [uid for (uid,) in db.query(models.User.id).filter(models.User.role.in_(roles)).all()]
