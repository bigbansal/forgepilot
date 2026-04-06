from datetime import UTC, datetime
from threading import Thread
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select

from manch_backend.core.deps import get_current_user, AuthContext
from manch_backend.db.models import ChatMessageRecord, ConversationRecord
from manch_backend.db.session import SessionLocal
from manch_backend.models import TaskRunner
from manch_backend.services.orchestrator import orchestrator

router = APIRouter()


class ConversationCreateRequest(BaseModel):
    title: str | None = None


class MessageCreateRequest(BaseModel):
    content: str
    runner: TaskRunner = TaskRunner.OPENSANDBOX
    approval_mode: str = "yolo"  # yolo | auto_edit | plan
    repo_id: str | None = None


def _message_to_dict(record: ChatMessageRecord) -> dict:
    return {
        "id": record.id,
        "conversation_id": record.conversation_id,
        "role": record.role,
        "content": record.content,
        "task_id": record.task_id,
        "created_at": record.created_at,
    }


def _conversation_to_dict(record: ConversationRecord, messages: list[ChatMessageRecord] | None = None) -> dict:
    payload = {
        "id": record.id,
        "title": record.title,
        "created_at": record.created_at,
        "updated_at": record.updated_at,
    }
    if messages is not None:
        payload["messages"] = [_message_to_dict(message) for message in messages]
    return payload


def _derive_title(content: str) -> str:
    cleaned = " ".join(content.strip().split())
    if not cleaned:
        return "New Chat"
    return f"{cleaned[:40]}..." if len(cleaned) > 40 else cleaned


_HISTORY_ROLES = {"user", "assistant"}
_MAX_HISTORY_TURNS = 10  # last N user+assistant messages to include


def _build_prompt_with_history(
    prior_messages: list[ChatMessageRecord],
    new_user_content: str,
) -> str:
    """Prepend recent conversation history so the agent has memory of prior turns."""
    history = [
        m for m in prior_messages
        if m.role in _HISTORY_ROLES
    ][-_MAX_HISTORY_TURNS:]

    if not history:
        return new_user_content

    lines: list[str] = [
        "=== Conversation history (most recent first shown last) ===",
    ]
    for m in history:
        role_label = "User" if m.role == "user" else "Assistant"
        lines.append(f"{role_label}: {m.content.strip()}")

    lines += [
        "=== End of history ===",
        "",
        f"User: {new_user_content}",
    ]
    return "\n".join(lines)


@router.post("")
def create_conversation(
    request: ConversationCreateRequest | None = None,
    auth: AuthContext = Depends(get_current_user),
):
    now = datetime.now(UTC)
    title = request.title.strip() if request and request.title else "New Chat"
    if not title:
        title = "New Chat"

    record = ConversationRecord(
        id=str(uuid4()),
        title=title,
        user_id=auth.user.id,
        team_id=auth.team_id,
        created_at=now,
        updated_at=now,
    )
    with SessionLocal() as db:
        db.add(record)
        db.commit()
        db.refresh(record)
        return _conversation_to_dict(record, messages=[])


@router.get("")
def list_conversations(auth: AuthContext = Depends(get_current_user)):
    with SessionLocal() as db:
        stmt = select(ConversationRecord).order_by(ConversationRecord.updated_at.desc())
        if auth.team_id:
            stmt = stmt.where(ConversationRecord.team_id == auth.team_id)
        else:
            stmt = stmt.where(ConversationRecord.user_id == auth.user.id)
        rows = db.execute(stmt).scalars().all()
        return [_conversation_to_dict(row) for row in rows]


@router.get("/{conversation_id}")
def get_conversation(
    conversation_id: str,
    auth: AuthContext = Depends(get_current_user),
):
    with SessionLocal() as db:
        conversation = db.get(ConversationRecord, conversation_id)
        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")
        # Team-scoped check
        if auth.team_id:
            if conversation.team_id != auth.team_id:
                raise HTTPException(status_code=404, detail="Conversation not found")
        elif conversation.user_id != auth.user.id:
            raise HTTPException(status_code=404, detail="Conversation not found")

        messages = (
            db.execute(
                select(ChatMessageRecord)
                .where(ChatMessageRecord.conversation_id == conversation_id)
                .order_by(ChatMessageRecord.created_at.asc())
            )
            .scalars()
            .all()
        )
        return _conversation_to_dict(conversation, messages=messages)


@router.post("/{conversation_id}/messages")
def send_message(
    conversation_id: str,
    request: MessageCreateRequest,
    auth: AuthContext = Depends(get_current_user),
):
    content = request.content.strip()
    if not content:
        raise HTTPException(status_code=400, detail="Message content cannot be empty")

    conversation_payload: dict | None = None
    with SessionLocal() as db:
        conversation = db.get(ConversationRecord, conversation_id)
        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")
        if auth.team_id:
            if conversation.team_id != auth.team_id:
                raise HTTPException(status_code=404, detail="Conversation not found")
        elif conversation.user_id != auth.user.id:
            raise HTTPException(status_code=404, detail="Conversation not found")

        now = datetime.now(UTC)
        user_message = ChatMessageRecord(
            id=str(uuid4()),
            conversation_id=conversation_id,
            role="user",
            content=content,
            task_id=None,
            created_at=now,
        )
        db.add(user_message)
        db.flush()

        existing_count = (
            db.execute(
                select(ChatMessageRecord.id).where(ChatMessageRecord.conversation_id == conversation_id)
            )
            .scalars()
            .all()
        )
        if len(existing_count) <= 1 and (not conversation.title or conversation.title == "New Chat"):
            conversation.title = _derive_title(content)

        # Load prior messages to build a history-aware prompt
        prior_messages = (
            db.execute(
                select(ChatMessageRecord)
                .where(ChatMessageRecord.conversation_id == conversation_id)
                .where(ChatMessageRecord.id != user_message.id)
                .order_by(ChatMessageRecord.created_at.asc())
            )
            .scalars()
            .all()
        )
        prompt_with_history = _build_prompt_with_history(prior_messages, content)

        # Pre-build history list while session is still open (avoids DetachedInstanceError)
        history_for_agents = [
            {"role": m.role, "content": m.content}
            for m in prior_messages[-10:]
        ]

        task = orchestrator.create_task(
            prompt_with_history,
            user_id=auth.user.id,
            team_id=auth.team_id,
            conversation_id=conversation_id,
            repo_id=request.repo_id,
        )

        system_message = ChatMessageRecord(
            id=str(uuid4()),
            conversation_id=conversation_id,
            role="system",
            content=f"Task created: {task.id}. Execution started with runner={request.runner.value}.",
            task_id=task.id,
            created_at=datetime.now(UTC),
        )
        db.add(system_message)

        conversation.updated_at = datetime.now(UTC)
        db.add(conversation)
        db.commit()

        messages = (
            db.execute(
                select(ChatMessageRecord)
                .where(ChatMessageRecord.conversation_id == conversation_id)
                .order_by(ChatMessageRecord.created_at.asc())
            )
            .scalars()
            .all()
        )
        conversation_payload = _conversation_to_dict(conversation, messages=messages)

    def _execute_in_background() -> None:
        if request.runner.value == "agent-pipeline":
            # ── Phase 2: Agent-based pipeline ─────────────
            # history_for_agents is pre-built above while session was open
            task_result, _msg = orchestrator.start_task_v2(
                task.id,
                user_id=auth.user.id,
                team_id=auth.team_id,
                history=history_for_agents,
                conversation_id=conversation_id,
            )
            # The agent pipeline runs async; post an initial message
            with SessionLocal() as bg_db:
                assistant_message = ChatMessageRecord(
                    id=str(uuid4()),
                    conversation_id=conversation_id,
                    role="assistant",
                    content="Agent pipeline started. I'll update you as each step completes.",
                    task_id=task_result.id if task_result else task.id,
                    created_at=datetime.now(UTC),
                )
                bg_db.add(assistant_message)
                bg_conversation = bg_db.get(ConversationRecord, conversation_id)
                if bg_conversation:
                    bg_conversation.updated_at = datetime.now(UTC)
                    bg_db.add(bg_conversation)
                bg_db.commit()
        else:
            # ── Phase 1: Direct sandbox command ───────────
            task_result, _session, message, output = orchestrator.start_task(
                task.id, runner=request.runner, approval_mode=request.approval_mode, user_id=auth.user.id, team_id=auth.team_id
            )
            output_text = [
                message,
                output.get("stdout") if output else None,
                f"stderr: {output.get('stderr')}" if output and output.get("stderr") else None,
                f"risk: {output.get('risk')}" if output and output.get("risk") else None,
            ]
            assistant_text = "\n\n".join(part for part in output_text if part)

            with SessionLocal() as bg_db:
                assistant_message = ChatMessageRecord(
                    id=str(uuid4()),
                    conversation_id=conversation_id,
                    role="assistant",
                    content=assistant_text or "Task completed.",
                    task_id=task_result.id if task_result else task.id,
                    created_at=datetime.now(UTC),
                )
                bg_db.add(assistant_message)

                bg_conversation = bg_db.get(ConversationRecord, conversation_id)
                if bg_conversation:
                    bg_conversation.updated_at = datetime.now(UTC)
                    bg_db.add(bg_conversation)

                bg_db.commit()

    Thread(target=_execute_in_background, daemon=True).start()

    return {
        "conversation": conversation_payload,
        "task": task,
    }
