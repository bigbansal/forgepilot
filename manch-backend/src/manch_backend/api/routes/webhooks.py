"""
Webhook endpoints for external bot channels.

Telegram
--------
  POST /api/v1/webhooks/telegram
    Receives Telegram Bot API Update objects.
    Register with:
      curl "https://api.telegram.org/bot<TOKEN>/setWebhook?url=https://<host>/api/v1/webhooks/telegram"

WhatsApp (Meta Cloud API)
-------------------------
  GET  /api/v1/webhooks/whatsapp
    Meta webhook verification handshake.
  POST /api/v1/webhooks/whatsapp
    Receives WhatsApp message events.

Both endpoints acknowledge immediately (HTTP 200) and process messages asynchronously
in background threads, then reply via the respective channel API.
"""
import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse

from manch_backend.config import settings
from manch_backend.services.bot_service import handle_telegram_update, handle_whatsapp_message

logger = logging.getLogger(__name__)

router = APIRouter()


# ═══════════════════════════════════════════════════════════════════
# Telegram
# ═══════════════════════════════════════════════════════════════════

@router.post("/telegram")
async def telegram_webhook(request: Request) -> dict[str, str]:
    """
    Receive a Telegram Update and dispatch it for processing.
    Returns immediately so Telegram does not retry.
    """
    try:
        body: dict[str, Any] = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    # Extract text message from Update object
    message = body.get("message") or body.get("edited_message")
    if not message:
        # Ignore non-message updates (inline queries, callbacks, etc.)
        return {"status": "ignored"}

    chat_id = message.get("chat", {}).get("id")
    text = message.get("text", "").strip()

    if not chat_id or not text:
        return {"status": "ignored"}

    if not settings.telegram_bot_token:
        logger.warning("Telegram webhook received but MANCH_TELEGRAM_BOT_TOKEN is not set")
        return {"status": "ignored"}

    handle_telegram_update(chat_id=chat_id, text=text)
    return {"status": "accepted"}


# ═══════════════════════════════════════════════════════════════════
# WhatsApp (Meta Cloud API)
# ═══════════════════════════════════════════════════════════════════

@router.get("/whatsapp", response_class=PlainTextResponse)
async def whatsapp_verify(
    hub_mode: str = Query(alias="hub.mode", default=""),
    hub_challenge: str = Query(alias="hub.challenge", default=""),
    hub_verify_token: str = Query(alias="hub.verify_token", default=""),
) -> str:
    """
    Meta webhook verification handshake.
    Meta sends a GET request with hub.challenge; we echo it back if the
    verify token matches.
    """
    if hub_mode == "subscribe" and hub_verify_token == settings.whatsapp_verify_token:
        logger.info("WhatsApp webhook verified successfully")
        return hub_challenge
    logger.warning("WhatsApp webhook verification failed — invalid verify_token")
    raise HTTPException(status_code=403, detail="Verification failed")


@router.post("/whatsapp")
async def whatsapp_webhook(request: Request) -> dict[str, str]:
    """
    Receive WhatsApp Cloud API events and dispatch incoming messages.
    Returns immediately so Meta does not retry.
    """
    try:
        body: dict[str, Any] = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    # Walk the Meta payload structure:
    # body.entry[].changes[].value.messages[]{from, text.body}
    try:
        entries = body.get("entry", [])
        for entry in entries:
            for change in entry.get("changes", []):
                value = change.get("value", {})
                messages = value.get("messages", [])
                for msg in messages:
                    msg_type = msg.get("type", "")
                    if msg_type != "text":
                        continue  # ignore images, audio, etc. for now
                    from_number: str = msg.get("from", "").strip()
                    text: str = msg.get("text", {}).get("body", "").strip()
                    if from_number and text:
                        handle_whatsapp_message(from_number=from_number, text=text)
    except Exception:
        logger.exception("Error parsing WhatsApp webhook payload")
        # Still return 200 so Meta does not flood with retries
        return {"status": "error"}

    return {"status": "accepted"}
