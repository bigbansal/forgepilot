"""FastAPI dependencies for authentication."""
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError

from forgepilot_backend.core.security import decode_token
from forgepilot_backend.db.models import UserRecord
from forgepilot_backend.db.session import SessionLocal

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


def get_current_user(token: str = Depends(oauth2_scheme)) -> UserRecord:
    """Validate JWT and return the authenticated UserRecord."""
    credentials_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_token(token)
        if payload.get("type") != "access":
            raise credentials_exc
        user_id: str | None = payload.get("sub")
        if not user_id:
            raise credentials_exc
    except JWTError:
        raise credentials_exc

    with SessionLocal() as db:
        user = db.get(UserRecord, user_id)

    if user is None or not user.is_active:
        raise credentials_exc
    return user


def get_user_from_token(token: str) -> UserRecord:
    """Validate a raw JWT string and return the UserRecord.

    Used for endpoints (e.g., SSE stream) that receive the token via query
    parameter rather than an Authorization header.
    """
    credentials_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_token(token)
        if payload.get("type") != "access":
            raise credentials_exc
        user_id: str | None = payload.get("sub")
        if not user_id:
            raise credentials_exc
    except JWTError:
        raise credentials_exc

    with SessionLocal() as db:
        user = db.get(UserRecord, user_id)

    if user is None or not user.is_active:
        raise credentials_exc
    return user
