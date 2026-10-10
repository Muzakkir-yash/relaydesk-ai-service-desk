import hashlib
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from config import settings
from database import get_db
from auth import (hash_password, verify_password, create_session_token, get_current_user, set_password,
                  set_auth_cookie, clear_auth_cookie)
from audit import write_audit
from ratelimit import SlidingWindowLimiter, client_ip, enforce
import models, schemas

router = APIRouter(prefix="/auth", tags=["auth"])

# Failed logins are counted per IP+account (stops guessing one password) and
# per IP (stops spraying many accounts). Successful logins clear the account bucket.
login_failures_by_account = SlidingWindowLimiter(settings.LOGIN_MAX_FAILURES_PER_ACCOUNT, settings.LOGIN_WINDOW_SECONDS)
login_failures_by_ip = SlidingWindowLimiter(settings.LOGIN_MAX_FAILURES_PER_IP, settings.LOGIN_WINDOW_SECONDS)
registrations_by_ip = SlidingWindowLimiter(settings.REGISTER_MAX_PER_IP, settings.REGISTER_WINDOW_SECONDS)

TOO_MANY_LOGINS = "Too many failed sign-in attempts. Please wait and try again."


@router.post("/register", response_model=schemas.UserOut, status_code=201)
def register(payload: schemas.UserRegister, request: Request, db: Session = Depends(get_db)):
    """Public self-service sign-up. Always creates an end user — technician
    and admin accounts can only be created by an admin via POST /users."""
    ip = client_ip(request)
    enforce(registrations_by_ip, ip, "Too many sign-ups from this network. Please try again later.")

    email = payload.email.lower()
    if db.query(models.User).filter(func.lower(models.User.email) == email).first():
        raise HTTPException(status_code=400, detail="Email already registered")

    user = models.User(
        name=payload.name.strip(),
        email=email,
        password_hash=hash_password(payload.password),
        role="enduser",
        team=payload.team,
        support_level="L1",
        primary_device=payload.primary_device,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    registrations_by_ip.hit(ip)
    write_audit(db, user, "user_registered", "user", user.id, f"New enduser registered: {email}")
    return user


@router.post("/login", response_model=schemas.Token)
def login(payload: schemas.UserLogin, request: Request, response: Response, db: Session = Depends(get_db)):
    email = payload.email.lower()
    ip = client_ip(request)
    account_key = f"{ip}|{email}"
    enforce(login_failures_by_ip, ip, TOO_MANY_LOGINS)
    enforce(login_failures_by_account, account_key, TOO_MANY_LOGINS)

    user = db.query(models.User).filter(func.lower(models.User.email) == email).first()
    if not user or not verify_password(payload.password, user.password_hash):
        login_failures_by_account.hit(account_key)
        login_failures_by_ip.hit(ip)
        write_audit(db, None, "login_failed", "user", user.id if user else None,
                    f"Failed sign-in for {email} from {ip}", actor_type="user")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )

    login_failures_by_account.reset(account_key)
    token = create_session_token(user)
    set_auth_cookie(response, token)
    write_audit(db, user, "user_login", "user", user.id, f"{user.role} logged in: {user.email}")
    # The token is also returned for API clients that use Bearer auth;
    # the browser UI relies on the httpOnly cookie and never stores it.
    return {"access_token": token, "token_type": "bearer"}


@router.post("/logout", status_code=204)
def logout(response: Response):
    clear_auth_cookie(response)
    return None


@router.get("/me", response_model=schemas.UserOut)
def me(current_user: models.User = Depends(get_current_user)):
    return current_user


# ── Password reset (no email needed: an admin hands the user a one-time link) ──
forgot_requests_by_ip = SlidingWindowLimiter(5, 60 * 60)
reset_attempts_by_ip = SlidingWindowLimiter(20, 60 * 60)

FORGOT_REPLY = ("If an account exists for that email, the IT team has been notified. "
                "An administrator will send you a password reset link.")


@router.post("/forgot-password", status_code=202)
def forgot_password(payload: schemas.ForgotPasswordRequest, request: Request, db: Session = Depends(get_db)):
    """Flags the account for an admin. Always answers the same way, so it
    can't be used to discover which emails have accounts."""
    ip = client_ip(request)
    enforce(forgot_requests_by_ip, ip, "Too many requests. Please try again later.")
    forgot_requests_by_ip.hit(ip)
    user = db.query(models.User).filter(func.lower(models.User.email) == payload.email.lower()).first()
    if user:
        user.password_reset_requested_at = datetime.utcnow()
        db.commit()
        write_audit(db, user, "password_reset_requested", "user", user.id,
                    f"Password reset requested for {user.email} from {ip}")
    return {"detail": FORGOT_REPLY}


@router.post("/reset-password", status_code=204)
def reset_password(payload: schemas.ResetPasswordRequest, request: Request, db: Session = Depends(get_db)):
    """Uses a one-time link from an admin. Signs out every existing session."""
    ip = client_ip(request)
    enforce(reset_attempts_by_ip, ip, "Too many attempts. Please try again later.")
    reset_attempts_by_ip.hit(ip)
    token_hash = hashlib.sha256(payload.token.encode()).hexdigest()
    reset = db.query(models.PasswordResetToken).filter(models.PasswordResetToken.token_hash == token_hash).first()
    if not reset or reset.used_at or reset.expires_at < datetime.utcnow():
        raise HTTPException(status_code=400, detail="This reset link is invalid or has expired. Ask IT for a new one.")
    user = db.query(models.User).filter(models.User.id == reset.user_id).first()
    if not user:
        raise HTTPException(status_code=400, detail="This reset link is invalid or has expired. Ask IT for a new one.")
    set_password(user, payload.new_password)
    user.password_reset_requested_at = None
    reset.used_at = datetime.utcnow()
    db.commit()
    write_audit(db, user, "password_reset_completed", "user", user.id, f"Password reset via link for {user.email}")
    return None


@router.post("/change-password", status_code=204)
def change_password(
    payload: schemas.ChangePasswordRequest,
    response: Response,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Change your own password. Other devices are signed out; this one stays signed in."""
    if not verify_password(payload.current_password, current_user.password_hash):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    set_password(current_user, payload.new_password)
    db.commit()
    set_auth_cookie(response, create_session_token(current_user))
    write_audit(db, current_user, "password_changed", "user", current_user.id, f"{current_user.email} changed their password")
    return None
