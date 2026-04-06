"""Agent registry — discovers and provides access to all registered agents."""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from manch_backend.agents.base import BaseAgent

logger = logging.getLogger(__name__)

_REGISTRY: dict[str, type["BaseAgent"]] = {}


def register_agent(cls: type["BaseAgent"]) -> type["BaseAgent"]:
    """Class decorator to register an agent in the global registry."""
    _REGISTRY[cls.name] = cls
    logger.debug("Registered agent: %s", cls.name)
    return cls


def get_agent(name: str) -> "BaseAgent":
    """Instantiate an agent by name."""
    cls = _REGISTRY.get(name)
    if cls is None:
        raise KeyError(f"Unknown agent: {name}. Available: {list(_REGISTRY.keys())}")
    return cls()


def list_agents() -> list["BaseAgent"]:
    """Return one instance of every registered agent."""
    return [cls() for cls in _REGISTRY.values()]


def available_agent_names() -> list[str]:
    """Return sorted list of registered agent names."""
    return sorted(_REGISTRY.keys())


def _auto_discover() -> None:
    """Import all agent modules so @register_agent decorators fire."""
    from manch_backend.agents import (  # noqa: F401
        guardian,
        scout,
        coder,
        sentinel,
        maestro,
        architect,
        fixer,
        reviewer,
        devops,
        docsmith,
        memory,
    )


_auto_discover()
