from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from auth import get_current_user
from database import get_db
import models, schemas

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("", response_model=schemas.NotificationList)
def list_notifications(
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Your newest notifications plus the unread count (for the bell badge)."""
    mine = db.query(models.Notification).filter(models.Notification.user_id == current_user.id)
    unread = mine.filter(models.Notification.read_at.is_(None)).count()
    items = mine.order_by(models.Notification.id.desc()).limit(limit).all()
    return {"unread": unread, "items": items}


@router.post("/{notification_id}/read", status_code=204)
def mark_read(
    notification_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    note = db.query(models.Notification).filter(
        models.Notification.id == notification_id, models.Notification.user_id == current_user.id
    ).first()
    if not note:
        raise HTTPException(status_code=404, detail="Notification not found")
    if not note.read_at:
        note.read_at = datetime.utcnow()
        db.commit()
    return None


@router.post("/read-all", status_code=204)
def mark_all_read(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    db.query(models.Notification).filter(
        models.Notification.user_id == current_user.id, models.Notification.read_at.is_(None)
    ).update({"read_at": datetime.utcnow()}, synchronize_session=False)
    db.commit()
    return None
