"""Base agent class — all ForgePilot agents inherit from this."""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from forgepilot_backend.models import AgentTier, ModelClass, RiskLevel

logger = logging.getLogger(__name__)


@dataclass
class AgentContext:
    """Runtime context passed into every agent invocation."""
    task_id: str
    step_id: str | None = None
    user_id: str | None = None
    prompt: str = ""
    history: list[dict[str, str]] = field(default_factory=list)
    repo_context: dict[str, Any] = field(default_factory=dict)
    sandbox_session_id: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentResult:
    """Standard result returned by every agent."""
    success: bool
    output: str = ""
    artifacts: list[dict[str, Any]] = field(default_factory=list)
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    next_agent: str | None = None
    risk_level: RiskLevel = RiskLevel.LOW
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class BaseAgent(ABC):
    """Abstract base class for all ForgePilot agents."""

    name: str = "base"
    tier: AgentTier = AgentTier.SPECIALIST
    model_class: ModelClass = ModelClass.BALANCED
    parallel_safe: bool = True
    purpose: str = ""

    def __init__(self) -> None:
        self._logger = logging.getLogger(f"agent.{self.name}")

    @abstractmethod
    def run(self, ctx: AgentContext) -> AgentResult:
        """Execute the agent's primary task. Must be overridden."""
        ...

    def build_system_prompt(self) -> str:
        """Load the agent's soul definition from .github/agents/{name}.md."""
        from pathlib import Path
        # Walk up from this file to find a directory containing .github/agents/
        current = Path(__file__).resolve().parent
        for _ in range(8):
            candidate = current / ".github" / "agents" / f"{self.name}.md"
            if candidate.exists():
                return candidate.read_text(encoding="utf-8")
            current = current.parent
        return f"You are {self.name}, a {self.tier.value} agent. {self.purpose}"

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} name={self.name} tier={self.tier.value}>"
