from threading import Lock
from datetime import datetime, UTC
from forgepilot_backend.models import Task, Session, TaskStatus


class InMemoryState:
    def __init__(self) -> None:
        self._lock = Lock()
        self.tasks: dict[str, Task] = {}
        self.sessions: dict[str, Session] = {}

    def add_task(self, task: Task) -> None:
        with self._lock:
            self.tasks[task.id] = task

    def update_task_status(self, task_id: str, status: TaskStatus) -> Task | None:
        with self._lock:
            task = self.tasks.get(task_id)
            if not task:
                return None
            task.status = status
            task.updated_at = datetime.now(UTC)
            self.tasks[task_id] = task
            return task

    def add_session(self, session: Session) -> None:
        with self._lock:
            self.sessions[session.id] = session


state = InMemoryState()
