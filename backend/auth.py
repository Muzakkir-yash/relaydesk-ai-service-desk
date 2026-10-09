"""
JWT authentication utilities.
"""

from datetime import datetime, timedelta
from typing import Optional

import bcrypt
from jose import JWTError, jwt
from fastapi import Depends, HTTPException, Request, Response, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from config import settings
from database import get_db
import models

# Browsers authenticate with the httpOnly session cookie; API clients may
# still send "Authorization: Bearer <token>".
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=False)

SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}
CSRF_HEADER = "X-Requested-With"


def set_auth_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=settings.AUTH_COOKIE_NAME,
        value=token,
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        httponly=True,  # not readable from JavaScript, so XSS cannot steal it
        secure=settings.is_production,
        samesite="lax",
        path="/",
    )


def clear_auth_cookie(response: Response) -> None:
    response.delete_cookie(
        key=settings.AUTH_COOKIE_NAME, path="/", httponly=True, secure=settings.is_production, samesite="lax"
    )

def hash_password(password: str) -> str:
    pwd_bytes = password.encode('utf-8')[:72]
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(pwd_bytes, salt).decode('utf-8')


def verify_password(plain: str, hashed: str) -> bool:
    pwd_bytes = plain.encode('utf-8')[:72]
    hashed_bytes = hashed.encode('utf-8')
    try:
        return bcrypt.checkpw(pwd_bytes, hashed_bytes)
    except Exception:
        return False


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (
        expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode["exp"] = expire
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def get_current_user(
    request: Request,
    bearer_token: Optional[str] = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> models.User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    token = bearer_token
    if not token:
        token = request.cookies.get(settings.AUTH_COOKIE_NAME)
        if not token:
            raise credentials_exception
        # Cookies are sent automatically, so a state-changing request must also
        # carry a header that a cross-site form or image tag cannot set (CSRF).
        if request.method not in SAFE_METHODS and request.headers.get(CSRF_HEADER) != "XMLHttpRequest":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Missing CSRF header")
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id = int(payload.get("sub"))
    except (JWTError, TypeError, ValueError):
        raise credentials_exception

    user = db.query(models.User).filter(models.User.id == user_id).first()
    if user is None:
        raise credentials_exception
    return user


def require_role(*roles: str):
    """Dependency factory — restricts endpoint to certain roles."""
    def _check(current_user: models.User = Depends(get_current_user)):
        if current_user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access requires one of: {roles}",
            )
        return current_user
    return _check
