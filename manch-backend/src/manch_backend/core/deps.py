"""FastAPI dependencies for authentication."""
from __future__ import annotations

from dataclasses import dataclass
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError

from manch_backend.core.security import decode_token
from manch_backend.db.models import UserRecord, TeamMemberRecord
from manch_backend.db.session import SessionLocal

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


@dataclass
class AuthContext:
    """Resolved authentication context: user + active team + role."""
    user: UserRecord
    team_id: str | None = None
    team_role: str | None = None  # owner, admin, member, viewer


def get_current_user(
    request: Request,
    token: str = Depends(oauth2_scheme),
) -> AuthContext:
    """Validate JWT and return AuthContext with team resolution.

    Team resolution priority:
    1. ``X-Team-Id`` request header (team switching without re-login)
    2. ``team_id`` claim baked into the JWT
    3. None (personal / no-team context)
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

    # ── Resolve team ──
    team_id: str | None = (
        request.headers.get("X-Team-Id")
        or payload.get("team_id")
    )
    team_role: str | None = None

    if team_id:
        with SessionLocal() as db:
            membership = (
                db.query(TeamMemberRecord)
                .filter(
                    TeamMemberRecord.team_id == team_id,
                    TeamMemberRecord.user_id == user_id,
                )
                .first()
            )
        if not membership:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not a member of the requested team",
            )
        team_role = membership.role

    return AuthContext(user=user, team_id=team_id, team_role=team_role)


def get_user_from_token(token: str) -> AuthContext:
    """Validate a raw JWT string and return AuthContext.

    Used for endpoints (e.g. SSE / WS) that receive the token via query
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

    team_id: str | None = payload.get("team_id")
    team_role: str | None = None
    if team_id:
        with SessionLocal() as db:
            membership = (
                db.query(TeamMemberRecord)
                .filter(
                    TeamMemberRecord.team_id == team_id,
                    TeamMemberRecord.user_id == user_id,
                )
                .first()
            )
        if membership:
            team_role = membership.role

    return AuthContext(user=user, team_id=team_id, team_role=team_role)


def require_team_role(*allowed_roles: str):
    """Dependency factory: ensure the caller has one of the allowed team roles."""
    def _check(auth: AuthContext = Depends(get_current_user)) -> AuthContext:
        if not auth.team_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Team context required",
            )
        if auth.team_role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires role: {', '.join(allowed_roles)}",
            )
        return auth
    return _check
