"""
User management endpoints — admin-only.
GET    /users        — list all users
POST   /users        — create a user with any role
GET    /users/{id}   — get one user
PATCH  /users/{id}   — update role, team, or support_level
DELETE /users/{id}   — delete a user with no ticket history
"""

from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from database import get_db
from auth import require_role, hash_password
from audit import write_audit
import models, schemas

router = APIRouter(prefix="/users", tags=["users"])


def _get_user_or_404(user_id: int, db: Session) -> models.User:
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.get("", response_model=List[schemas.UserOut])
def list_users(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role("admin")),
):
    """List all users — admin only."""
    return db.query(models.User).order_by(models.User.created_at.desc()).all()


@router.post("", response_model=schemas.UserOut, status_code=201)
def create_user(
    payload: schemas.UserRegister,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role("admin")),
):
    """Create a new user — admin only."""
    email = payload.email.lower()
    if db.query(models.User).filter(func.lower(models.User.email) == email).first():
        raise HTTPException(status_code=400, detail="Email already registered")

    support_lvl = payload.support_level or ("L3" if payload.role == "admin" else "L1")

    user = models.User(
        name=payload.name.strip(),
        email=email,
        password_hash=hash_password(payload.password),
        role=payload.role,
        team=payload.team,
        support_level=support_lvl,
        primary_device=payload.primary_device,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    write_audit(db, current_user, "user_created", "user", user.id,
                f"Admin created user #{user.id} ({email}) with role '{payload.role}' and tier '{support_lvl}'")
    return user


@router.get("/{user_id}", response_model=schemas.UserOut)
def get_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role("admin")),
):
    return _get_user_or_404(user_id, db)


@router.patch("/{user_id}", response_model=schemas.UserOut)
def update_user(
    user_id: int,
    payload: schemas.UserUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role("admin")),
):
    """Update a user's role, team, or support level — admin only."""
    user = _get_user_or_404(user_id, db)

    update_data = payload.model_dump(exclude_none=True)
    if user.id == current_user.id and update_data.get("role", "admin") != "admin":
        raise HTTPException(status_code=400, detail="You cannot remove your own admin role")

    for field, value in update_data.items():
        setattr(user, field, value)
    db.commit()
    db.refresh(user)

    write_audit(db, current_user, "user_updated", "user", user_id, f"Admin updated user #{user_id}: {update_data}")
    return user


@router.delete("/{user_id}", status_code=204)
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role("admin")),
):
    """Delete a user account — admin only. Users with ticket history are kept
    so the audit trail and metrics stay intact."""
    user = _get_user_or_404(user_id, db)
    if user.id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot delete your own account")
    has_tickets = db.query(models.Ticket.id).filter(
        or_(models.Ticket.user_id == user_id, models.Ticket.assigned_to == user_id)
    ).first()
    if has_tickets:
        raise HTTPException(status_code=409, detail="User has ticket history and cannot be deleted")

    email = user.email
    db.query(models.TicketMessage).filter(models.TicketMessage.sender_id == user_id).update({"sender_id": None})
    db.delete(user)
    db.commit()

    write_audit(db, current_user, "user_deleted", "user", user_id, f"Admin deleted user #{user_id} ({email})")
    return None
