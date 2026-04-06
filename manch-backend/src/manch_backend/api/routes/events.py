import asyncio
import json
from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse
from manch_backend.core.deps import get_user_from_token
from manch_backend.services.events import event_broker

router = APIRouter()


def _extract_task_ids(data: dict) -> list[str]:
    """Accept both 'task_ids' (array) and 'task_id' (string) from WS messages."""
    ids = data.get("task_ids") or []
    if isinstance(ids, str):
        ids = [ids]
    single = data.get("task_id")
    if single and isinstance(single, str) and single not in ids:
        ids.append(single)
    return ids


@router.get("/stream")
async def stream_events(token: str = Query(..., description="JWT access token")):
    """SSE endpoint (kept for backward compatibility; prefer /events/ws)."""
    auth = get_user_from_token(token)

    subscriber = await event_broker.subscribe(user_id=auth.user.id, team_id=auth.team_id)

    async def event_generator():
        try:
            while True:
                try:
                    event = await asyncio.wait_for(subscriber.get(), timeout=15)
                    yield f"event: {event['type']}\ndata: {json.dumps(event)}\n\n"
                except asyncio.TimeoutError:
                    yield "event: heartbeat\ndata: {}\n\n"
        finally:
            await event_broker.unsubscribe(subscriber)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


# ── WebSocket endpoint (Task #59) ─────────────────────────────────

@router.websocket("/ws")
async def websocket_events(websocket: WebSocket, token: str = Query(...)):
    """Bidirectional WebSocket for real-time events. Replaces SSE."""
    try:
        auth = get_user_from_token(token)
    except Exception:
        await websocket.close(code=4001, reason="Unauthorized")
        return

    await websocket.accept()
    subscriber = await event_broker.subscribe(user_id=auth.user.id, team_id=auth.team_id)

    async def _sender():
        """Forward events from the broker queue to the websocket."""
        try:
            while True:
                try:
                    event = await asyncio.wait_for(subscriber.get(), timeout=15)
                    await websocket.send_json(event)
                except asyncio.TimeoutError:
                    # Heartbeat
                    await websocket.send_json({"type": "heartbeat", "timestamp": "", "payload": {}})
        except Exception:
            pass

    async def _receiver():
        """Listen for client messages (subscribe/unsubscribe to tasks, ping)."""
        try:
            while True:
                data = await websocket.receive_json()
                action = data.get("action")
                if action == "ping":
                    await websocket.send_json({"type": "pong", "timestamp": "", "payload": {}})
                elif action == "subscribe":
                    ids = _extract_task_ids(data)
                    for tid in ids:
                        await event_broker.add_task_filter(subscriber, tid)
                elif action == "unsubscribe":
                    ids = _extract_task_ids(data)
                    for tid in ids:
                        await event_broker.remove_task_filter(subscriber, tid)
        except (WebSocketDisconnect, Exception):
            pass

    sender_task = asyncio.create_task(_sender())
    receiver_task = asyncio.create_task(_receiver())

    try:
        # Wait for either direction to close
        done, pending = await asyncio.wait(
            [sender_task, receiver_task], return_when=asyncio.FIRST_COMPLETED
        )
        for task in pending:
            task.cancel()
    finally:
        await event_broker.unsubscribe(subscriber)
        try:
            await websocket.close()
        except Exception:
            pass
