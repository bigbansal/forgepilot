from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select

from manch_backend.core.deps import get_current_user, AuthContext
from manch_backend.db.models import ChatMessageRecord, TaskRecord
from manch_backend.db.session import SessionLocal
from manch_backend.models import TaskRunner
from manch_backend.services.orchestrator import orchestrator

router = APIRouter()


class CreateTaskRequest(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=10000)


class StartTaskRequest(BaseModel):
    runner: TaskRunner = TaskRunner.OPENSANDBOX


def _get_team_task(task_id: str, auth: AuthContext) -> TaskRecord:
    """Load a TaskRecord and 404 if not found or not accessible by the team / user."""
    with SessionLocal() as db:
        record = db.get(TaskRecord, task_id)
        if not record:
            raise HTTPException(status_code=404, detail="Task not found")
        # Team context: check team_id; fallback to user_id
        if auth.team_id:
            if record.team_id != auth.team_id:
                raise HTTPException(status_code=404, detail="Task not found")
        elif record.user_id != auth.user.id:
            raise HTTPException(status_code=404, detail="Task not found")
        return record


@router.post("")
def create_task(
    request: CreateTaskRequest,
    auth: AuthContext = Depends(get_current_user),
):
    return orchestrator.create_task(request.prompt, user_id=auth.user.id, team_id=auth.team_id)


@router.post("/{task_id}/start")
def start_task(
    task_id: str,
    request: StartTaskRequest | None = None,
    auth: AuthContext = Depends(get_current_user),
):
    _get_team_task(task_id, auth)
    runner = request.runner if request else TaskRunner.OPENSANDBOX
    task, session, message, output = orchestrator.start_task(task_id, runner=runner, user_id=auth.user.id, team_id=auth.team_id)
    if task is None:
        raise HTTPException(status_code=404, detail=message)
    return {"task": task, "session": session, "message": message, "output": output}


@router.get("/{task_id}")
def get_task(
    task_id: str,
    auth: AuthContext = Depends(get_current_user),
):
    _get_team_task(task_id, auth)
    task = orchestrator.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@router.get("")
def list_tasks(auth: AuthContext = Depends(get_current_user)):
    return orchestrator.list_tasks(user_id=auth.user.id, team_id=auth.team_id)


@router.get("/{task_id}/messages")
def get_task_messages(
    task_id: str,
    auth: AuthContext = Depends(get_current_user),
):
    _get_team_task(task_id, auth)
    with SessionLocal() as db:
        messages = (
            db.execute(
                select(ChatMessageRecord)
                .where(ChatMessageRecord.task_id == task_id)
                .order_by(ChatMessageRecord.created_at.asc())
            )
            .scalars()
            .all()
        )

    return [
        {
            "id": message.id,
            "role": message.role,
            "content": message.content,
            "task_id": message.task_id,
            "created_at": message.created_at,
        }
        for message in messages
    ]
