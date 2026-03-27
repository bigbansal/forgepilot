from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select

from forgepilot_backend.core.deps import get_current_user
from forgepilot_backend.db.models import ChatMessageRecord, TaskRecord, UserRecord
from forgepilot_backend.db.session import SessionLocal
from forgepilot_backend.models import TaskRunner
from forgepilot_backend.services.orchestrator import orchestrator

router = APIRouter()


class CreateTaskRequest(BaseModel):
    prompt: str


class StartTaskRequest(BaseModel):
    runner: TaskRunner = TaskRunner.OPENSANDBOX


def _get_owned_task(task_id: str, user_id: str) -> TaskRecord:
    """Load a TaskRecord and 404 if not found or not owned by user."""
    with SessionLocal() as db:
        record = db.get(TaskRecord, task_id)
        if not record or record.user_id != user_id:
            raise HTTPException(status_code=404, detail="Task not found")
        return record


@router.post("")
def create_task(
    request: CreateTaskRequest,
    current_user: UserRecord = Depends(get_current_user),
):
    return orchestrator.create_task(request.prompt, user_id=current_user.id)


@router.post("/{task_id}/start")
def start_task(
    task_id: str,
    request: StartTaskRequest | None = None,
    current_user: UserRecord = Depends(get_current_user),
):
    _get_owned_task(task_id, current_user.id)
    runner = request.runner if request else TaskRunner.OPENSANDBOX
    task, session, message, output = orchestrator.start_task(task_id, runner=runner, user_id=current_user.id)
    if task is None:
        raise HTTPException(status_code=404, detail=message)
    return {"task": task, "session": session, "message": message, "output": output}


@router.get("/{task_id}")
def get_task(
    task_id: str,
    current_user: UserRecord = Depends(get_current_user),
):
    _get_owned_task(task_id, current_user.id)
    task = orchestrator.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@router.get("")
def list_tasks(current_user: UserRecord = Depends(get_current_user)):
    return orchestrator.list_tasks(user_id=current_user.id)


@router.get("/{task_id}/messages")
def get_task_messages(
    task_id: str,
    current_user: UserRecord = Depends(get_current_user),
):
    _get_owned_task(task_id, current_user.id)
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
