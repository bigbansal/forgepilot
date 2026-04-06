"""Phase 2 API routes — plan steps, approvals, artifacts, and agent pipeline."""
from __future__ import annotations

from typing import Literal
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select

from manch_backend.core.deps import get_current_user, AuthContext
from manch_backend.db.models import (
    ApprovalRequestRecord,
    ArtifactRecord,
    PlanStepRecord,
    TaskRecord,
    ToolExecutionRecord,
)
from manch_backend.db.session import SessionLocal
from manch_backend.models import TaskRunner
from manch_backend.services.orchestrator import orchestrator

router = APIRouter()


# ── Request / Response models ─────────────────────────


class StartAgentPipelineRequest(BaseModel):
    history: list[dict[str, str]] = []


class ApprovalDecisionRequest(BaseModel):
    decision: Literal["approve", "reject"]
    reason: str | None = None


# ── Helper ────────────────────────────────────────────


def _require_owned_task(task_id: str, auth: AuthContext) -> TaskRecord:
    with SessionLocal() as db:
        record = db.get(TaskRecord, task_id)
        if not record:
            raise HTTPException(status_code=404, detail="Task not found")
        if auth.team_id:
            if record.team_id != auth.team_id:
                raise HTTPException(status_code=404, detail="Task not found")
        elif record.user_id != auth.user.id:
            raise HTTPException(status_code=404, detail="Task not found")
        return record


# ── Agent pipeline ────────────────────────────────────


@router.post("/{task_id}/agent-start")
def start_agent_pipeline(
    task_id: str,
    request: StartAgentPipelineRequest | None = None,
    auth: AuthContext = Depends(get_current_user),
):
    """Start the Phase 2 agent-based execution pipeline for a task."""
    _require_owned_task(task_id, auth)
    history = request.history if request else []
    task, message = orchestrator.start_task_v2(
        task_id, user_id=auth.user.id, team_id=auth.team_id, history=history
    )
    if task is None:
        raise HTTPException(status_code=404, detail=message)
    return {"task": task, "message": message}


# ── Plan steps ────────────────────────────────────────


@router.get("/{task_id}/plan")
def get_plan_steps(
    task_id: str,
    auth: AuthContext = Depends(get_current_user),
):
    """Get all plan steps for a task."""
    _require_owned_task(task_id, auth)
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
    auth: AuthContext = Depends(get_current_user),
):
    """Get all tool executions for a task."""
    _require_owned_task(task_id, auth)
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
    auth: AuthContext = Depends(get_current_user),
):
    """Get all approval requests for a task."""
    _require_owned_task(task_id, auth)
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
            "paused_step_index": r.paused_step_index,
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
    auth: AuthContext = Depends(get_current_user),
):
    """Approve or reject an approval request."""
    _require_owned_task(task_id, auth)
    from datetime import datetime, UTC

    paused_step_index: int | None = None
    step_id: str | None = None
    operation_type: str | None = None
    with SessionLocal() as db:
        record = db.get(ApprovalRequestRecord, approval_id)
        if not record or record.task_id != task_id:
            raise HTTPException(status_code=404, detail="Approval not found")
        if record.decision is not None:
            raise HTTPException(status_code=400, detail="Already decided")

        record.decision = request.decision
        record.decided_by = auth.user.id
        record.resolved_at = datetime.now(UTC)
        paused_step_index = record.paused_step_index
        step_id = record.step_id
        operation_type = record.operation_type
        db.commit()
        db.refresh(record)

    if request.decision == "approve" and paused_step_index is not None:
        if step_id is None and (operation_type or "").startswith("task_start"):
            runner_value = TaskRunner.OPENSANDBOX.value
            if operation_type and ":" in operation_type:
                _, candidate = operation_type.split(":", 1)
                if candidate in {r.value for r in TaskRunner}:
                    runner_value = candidate
            orchestrator.resume_direct_task(
                task_id=task_id,
                runner=TaskRunner(runner_value),
                user_id=auth.user.id,
                team_id=auth.team_id,
            )
        else:
            # Resume the agent pipeline from the paused step
            orchestrator.resume_task_v2(
                task_id=task_id,
                user_id=auth.user.id,
                team_id=auth.team_id,
                start_index=paused_step_index,
            )
    elif request.decision == "reject":
        # Transition task to CANCELLED and post rejection message
        orchestrator.cancel_task(
            task_id=task_id,
            user_id=auth.user.id,
            team_id=auth.team_id,
            reason=request.reason or "Approval rejected by user",
        )

    return {
        "id": record.id,
        "decision": record.decision,
        "resolved_at": record.resolved_at,
        "resumed": request.decision == "approve" and paused_step_index is not None,
    }


# ── Artifacts ─────────────────────────────────────────


@router.get("/{task_id}/artifacts")
def get_artifacts(
    task_id: str,
    auth: AuthContext = Depends(get_current_user),
):
    """Get all artifacts produced for a task."""
    _require_owned_task(task_id, auth)
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


# ── Diff endpoint ─────────────────────────────────────


@router.get("/{task_id}/diff")
def get_task_diff(
    task_id: str,
    auth: AuthContext = Depends(get_current_user),
):
    """Return diff artifacts for a task (for Monaco diff viewer)."""
    _require_owned_task(task_id, auth)
    with SessionLocal() as db:
        rows = (
            db.execute(
                select(ArtifactRecord)
                .where(
                    ArtifactRecord.task_id == task_id,
                    ArtifactRecord.artifact_type == "diff",
                )
                .order_by(ArtifactRecord.created_at)
            )
            .scalars()
            .all()
        )
    return [
        {
            "id": r.id,
            "step_id": r.step_id,
            "content": r.content,
            "metadata_json": r.metadata_json,
            "created_at": r.created_at,
        }
        for r in rows
    ]
