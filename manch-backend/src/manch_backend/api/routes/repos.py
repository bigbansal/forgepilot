"""Repository management API endpoints — multi-repo support."""
from __future__ import annotations

import json
import logging
from datetime import datetime, UTC
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from manch_backend.core.deps import get_current_user, AuthContext
from manch_backend.db.models import RepositoryRecord
from manch_backend.db.session import SessionLocal
from manch_backend.services.sandbox import OpenSandboxAdapter
from sqlalchemy import select

logger = logging.getLogger(__name__)
router = APIRouter()

sandbox = OpenSandboxAdapter()


# ── Schemas ──────────────────────────────────────────


class RepoCreate(BaseModel):
    name: str
    url: str
    default_branch: str = "main"
    description: str | None = None


class RepoUpdate(BaseModel):
    name: str | None = None
    url: str | None = None
    default_branch: str | None = None
    description: str | None = None
    is_active: bool | None = None


class RepoCloneRequest(BaseModel):
    """Optional overrides for clone operation."""
    branch: str | None = None
    depth: int | None = 1  # shallow clone by default
    target_dir: str | None = None  # directory name inside sandbox


class RepoCloneResponse(BaseModel):
    status: str
    repo_id: str
    repo_name: str
    clone_url: str
    branch: str
    sandbox_session_id: str
    stdout: str
    stderr: str
    exit_code: int


class QuickCloneRequest(BaseModel):
    """Clone any URL without pre-registering."""
    url: str
    branch: str = "main"
    depth: int | None = 1
    name: str | None = None  # auto-derived from URL if omitted


class RepoSummary(BaseModel):
    id: str
    name: str
    url: str
    default_branch: str
    description: str | None = None
    is_active: bool
    last_synced_at: str | None = None
    created_at: str


# ── Endpoints ────────────────────────────────────────


@router.get("", response_model=list[RepoSummary])
def list_repos(
    active_only: bool = Query(True),
    auth: AuthContext = Depends(get_current_user),
):
    """List registered repositories scoped by team."""
    with SessionLocal() as db:
        stmt = select(RepositoryRecord).order_by(RepositoryRecord.name)
        if active_only:
            stmt = stmt.where(RepositoryRecord.is_active == True)
        if auth.team_id:
            stmt = stmt.where(RepositoryRecord.team_id == auth.team_id)
        records = db.execute(stmt).scalars().all()

    return [
        RepoSummary(
            id=r.id,
            name=r.name,
            url=r.url,
            default_branch=r.default_branch,
            description=r.description,
            is_active=r.is_active,
            last_synced_at=r.last_synced_at.isoformat() if r.last_synced_at else None,
            created_at=r.created_at.isoformat(),
        )
        for r in records
    ]


@router.post("", response_model=RepoSummary, status_code=201)
def create_repo(
    body: RepoCreate,
    auth: AuthContext = Depends(get_current_user),
):
    """Register a new repository."""
    with SessionLocal() as db:
        record = RepositoryRecord(
            id=str(uuid4()),
            name=body.name,
            url=body.url,
            default_branch=body.default_branch,
            description=body.description,
            owner_id=auth.user.id,
            team_id=auth.team_id,
        )
        db.add(record)
        db.commit()
        db.refresh(record)

    # Emit audit event
    try:
        from manch_backend.api.routes.audit_log import emit_audit_event
        emit_audit_event(
            "repo.created",
            user_id=auth.user.id,
            team_id=auth.team_id,
            resource_type="repository",
            resource_id=record.id,
            detail=f"Registered repo: {body.name} ({body.url})",
        )
    except Exception:
        pass

    return RepoSummary(
        id=record.id,
        name=record.name,
        url=record.url,
        default_branch=record.default_branch,
        description=record.description,
        is_active=record.is_active,
        last_synced_at=None,
        created_at=record.created_at.isoformat(),
    )


@router.get("/{repo_id}", response_model=RepoSummary)
def get_repo(
    repo_id: str,
    auth: AuthContext = Depends(get_current_user),
):
    """Get a single repository by ID."""
    with SessionLocal() as db:
        record = db.get(RepositoryRecord, repo_id)
    if not record:
        raise HTTPException(status_code=404, detail="Repository not found")
    return RepoSummary(
        id=record.id,
        name=record.name,
        url=record.url,
        default_branch=record.default_branch,
        description=record.description,
        is_active=record.is_active,
        last_synced_at=record.last_synced_at.isoformat() if record.last_synced_at else None,
        created_at=record.created_at.isoformat(),
    )


@router.patch("/{repo_id}", response_model=RepoSummary)
def update_repo(
    repo_id: str,
    body: RepoUpdate,
    auth: AuthContext = Depends(get_current_user),
):
    """Update a repository's settings."""
    with SessionLocal() as db:
        record = db.get(RepositoryRecord, repo_id)
        if not record:
            raise HTTPException(status_code=404, detail="Repository not found")
        for field in ("name", "url", "default_branch", "description", "is_active"):
            val = getattr(body, field, None)
            if val is not None:
                setattr(record, field, val)
        record.updated_at = datetime.now(UTC)
        db.commit()
        db.refresh(record)

    return RepoSummary(
        id=record.id,
        name=record.name,
        url=record.url,
        default_branch=record.default_branch,
        description=record.description,
        is_active=record.is_active,
        last_synced_at=record.last_synced_at.isoformat() if record.last_synced_at else None,
        created_at=record.created_at.isoformat(),
    )


@router.delete("/{repo_id}", status_code=204)
def delete_repo(
    repo_id: str,
    auth: AuthContext = Depends(get_current_user),
):
    """Soft-delete a repository (set inactive)."""
    with SessionLocal() as db:
        record = db.get(RepositoryRecord, repo_id)
        if not record:
            raise HTTPException(status_code=404, detail="Repository not found")
        record.is_active = False
        record.updated_at = datetime.now(UTC)
        db.commit()


# ── Clone endpoints ──────────────────────────────────


def _derive_repo_name(url: str) -> str:
    """Extract a reasonable directory name from a git URL."""
    name = url.rstrip("/").rsplit("/", 1)[-1]
    if name.endswith(".git"):
        name = name[:-4]
    return name or "repo"


def _run_clone(url: str, branch: str, depth: int | None, target_dir: str) -> RepoCloneResponse | dict:
    """Spin up a sandbox, run git clone, return result."""
    session_id = sandbox.create_session()
    try:
        depth_flag = f" --depth {depth}" if depth else ""
        cmd = f"git clone {url} --branch {branch}{depth_flag} /workspace/{target_dir}"
        result = sandbox.run_command(session_id, cmd, keep_alive=True)

        # If clone succeeded, list the contents as a sanity check
        if result.exit_code == 0:
            ls = sandbox.run_command(session_id, f"ls -la /workspace/{target_dir}", keep_alive=True)
            stdout = f"{result.stdout}\n---\n{ls.stdout}".strip()
        else:
            stdout = result.stdout

        return {
            "stdout": stdout,
            "stderr": result.stderr,
            "exit_code": result.exit_code,
            "sandbox_session_id": session_id,
        }
    except Exception as e:
        logger.exception("Clone failed for %s", url)
        sandbox.destroy_session(session_id)
        raise HTTPException(status_code=500, detail=f"Clone failed: {e}")


@router.post("/{repo_id}/clone", response_model=RepoCloneResponse)
def clone_repo(
    repo_id: str,
    body: RepoCloneRequest | None = None,
    auth: AuthContext = Depends(get_current_user),
):
    """Clone a registered repository into a new sandbox.

    Returns the sandbox session ID so a task or interactive session
    can continue working inside the cloned repository.
    """
    with SessionLocal() as db:
        record = db.get(RepositoryRecord, repo_id)
    if not record:
        raise HTTPException(status_code=404, detail="Repository not found")

    branch = (body.branch if body and body.branch else record.default_branch) or "main"
    depth = body.depth if body else 1
    target_dir = (body.target_dir if body and body.target_dir else None) or _derive_repo_name(record.url)

    clone_result = _run_clone(record.url, branch, depth, target_dir)

    # Update last_synced_at
    with SessionLocal() as db:
        rec = db.get(RepositoryRecord, repo_id)
        if rec:
            rec.last_synced_at = datetime.now(UTC)
            db.commit()

    # Audit
    try:
        from manch_backend.api.routes.audit_log import emit_audit_event
        emit_audit_event(
            "repo.cloned",
            user_id=auth.user.id,
            team_id=auth.team_id,
            resource_type="repository",
            resource_id=repo_id,
            detail=f"Cloned {record.url} ({branch}) into sandbox {clone_result['sandbox_session_id']}",
        )
    except Exception:
        pass

    return RepoCloneResponse(
        status="cloned" if clone_result["exit_code"] == 0 else "failed",
        repo_id=repo_id,
        repo_name=record.name,
        clone_url=record.url,
        branch=branch,
        **clone_result,
    )


@router.post("/clone", response_model=RepoCloneResponse)
def quick_clone(
    body: QuickCloneRequest,
    auth: AuthContext = Depends(get_current_user),
):
    """Clone any git URL directly (no pre-registration needed).

    Optionally registers the repo if a name is provided.
    """
    name = body.name or _derive_repo_name(body.url)
    target_dir = name

    clone_result = _run_clone(body.url, body.branch, body.depth, target_dir)

    # Auto-register the repo if clone succeeded
    repo_id = ""
    if clone_result["exit_code"] == 0:
        try:
            with SessionLocal() as db:
                existing = db.execute(
                    select(RepositoryRecord).where(RepositoryRecord.url == body.url)
                ).scalar_one_or_none()
                if existing:
                    repo_id = existing.id
                    existing.last_synced_at = datetime.now(UTC)
                    db.commit()
                else:
                    repo_id = str(uuid4())
                    new_rec = RepositoryRecord(
                        id=repo_id,
                        name=name,
                        url=body.url,
                        default_branch=body.branch,
                        owner_id=auth.user.id,
                        team_id=auth.team_id,
                    )
                    db.add(new_rec)
                    db.commit()
        except Exception:
            logger.exception("Auto-register after clone failed")

    return RepoCloneResponse(
        status="cloned" if clone_result["exit_code"] == 0 else "failed",
        repo_id=repo_id,
        repo_name=name,
        clone_url=body.url,
        branch=body.branch,
        **clone_result,
    )
