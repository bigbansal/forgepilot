"""Authentication endpoints: register, login, refresh, me, teams."""
from datetime import datetime, UTC
from uuid import uuid4
import re

from fastapi import APIRouter, Depends, HTTPException, status
from jose import JWTError
from pydantic import BaseModel, Field
from sqlalchemy import select

from manch_backend.core.deps import get_current_user, AuthContext
from manch_backend.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from manch_backend.db.models import UserRecord, TeamRecord, TeamMemberRecord
from manch_backend.db.session import SessionLocal

router = APIRouter()


# ── Request / Response schemas ────────────────────────────────────────────────


class RegisterRequest(BaseModel):
    email: str = Field(..., pattern=r'^[\w.+-]+@[\w-]+\.[\w.-]+$', max_length=254)
    password: str = Field(..., min_length=8, max_length=128)
    full_name: str | None = None


class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    team_id: str | None = None


class RefreshRequest(BaseModel):
    refresh_token: str


class SwitchTeamRequest(BaseModel):
    team_id: str


class TeamSummary(BaseModel):
    id: str
    name: str
    slug: str
    role: str


class UserResponse(BaseModel):
    id: str
    email: str
    full_name: str | None
    is_active: bool
    created_at: datetime
    teams: list[TeamSummary] = []


class CreateTeamRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)


class InviteMemberRequest(BaseModel):
    email: str
    role: str = "member"


class TeamMemberResponse(BaseModel):
    id: str
    user_id: str
    email: str
    full_name: str | None
    role: str
    joined_at: datetime


def _slugify(name: str) -> str:
    slug = re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')
    return slug or "team"


def _get_user_teams(user_id: str) -> list[TeamSummary]:
    with SessionLocal() as db:
        rows = (
            db.query(TeamRecord, TeamMemberRecord.role)
            .join(TeamMemberRecord, TeamMemberRecord.team_id == TeamRecord.id)
            .filter(TeamMemberRecord.user_id == user_id, TeamRecord.is_active == True)
            .all()
        )
        return [
            TeamSummary(id=team.id, name=team.name, slug=team.slug, role=role)
            for team, role in rows
        ]


def _user_to_response(user: UserRecord) -> UserResponse:
    return UserResponse(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        is_active=user.is_active,
        created_at=user.created_at,
        teams=_get_user_teams(user.id),
    )


def _create_personal_team(user_id: str, db) -> TeamRecord:
    """Create a default 'Personal' team for a new user."""
    team = TeamRecord(
        id=str(uuid4()),
        name="Personal",
        slug=f"personal-{user_id[:8]}",
        owner_id=user_id,
        is_active=True,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    db.add(team)
    db.flush()  # ensure team row exists before FK reference
    member = TeamMemberRecord(
        id=str(uuid4()),
        team_id=team.id,
        user_id=user_id,
        role="owner",
        joined_at=datetime.now(UTC),
    )
    db.add(member)
    return team


# ── Endpoints ─────────────────────────────────────────────────────────────────


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(request: RegisterRequest):
    """Create a new user account, auto-create a personal team, return JWT tokens."""
    password = request.password.strip()
    if len(password) < 8:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Password must be at least 8 characters",
        )

    with SessionLocal() as db:
        existing = db.execute(
            select(UserRecord).where(UserRecord.email == request.email.lower())
        ).scalar_one_or_none()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Email already registered",
            )

        user = UserRecord(
            id=str(uuid4()),
            email=request.email.lower(),
            hashed_password=hash_password(password),
            full_name=request.full_name,
            is_active=True,
            created_at=datetime.now(UTC),
        )
        db.add(user)
        db.flush()

        # Auto-create personal team
        team = _create_personal_team(user.id, db)
        db.commit()

        user_id = user.id
        team_id = team.id

    return TokenResponse(
        access_token=create_access_token(user_id, team_id=team_id),
        refresh_token=create_refresh_token(user_id, team_id=team_id),
        team_id=team_id,
    )


@router.post("/login", response_model=TokenResponse)
def login(request: LoginRequest):
    """Authenticate with email + password and return JWT tokens scoped to last-active team."""
    with SessionLocal() as db:
        user = db.execute(
            select(UserRecord).where(UserRecord.email == request.email.lower())
        ).scalar_one_or_none()
        if not user or not verify_password(request.password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
        if not user.is_active:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User account is disabled")
        user_id = user.id

    # Determine default team (first owned, or first membership)
    teams = _get_user_teams(user_id)
    default_team_id = teams[0].id if teams else None

    return TokenResponse(
        access_token=create_access_token(user_id, team_id=default_team_id),
        refresh_token=create_refresh_token(user_id, team_id=default_team_id),
        team_id=default_team_id,
    )


@router.post("/refresh", response_model=TokenResponse)
def refresh_token(request: RefreshRequest):
    """Exchange a refresh token for a new access + refresh token pair."""
    credentials_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired refresh token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_token(request.refresh_token)
        if payload.get("type") != "refresh":
            raise credentials_exc
        user_id: str | None = payload.get("sub")
        if not user_id:
            raise credentials_exc
    except JWTError:
        raise credentials_exc

    with SessionLocal() as db:
        user = db.get(UserRecord, user_id)

    if not user or not user.is_active:
        raise credentials_exc

    team_id = payload.get("team_id")
    return TokenResponse(
        access_token=create_access_token(user.id, team_id=team_id),
        refresh_token=create_refresh_token(user.id, team_id=team_id),
        team_id=team_id,
    )


@router.post("/switch-team", response_model=TokenResponse)
def switch_team(
    request: SwitchTeamRequest,
    auth: AuthContext = Depends(get_current_user),
):
    """Issue new tokens scoped to a different team."""
    # Validate membership
    with SessionLocal() as db:
        membership = (
            db.query(TeamMemberRecord)
            .filter(
                TeamMemberRecord.team_id == request.team_id,
                TeamMemberRecord.user_id == auth.user.id,
            )
            .first()
        )
    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not a member of the requested team",
        )

    return TokenResponse(
        access_token=create_access_token(auth.user.id, team_id=request.team_id),
        refresh_token=create_refresh_token(auth.user.id, team_id=request.team_id),
        team_id=request.team_id,
    )


@router.get("/me", response_model=UserResponse)
def me(auth: AuthContext = Depends(get_current_user)):
    """Return the currently authenticated user's profile with teams."""
    return _user_to_response(auth.user)


# ── Team management endpoints ────────────────────────────────────────────────


@router.post("/teams", status_code=status.HTTP_201_CREATED)
def create_team(
    request: CreateTeamRequest,
    auth: AuthContext = Depends(get_current_user),
):
    """Create a new team. The caller becomes the owner."""
    slug = _slugify(request.name)
    with SessionLocal() as db:
        # Ensure slug uniqueness
        existing = db.execute(
            select(TeamRecord).where(TeamRecord.slug == slug)
        ).scalar_one_or_none()
        if existing:
            slug = f"{slug}-{str(uuid4())[:8]}"

        team = TeamRecord(
            id=str(uuid4()),
            name=request.name,
            slug=slug,
            owner_id=auth.user.id,
            is_active=True,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        db.add(team)
        db.flush()  # ensure team row exists before FK reference
        member = TeamMemberRecord(
            id=str(uuid4()),
            team_id=team.id,
            user_id=auth.user.id,
            role="owner",
            joined_at=datetime.now(UTC),
        )
        db.add(member)
        db.commit()

        result = {"id": team.id, "name": team.name, "slug": team.slug}

    return result


@router.get("/teams")
def list_teams(auth: AuthContext = Depends(get_current_user)):
    """List all teams the current user belongs to."""
    return _get_user_teams(auth.user.id)


@router.get("/teams/{team_id}/members")
def list_team_members(
    team_id: str,
    auth: AuthContext = Depends(get_current_user),
):
    """List members of a team (must be a member)."""
    with SessionLocal() as db:
        # Check membership
        membership = (
            db.query(TeamMemberRecord)
            .filter(TeamMemberRecord.team_id == team_id, TeamMemberRecord.user_id == auth.user.id)
            .first()
        )
        if not membership:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not a member of this team")

        rows = (
            db.query(TeamMemberRecord, UserRecord)
            .join(UserRecord, UserRecord.id == TeamMemberRecord.user_id)
            .filter(TeamMemberRecord.team_id == team_id)
            .all()
        )
        return [
            TeamMemberResponse(
                id=tm.id,
                user_id=tm.user_id,
                email=u.email,
                full_name=u.full_name,
                role=tm.role,
                joined_at=tm.joined_at,
            )
            for tm, u in rows
        ]


@router.post("/teams/{team_id}/members")
def invite_member(
    team_id: str,
    request: InviteMemberRequest,
    auth: AuthContext = Depends(get_current_user),
):
    """Invite a user to a team by email. Caller must be owner or admin."""
    with SessionLocal() as db:
        # Check caller's role
        caller_membership = (
            db.query(TeamMemberRecord)
            .filter(TeamMemberRecord.team_id == team_id, TeamMemberRecord.user_id == auth.user.id)
            .first()
        )
        if not caller_membership or caller_membership.role not in ("owner", "admin"):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only owner/admin can invite members")

        # Find user by email
        invitee = db.execute(
            select(UserRecord).where(UserRecord.email == request.email.lower())
        ).scalar_one_or_none()
        if not invitee:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

        # Check not already a member
        existing = (
            db.query(TeamMemberRecord)
            .filter(TeamMemberRecord.team_id == team_id, TeamMemberRecord.user_id == invitee.id)
            .first()
        )
        if existing:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User is already a member")

        role = request.role if request.role in ("admin", "member", "viewer") else "member"
        invitee_id = invitee.id
        member = TeamMemberRecord(
            id=str(uuid4()),
            team_id=team_id,
            user_id=invitee_id,
            role=role,
            joined_at=datetime.now(UTC),
        )
        db.add(member)
        db.commit()

        return {"status": "invited", "user_id": invitee_id, "role": role}


@router.delete("/teams/{team_id}/members/{user_id}")
def remove_member(
    team_id: str,
    user_id: str,
    auth: AuthContext = Depends(get_current_user),
):
    """Remove a member from a team. Caller must be owner or admin."""
    with SessionLocal() as db:
        caller_membership = (
            db.query(TeamMemberRecord)
            .filter(TeamMemberRecord.team_id == team_id, TeamMemberRecord.user_id == auth.user.id)
            .first()
        )
        if not caller_membership or caller_membership.role not in ("owner", "admin"):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only owner/admin can remove members")

        target = (
            db.query(TeamMemberRecord)
            .filter(TeamMemberRecord.team_id == team_id, TeamMemberRecord.user_id == user_id)
            .first()
        )
        if not target:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found")
        if target.role == "owner":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot remove team owner")

        db.delete(target)
        db.commit()

    return {"status": "removed"}
