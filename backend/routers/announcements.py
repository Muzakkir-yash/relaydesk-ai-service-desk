"""
System Announcements & Global Outage Banners (Major Incident Management / MIM)
"""

from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from database import get_db
from auth import get_current_user, require_role
from audit import write_audit
import models, schemas

router = APIRouter(prefix="/announcements", tags=["announcements"])


@router.get("/active", response_model=List[schemas.AnnouncementOut])
def get_active_announcements(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Retrieve all currently active global outage & maintenance banners."""
    return (
        db.query(models.SystemAnnouncement)
        .filter(models.SystemAnnouncement.is_active == True)
        .order_by(models.SystemAnnouncement.created_at.desc())
        .all()
    )


@router.get("", response_model=List[schemas.AnnouncementOut])
def list_all_announcements(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role("technician", "admin")),
):
    """Retrieve all system announcements including historical/resolved ones."""
    return (
        db.query(models.SystemAnnouncement)
        .order_by(models.SystemAnnouncement.created_at.desc())
        .all()
    )


@router.post("", response_model=schemas.AnnouncementOut, status_code=201)
def create_announcement(
    payload: schemas.AnnouncementCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role("technician", "admin")),
):
    """Broadcast a new global IT outage / maintenance banner."""
    announcement = models.SystemAnnouncement(
        title=payload.title,
        message=payload.message,
        severity=payload.severity,
        is_active=payload.is_active,
        affected_services=payload.affected_services or [],
        workaround=payload.workaround,
        estimated_resolution=payload.estimated_resolution,
        created_by_id=current_user.id,
    )
    db.add(announcement)
    db.commit()
    db.refresh(announcement)

    write_audit(
        db,
        current_user,
        "broadcast_outage_banner",
        "announcement",
        announcement.id,
        f"Broadcasted [{announcement.severity.upper()}] MIM Outage Banner: '{announcement.title}'",
    )

    return announcement


@router.patch("/{announcement_id}", response_model=schemas.AnnouncementOut)
def update_announcement(
    announcement_id: int,
    payload: schemas.AnnouncementUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role("technician", "admin")),
):
    """Update announcement status, resolution ETA, or toggle active/resolved."""
    announcement = db.query(models.SystemAnnouncement).filter(models.SystemAnnouncement.id == announcement_id).first()
    if not announcement:
        raise HTTPException(status_code=404, detail="Announcement not found")

    if payload.title is not None:
        announcement.title = payload.title
    if payload.message is not None:
        announcement.message = payload.message
    if payload.severity is not None:
        announcement.severity = payload.severity
    if payload.affected_services is not None:
        announcement.affected_services = payload.affected_services
    if payload.workaround is not None:
        announcement.workaround = payload.workaround
    if payload.estimated_resolution is not None:
        announcement.estimated_resolution = payload.estimated_resolution
    if payload.is_active is not None:
        announcement.is_active = payload.is_active

    db.commit()
    db.refresh(announcement)

    write_audit(
        db,
        current_user,
        "update_outage_banner",
        "announcement",
        announcement.id,
        f"Updated MIM Outage Banner #{announcement.id} (is_active={announcement.is_active})",
    )

    return announcement


@router.delete("/{announcement_id}", status_code=204)
def delete_announcement(
    announcement_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role("admin")),
):
    """Delete an announcement (Admin only)."""
    announcement = db.query(models.SystemAnnouncement).filter(models.SystemAnnouncement.id == announcement_id).first()
    if not announcement:
        raise HTTPException(status_code=404, detail="Announcement not found")

    db.delete(announcement)
    db.commit()

    write_audit(
        db,
        current_user,
        "delete_outage_banner",
        "announcement",
        announcement_id,
        f"Deleted MIM Outage Banner #{announcement_id}",
    )
    return None
