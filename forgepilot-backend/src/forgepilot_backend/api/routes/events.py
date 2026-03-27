import asyncio
import json
from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse
from forgepilot_backend.core.deps import get_user_from_token
from forgepilot_backend.services.events import event_broker

router = APIRouter()


@router.get("/stream")
async def stream_events(token: str = Query(..., description="JWT access token")):
    # Authenticate via query param (EventSource API cannot set Authorization headers)
    current_user = get_user_from_token(token)

    subscriber = await event_broker.subscribe(user_id=current_user.id)

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
