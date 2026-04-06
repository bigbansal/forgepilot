"""Global approvals endpoint — lists all pending approvals across all tasks."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select

from manch_backend.core.deps import get_current_user, AuthContext
from manch_backend.db.models import ApprovalRequestRecord, TaskRecord
from manch_backend.db.session import SessionLocal

router = APIRouter()


@router.get("")
def list_pending_approvals(
    auth: AuthContext = Depends(get_current_user),
):
    """List all pending approval requests for the team's tasks (or user's if no team)."""
    risk_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}

    with SessionLocal() as db:
        stmt = (
            select(ApprovalRequestRecord)
            .join(TaskRecord, TaskRecord.id == ApprovalRequestRecord.task_id)
            .where(ApprovalRequestRecord.decision.is_(None))
            .order_by(ApprovalRequestRecord.requested_at.desc())
        )
        if auth.team_id:
            stmt = stmt.where(TaskRecord.team_id == auth.team_id)
        else:
            stmt = stmt.where(TaskRecord.user_id == auth.user.id)
        rows = db.execute(stmt).scalars().all()

    # Sort by risk severity then recency
    rows_sorted = sorted(
        rows,
        key=lambda r: (risk_order.get(r.risk_level or "", 3), r.requested_at),
    )

    return [
        {
            "id": r.id,
            "task_id": r.task_id,
            "step_id": r.step_id,
            "operation_type": r.operation_type,
            "risk_level": r.risk_level,
            "reason": r.reason,
            "paused_step_index": r.paused_step_index,
            "requested_at": r.requested_at,
        }
        for r in rows_sorted
    ]


@router.get("/count")
def pending_approval_count(
    auth: AuthContext = Depends(get_current_user),
):
    """Return the count of pending approvals (for sidebar badge)."""
    from sqlalchemy import func

    with SessionLocal() as db:
        stmt = (
            select(func.count())
            .select_from(ApprovalRequestRecord)
            .join(TaskRecord, TaskRecord.id == ApprovalRequestRecord.task_id)
            .where(ApprovalRequestRecord.decision.is_(None))
        )
        if auth.team_id:
            stmt = stmt.where(TaskRecord.team_id == auth.team_id)
        else:
            stmt = stmt.where(TaskRecord.user_id == auth.user.id)
        count = db.scalar(stmt)
    return {"count": count or 0}
