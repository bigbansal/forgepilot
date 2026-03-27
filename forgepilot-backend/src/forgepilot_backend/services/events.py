import asyncio
from dataclasses import dataclass, field
from datetime import datetime, UTC
from typing import Any


@dataclass
class _Subscriber:
    queue: asyncio.Queue[dict[str, Any]] = field(default_factory=asyncio.Queue)
    user_id: str | None = None


class EventBroker:
    def __init__(self) -> None:
        self._subscribers: list[_Subscriber] = []
        self._lock = asyncio.Lock()
        self._main_loop: asyncio.AbstractEventLoop | None = None

    def set_main_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        """Register the main event loop so background threads can schedule publishes."""
        self._main_loop = loop

    def publish_threadsafe(self, event_type: str, payload: dict[str, Any], user_id: str | None = None) -> None:
        """Publish an event from a background (non-async) thread."""
        if self._main_loop and self._main_loop.is_running():
            asyncio.run_coroutine_threadsafe(
                self.publish(event_type, payload, user_id=user_id), self._main_loop
            )

    async def subscribe(self, user_id: str | None = None) -> asyncio.Queue[dict[str, Any]]:
        sub = _Subscriber(user_id=user_id)
        async with self._lock:
            self._subscribers.append(sub)
        return sub.queue

    async def unsubscribe(self, queue: asyncio.Queue[dict[str, Any]]) -> None:
        async with self._lock:
            self._subscribers = [s for s in self._subscribers if s.queue is not queue]

    async def publish(self, event_type: str, payload: dict[str, Any], user_id: str | None = None) -> None:
        event = {
            "type": event_type,
            "timestamp": datetime.now(UTC).isoformat(),
            "payload": payload,
        }
        async with self._lock:
            subscribers = list(self._subscribers)
        for sub in subscribers:
            # Deliver if: event has no user scope OR subscriber has no filter OR they match
            if user_id is None or sub.user_id is None or sub.user_id == user_id:
                await sub.queue.put(event)


event_broker = EventBroker()
