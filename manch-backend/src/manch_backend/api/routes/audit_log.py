"""Audit log API endpoints — immutable activity trail."""
from __future__ import annotations

import json
import logging
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel

from manch_backend.core.deps import get_current_user, AuthContext
from manch_backend.db.models import AuditLogRecord
from manch_backend.db.session import SessionLocal
from sqlalchemy import select, func

logger = logging.getLogger(__name__)
router = APIRouter()


# ── Schemas ──────────────────────────────────────────


class AuditLogEntry(BaseModel):
    id: str
    user_id: str | None = None
    action: str
    resource_type: str | None = None
    resource_id: str | None = None
    detail: str | None = None
    ip_address: str | None = None
    created_at: str


class AuditLogListResponse(BaseModel):
    items: list[AuditLogEntry]
    total: int
    page: int
    page_size: int


# ── Helper ───────────────────────────────────────────


def emit_audit_event(
    action: str,
    *,
    user_id: str | None = None,
    team_id: str | None = None,
    resource_type: str | None = None,
    resource_id: str | None = None,
    detail: str | None = None,
    ip_address: str | None = None,
) -> None:
    """Persist an audit event. Fire-and-forget — should never disrupt the caller."""
    try:
        with SessionLocal() as db:
            record = AuditLogRecord(
                id=str(uuid4()),
                user_id=user_id,
                team_id=team_id,
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                detail=detail,
                ip_address=ip_address,
            )
            db.add(record)
            db.commit()
    except Exception:
        logger.exception("Failed to write audit event: %s", action)


# ── Endpoints ────────────────────────────────────────


@router.get("", response_model=AuditLogListResponse)
def list_audit_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    action: str | None = Query(None),
    resource_type: str | None = Query(None),
    user_id: str | None = Query(None),
    auth: AuthContext = Depends(get_current_user),
):
    """List audit log entries with optional filters, newest-first, scoped by team."""
    with SessionLocal() as db:
        stmt = select(AuditLogRecord).order_by(AuditLogRecord.created_at.desc())
        count_stmt = select(func.count(AuditLogRecord.id))

        if auth.team_id:
            stmt = stmt.where(AuditLogRecord.team_id == auth.team_id)
            count_stmt = count_stmt.where(AuditLogRecord.team_id == auth.team_id)
        if action:
            stmt = stmt.where(AuditLogRecord.action == action)
            count_stmt = count_stmt.where(AuditLogRecord.action == action)
        if resource_type:
            stmt = stmt.where(AuditLogRecord.resource_type == resource_type)
            count_stmt = count_stmt.where(AuditLogRecord.resource_type == resource_type)
        if user_id:
            stmt = stmt.where(AuditLogRecord.user_id == user_id)
            count_stmt = count_stmt.where(AuditLogRecord.user_id == user_id)

        total = db.execute(count_stmt).scalar() or 0
        records = db.execute(stmt.offset((page - 1) * page_size).limit(page_size)).scalars().all()

        items = [
            AuditLogEntry(
                id=r.id,
                user_id=r.user_id,
                action=r.action,
                resource_type=r.resource_type,
                resource_id=r.resource_id,
                detail=r.detail,
                ip_address=r.ip_address,
                created_at=r.created_at.isoformat(),
            )
            for r in records
        ]

    return AuditLogListResponse(items=items, total=total, page=page, page_size=page_size)


@router.get("/actions", response_model=list[str])
def list_audit_actions(
    auth: AuthContext = Depends(get_current_user),
):
    """Return distinct audit actions for filter dropdowns."""
    with SessionLocal() as db:
        rows = db.execute(
            select(AuditLogRecord.action).distinct().order_by(AuditLogRecord.action)
        ).scalars().all()
    return list(rows)
