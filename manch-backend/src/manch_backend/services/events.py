import asyncio
from dataclasses import dataclass, field
from datetime import datetime, UTC
from typing import Any


@dataclass
class _Subscriber:
    queue: asyncio.Queue[dict[str, Any]] = field(default_factory=asyncio.Queue)
    user_id: str | None = None
    team_id: str | None = None
    task_ids: set[str] = field(default_factory=set)  # empty → all tasks


class EventBroker:
    def __init__(self) -> None:
        self._subscribers: list[_Subscriber] = []
        self._lock = asyncio.Lock()
        self._main_loop: asyncio.AbstractEventLoop | None = None

    def set_main_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        """Register the main event loop so background threads can schedule publishes."""
        self._main_loop = loop

    def publish_threadsafe(
        self,
        event_type: str,
        payload: dict[str, Any],
        user_id: str | None = None,
        team_id: str | None = None,
    ) -> None:
        """Publish an event from a background (non-async) thread."""
        if self._main_loop and self._main_loop.is_running():
            asyncio.run_coroutine_threadsafe(
                self.publish(event_type, payload, user_id=user_id, team_id=team_id),
                self._main_loop,
            )

    async def subscribe(
        self,
        user_id: str | None = None,
        team_id: str | None = None,
    ) -> asyncio.Queue[dict[str, Any]]:
        sub = _Subscriber(user_id=user_id, team_id=team_id)
        async with self._lock:
            self._subscribers.append(sub)
        return sub.queue

    async def unsubscribe(self, queue: asyncio.Queue[dict[str, Any]]) -> None:
        async with self._lock:
            self._subscribers = [s for s in self._subscribers if s.queue is not queue]

    async def add_task_filter(self, queue: asyncio.Queue[dict[str, Any]], task_id: str) -> None:
        """Add a task_id to a subscriber's filter set (for WS subscribe action)."""
        async with self._lock:
            for s in self._subscribers:
                if s.queue is queue:
                    s.task_ids.add(task_id)
                    break

    async def remove_task_filter(self, queue: asyncio.Queue[dict[str, Any]], task_id: str) -> None:
        """Remove a task_id from a subscriber's filter set."""
        async with self._lock:
            for s in self._subscribers:
                if s.queue is queue:
                    s.task_ids.discard(task_id)
                    break

    async def publish(
        self,
        event_type: str,
        payload: dict[str, Any],
        user_id: str | None = None,
        team_id: str | None = None,
    ) -> None:
        event = {
            "type": event_type,
            "timestamp": datetime.now(UTC).isoformat(),
            "payload": payload,
        }
        async with self._lock:
            subscribers = list(self._subscribers)
        for sub in subscribers:
            # ── Team filter: deliver if team matches or no team scope ──
            if team_id and sub.team_id and sub.team_id != team_id:
                continue
            # ── User filter: fallback when no team ──
            if not team_id and user_id and sub.user_id and sub.user_id != user_id:
                continue
            # ── Task filter: only if subscriber has task-level filters ──
            event_task_id = payload.get("task_id") or payload.get("id")
            if sub.task_ids and event_task_id and event_task_id not in sub.task_ids:
                continue
            await sub.queue.put(event)


event_broker = EventBroker()
