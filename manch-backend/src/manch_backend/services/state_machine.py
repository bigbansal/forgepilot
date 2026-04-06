"""Task state machine — enforces valid transitions per §15 of system design."""
from __future__ import annotations

import logging
from manch_backend.models import TaskStatus

logger = logging.getLogger(__name__)

# Allowed transitions: current → set of valid targets
_TRANSITIONS: dict[TaskStatus, set[TaskStatus]] = {
    TaskStatus.CREATED: {TaskStatus.PLANNING, TaskStatus.RUNNING, TaskStatus.FAILED, TaskStatus.CANCELLED},
    TaskStatus.PLANNING: {TaskStatus.RUNNING, TaskStatus.FAILED, TaskStatus.CANCELLED},
    TaskStatus.RUNNING: {
        TaskStatus.WAITING_APPROVAL,
        TaskStatus.VALIDATING,
        TaskStatus.COMPLETED,  # only when plan has no sentinel step
        TaskStatus.FAILED,
        TaskStatus.CANCELLED,
    },
    TaskStatus.WAITING_APPROVAL: {
        TaskStatus.RUNNING,     # approved → resume
        TaskStatus.FAILED,      # rejected
        TaskStatus.CANCELLED,   # rejected
    },
    TaskStatus.VALIDATING: {
        TaskStatus.COMPLETED,
        TaskStatus.FAILED,
    },
    TaskStatus.COMPLETED: set(),   # terminal
    TaskStatus.FAILED: set(),      # terminal
    TaskStatus.CANCELLED: set(),   # terminal
}


class InvalidTransitionError(Exception):
    """Raised when a state transition is not allowed."""

    def __init__(self, current: TaskStatus, target: TaskStatus) -> None:
        self.current = current
        self.target = target
        super().__init__(
            f"Invalid state transition: {current.value} → {target.value}. "
            f"Allowed from {current.value}: {sorted(s.value for s in _TRANSITIONS.get(current, set()))}"
        )


class TaskStateMachine:
    """Guards all task status transitions.

    Usage:
        sm = TaskStateMachine()
        sm.transition(current_status, target_status)          # raises on invalid
        sm.can_transition(current_status, target_status)      # returns bool
    """

    @staticmethod
    def transition(current: TaskStatus, target: TaskStatus) -> TaskStatus:
        """Validate and return the target status.

        Raises InvalidTransitionError if the transition is not allowed.
        """
        if target not in _TRANSITIONS.get(current, set()):
            raise InvalidTransitionError(current, target)
        logger.debug("State transition: %s → %s", current.value, target.value)
        return target

    @staticmethod
    def can_transition(current: TaskStatus, target: TaskStatus) -> bool:
        return target in _TRANSITIONS.get(current, set())

    @staticmethod
    def is_terminal(status: TaskStatus) -> bool:
        return status in {TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED}

    @staticmethod
    def allowed_targets(current: TaskStatus) -> set[TaskStatus]:
        return _TRANSITIONS.get(current, set())
