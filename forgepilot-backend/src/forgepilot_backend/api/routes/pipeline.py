"""Phase 2 API routes — plan steps, approvals, artifacts, and agent pipeline."""
from __future__ import annotations

from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select

from forgepilot_backend.core.deps import get_current_user
from forgepilot_backend.db.models import (
    ApprovalRequestRecord,
    ArtifactRecord,
    PlanStepRecord,
    TaskRecord,
    ToolExecutionRecord,
    UserRecord,
)
from forgepilot_backend.db.session import SessionLocal
from forgepilot_backend.services.orchestrator import orchestrator

router = APIRouter()


# ── Request / Response models ─────────────────────────


class StartAgentPipelineRequest(BaseModel):
    history: list[dict[str, str]] = []


class ApprovalDecisionRequest(BaseModel):
    decision: str  # "approve" | "reject"


# ── Helper ────────────────────────────────────────────


def _require_owned_task(task_id: str, user_id: str) -> TaskRecord:
    with SessionLocal() as db:
        record = db.get(TaskRecord, task_id)
        if not record or record.user_id != user_id:
            raise HTTPException(status_code=404, detail="Task not found")
        return record


# ── Agent pipeline ────────────────────────────────────


@router.post("/{task_id}/agent-start")
def start_agent_pipeline(
    task_id: str,
    request: StartAgentPipelineRequest | None = None,
    current_user: UserRecord = Depends(get_current_user),
):
    """Start the Phase 2 agent-based execution pipeline for a task."""
    _require_owned_task(task_id, current_user.id)
    history = request.history if request else []
    task, message = orchestrator.start_task_v2(
        task_id, user_id=current_user.id, history=history
    )
    if task is None:
        raise HTTPException(status_code=404, detail=message)
    return {"task": task, "message": message}


# ── Plan steps ────────────────────────────────────────


@router.get("/{task_id}/plan")
def get_plan_steps(
    task_id: str,
    current_user: UserRecord = Depends(get_current_user),
):
    """Get all plan steps for a task."""
    _require_owned_task(task_id, current_user.id)
    with SessionLocal() as db:
        rows = (
            db.execute(
                select(PlanStepRecord)
                .where(PlanStepRecord.task_id == task_id)
                .order_by(PlanStepRecord.order_index)
            )
            .scalars()
            .all()
        )
    return [
        {
            "id": r.id,
            "task_id": r.task_id,
            "order_index": r.order_index,
            "agent_name": r.agent_name,
            "description": r.description,
            "status": r.status,
            "output_summary": r.output_summary,
            "started_at": r.started_at,
            "finished_at": r.finished_at,
        }
        for r in rows
    ]


# ── Tool executions ──────────────────────────────────


@router.get("/{task_id}/tools")
def get_tool_executions(
    task_id: str,
    current_user: UserRecord = Depends(get_current_user),
):
    """Get all tool executions for a task."""
    _require_owned_task(task_id, current_user.id)
    with SessionLocal() as db:
        rows = (
            db.execute(
                select(ToolExecutionRecord)
                .where(ToolExecutionRecord.task_id == task_id)
                .order_by(ToolExecutionRecord.created_at)
            )
            .scalars()
            .all()
        )
    return [
        {
            "id": r.id,
            "task_id": r.task_id,
            "step_id": r.step_id,
            "tool_name": r.tool_name,
            "input_summary": r.input_summary,
            "output_summary": r.output_summary,
            "result_status": r.result_status,
            "duration_ms": r.duration_ms,
            "created_at": r.created_at,
        }
        for r in rows
    ]


# ── Approvals ─────────────────────────────────────────


@router.get("/{task_id}/approvals")
def get_approvals(
    task_id: str,
    current_user: UserRecord = Depends(get_current_user),
):
    """Get all approval requests for a task."""
    _require_owned_task(task_id, current_user.id)
    with SessionLocal() as db:
        rows = (
            db.execute(
                select(ApprovalRequestRecord)
                .where(ApprovalRequestRecord.task_id == task_id)
                .order_by(ApprovalRequestRecord.requested_at)
            )
            .scalars()
            .all()
        )
    return [
        {
            "id": r.id,
            "task_id": r.task_id,
            "step_id": r.step_id,
            "operation_type": r.operation_type,
            "risk_level": r.risk_level,
            "reason": r.reason,
            "decision": r.decision,
            "decided_by": r.decided_by,
            "requested_at": r.requested_at,
            "resolved_at": r.resolved_at,
        }
        for r in rows
    ]


@router.post("/{task_id}/approvals/{approval_id}/decide")
def decide_approval(
    task_id: str,
    approval_id: str,
    request: ApprovalDecisionRequest,
    current_user: UserRecord = Depends(get_current_user),
):
    """Approve or reject an approval request."""
    _require_owned_task(task_id, current_user.id)
    from datetime import datetime, UTC

    with SessionLocal() as db:
        record = db.get(ApprovalRequestRecord, approval_id)
        if not record or record.task_id != task_id:
            raise HTTPException(status_code=404, detail="Approval not found")
        if record.decision is not None:
            raise HTTPException(status_code=400, detail="Already decided")

        record.decision = request.decision
        record.decided_by = current_user.id
        record.resolved_at = datetime.now(UTC)
        db.commit()
        db.refresh(record)

    # TODO: If approved, resume the pipeline from the paused step
    return {"id": record.id, "decision": record.decision, "resolved_at": record.resolved_at}


# ── Artifacts ─────────────────────────────────────────


@router.get("/{task_id}/artifacts")
def get_artifacts(
    task_id: str,
    current_user: UserRecord = Depends(get_current_user),
):
    """Get all artifacts produced for a task."""
    _require_owned_task(task_id, current_user.id)
    with SessionLocal() as db:
        rows = (
            db.execute(
                select(ArtifactRecord)
                .where(ArtifactRecord.task_id == task_id)
                .order_by(ArtifactRecord.created_at)
            )
            .scalars()
            .all()
        )
    return [
        {
            "id": r.id,
            "task_id": r.task_id,
            "step_id": r.step_id,
            "artifact_type": r.artifact_type,
            "content": r.content,
            "storage_path": r.storage_path,
            "metadata_json": r.metadata_json,
            "created_at": r.created_at,
        }
        for r in rows
    ]
