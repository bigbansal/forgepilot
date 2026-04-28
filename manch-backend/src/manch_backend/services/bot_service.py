"""
Bot integration service — shared logic for Telegram and WhatsApp channels.

Flow for each incoming message:
  1. Look up (or create) a persistent ConversationRecord keyed by channel+sender.
  2. Add the user message to the conversation history.
  3. Create a task via orchestrator.create_task().
  4. Run orchestrator.start_task() synchronously (called from a background thread
     so the webhook can return 200 immediately).
  5. Store the assistant reply and send it back to the user via the channel API.
"""
from __future__ import annotations

import logging
from datetime import UTC, datetime
from threading import Thread
from uuid import uuid4

import httpx
from sqlalchemy import select

from manch_backend.config import settings
from manch_backend.db.models import ChatMessageRecord, ConversationRecord
from manch_backend.db.session import SessionLocal
from manch_backend.models import TaskRunner
from manch_backend.services.orchestrator import orchestrator

logger = logging.getLogger(__name__)

# ─── Conversation helpers ─────────────────────────────────────────────────────

_BOT_TITLE_PREFIX = {
    "telegram": "telegram:",
    "whatsapp": "whatsapp:",
}


def _channel_title(channel: str, sender_id: str) -> str:
    """Unique conversation title used to look up a persistent bot conversation."""
    prefix = _BOT_TITLE_PREFIX.get(channel, f"{channel}:")
    return f"{prefix}{sender_id}"


def get_or_create_bot_conversation(channel: str, sender_id: str) -> str:
    """Return the conversation_id for this channel+sender, creating one if needed."""
    title = _channel_title(channel, sender_id)
    with SessionLocal() as db:
        row = (
            db.execute(
                select(ConversationRecord)
                .where(ConversationRecord.title == title)
                .where(ConversationRecord.user_id.is_(None))
                .order_by(ConversationRecord.created_at.asc())
                .limit(1)
            )
            .scalars()
            .first()
        )
        if row:
            return row.id

        now = datetime.now(UTC)
        record = ConversationRecord(
            id=str(uuid4()),
            title=title,
            user_id=None,
            team_id=None,
            created_at=now,
            updated_at=now,
        )
        db.add(record)
        db.commit()
        db.refresh(record)
        return record.id


def _get_history(conversation_id: str) -> list[ChatMessageRecord]:
    with SessionLocal() as db:
        return (
            db.execute(
                select(ChatMessageRecord)
                .where(ChatMessageRecord.conversation_id == conversation_id)
                .order_by(ChatMessageRecord.created_at.asc())
            )
            .scalars()
            .all()
        )


def _build_history_prompt(prior: list[ChatMessageRecord], new_content: str) -> str:
    roles = {"user", "assistant"}
    history = [m for m in prior if m.role in roles][-10:]
    if not history:
        return new_content
    lines = ["=== Conversation history (most recent first shown last) ==="]
    for m in history:
        label = "User" if m.role == "user" else "Assistant"
        lines.append(f"{label}: {m.content.strip()}")
    lines += ["=== End of history ===", "", f"User: {new_content}"]
    return "\n".join(lines)


# ─── Core dispatch ────────────────────────────────────────────────────────────

def dispatch_bot_message(
    channel: str,
    sender_id: str,
    text: str,
    reply_fn: "Callable[[str], None]",  # noqa: F821
) -> None:
    """
    Process an incoming bot message and send the reply via reply_fn.
    Designed to be called from a background Thread so the webhook returns immediately.
    """
    try:
        conversation_id = get_or_create_bot_conversation(channel, sender_id)
        prior = _get_history(conversation_id)

        with SessionLocal() as db:
            now = datetime.now(UTC)
            user_msg = ChatMessageRecord(
                id=str(uuid4()),
                conversation_id=conversation_id,
                role="user",
                content=text,
                task_id=None,
                created_at=now,
            )
            db.add(user_msg)
            db.commit()

        prompt = _build_history_prompt(prior, text)
        task = orchestrator.create_task(
            prompt,
            user_id=None,
            team_id=None,
            conversation_id=conversation_id,
        )

        with SessionLocal() as db:
            sys_msg = ChatMessageRecord(
                id=str(uuid4()),
                conversation_id=conversation_id,
                role="system",
                content=f"Task created: {task.id}. Execution started via {channel} bot.",
                task_id=task.id,
                created_at=datetime.now(UTC),
            )
            db.add(sys_msg)
            conv = db.get(ConversationRecord, conversation_id)
            if conv:
                conv.updated_at = datetime.now(UTC)
                db.add(conv)
            db.commit()

        # Run synchronously (this call blocks until task finishes)
        task_result, _session, message, output = orchestrator.start_task(
            task.id,
            runner=TaskRunner.OPENSANDBOX,
            approval_mode="yolo",
            user_id=None,
            team_id=None,
        )

        output_parts = [
            message,
            output.get("stdout") if output else None,
            f"stderr: {output.get('stderr')}" if output and output.get("stderr") else None,
        ]
        reply_text = "\n\n".join(p for p in output_parts if p) or "Task completed."

        # Persist assistant reply
        with SessionLocal() as db:
            asst_msg = ChatMessageRecord(
                id=str(uuid4()),
                conversation_id=conversation_id,
                role="assistant",
                content=reply_text,
                task_id=task_result.id if task_result else task.id,
                created_at=datetime.now(UTC),
            )
            db.add(asst_msg)
            conv = db.get(ConversationRecord, conversation_id)
            if conv:
                conv.updated_at = datetime.now(UTC)
                db.add(conv)
            db.commit()

        reply_fn(reply_text)

    except Exception:
        logger.exception("Bot dispatch error [channel=%s sender=%s]", channel, sender_id)
        try:
            reply_fn("Sorry, an error occurred while processing your request.")
        except Exception:
            pass


# ─── Channel send helpers ──────────────────────────────────────────────────────

def send_telegram_message(chat_id: str | int, text: str) -> None:
    """Send a text message to a Telegram chat via Bot API."""
    token = settings.telegram_bot_token
    if not token:
        logger.warning("MANCH_TELEGRAM_BOT_TOKEN not configured — cannot send reply")
        return
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    # Telegram messages have a 4096 char limit; truncate if needed
    if len(text) > 4096:
        text = text[:4090] + "\n…"
    try:
        resp = httpx.post(url, json={"chat_id": chat_id, "text": text}, timeout=10)
        resp.raise_for_status()
    except Exception:
        logger.exception("Failed to send Telegram message to chat_id=%s", chat_id)


def send_whatsapp_message(to: str, text: str) -> None:
    """Send a text message via WhatsApp Cloud API."""
    token = settings.whatsapp_token
    phone_number_id = settings.whatsapp_phone_number_id
    if not token or not phone_number_id:
        logger.warning("WhatsApp credentials not configured — cannot send reply")
        return
    url = f"https://graph.facebook.com/v19.0/{phone_number_id}/messages"
    # WhatsApp text messages are capped at 4096 chars
    if len(text) > 4096:
        text = text[:4090] + "\n…"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"body": text},
    }
    try:
        resp = httpx.post(url, headers=headers, json=payload, timeout=10)
        resp.raise_for_status()
    except Exception:
        logger.exception("Failed to send WhatsApp message to %s", to)


# ─── Background dispatch factories ───────────────────────────────────────────

def handle_telegram_update(chat_id: int | str, text: str) -> None:
    """Fire-and-forget: process a Telegram message in a background thread."""
    def _reply(reply_text: str) -> None:
        send_telegram_message(chat_id, reply_text)

    Thread(
        target=dispatch_bot_message,
        args=("telegram", str(chat_id), text, _reply),
        daemon=True,
    ).start()


def handle_whatsapp_message(from_number: str, text: str) -> None:
    """Fire-and-forget: process a WhatsApp message in a background thread."""
    def _reply(reply_text: str) -> None:
        send_whatsapp_message(from_number, reply_text)

    Thread(
        target=dispatch_bot_message,
        args=("whatsapp", from_number, text, _reply),
        daemon=True,
    ).start()
