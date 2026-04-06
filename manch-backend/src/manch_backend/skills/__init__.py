"""Skill framework — base class, manifest schema, and lifecycle protocol.

Every skill is a self-contained unit that provides one or more *tools*
(registered into the existing ``tools.py`` registry) or *agents*
(registered into the agent registry).

A skill may be:
* **built-in** — shipped with Manch under ``skills/builtins/``
* **plugin**  — installed via pip (entry-point group ``manch.skills``)
* **local**   — dropped into the ``skills/`` folder with a ``manifest.yaml``

Lifecycle:
    init()  →   validate()  →   register()  →   teardown()
"""
from __future__ import annotations

import abc
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from manch_backend.models import RiskLevel

logger = logging.getLogger(__name__)


# ── Manifest Schema ──────────────────────────────────


class SkillKind(str, Enum):
    """Whether a skill contributes tools, agents, or both."""
    TOOL = "tool"
    AGENT = "agent"
    COMPOSITE = "composite"  # provides both


@dataclass
class SkillManifest:
    """Declarative metadata parsed from ``manifest.yaml`` or set in code."""
    name: str
    version: str = "0.1.0"
    description: str = ""
    kind: SkillKind = SkillKind.TOOL
    risk_level: RiskLevel = RiskLevel.LOW
    author: str = ""
    tags: list[str] = field(default_factory=list)
    # Dependencies — other skill names that must be loaded first.
    dependencies: list[str] = field(default_factory=list)
    # JSON-Schema-like dict describing accepted configuration keys.
    config_schema: dict[str, Any] = field(default_factory=dict)


# ── Base Skill ───────────────────────────────────────


class BaseSkill(abc.ABC):
    """Abstract base every skill must subclass.

    Subclasses implement the four lifecycle hooks. The skill registry
    calls them in order.
    """

    manifest: SkillManifest  # subclasses must set this

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        self.config: dict[str, Any] = config or {}
        self._initialised = False

    # ── Lifecycle hooks (override as needed) ─────────

    def init(self) -> None:
        """Called once after the skill is loaded. Use for heavy setup."""
        self._initialised = True

    def validate(self) -> list[str]:
        """Return a list of validation errors (empty = OK).

        Check that required config keys exist, external services are
        reachable, etc.
        """
        return []

    @abc.abstractmethod
    def register(self) -> None:
        """Register tools / agents into the global registries.

        This is the only *required* hook. It runs after ``init()`` and
        ``validate()`` pass.
        """

    def teardown(self) -> None:
        """Called when the skill is disabled or the server shuts down."""
        self._initialised = False

    # ── Helpers ──────────────────────────────────────

    @property
    def name(self) -> str:
        return self.manifest.name

    def to_skill_md(self) -> str:
        """Generate a SKILL.md document suitable for injection into codex-cli or
        gemini-cli.  The output follows the agentskills.io open standard — YAML
        frontmatter (``name`` + ``description``) followed by a Markdown body.

        The description in the frontmatter is the primary triggering signal: the
        CLI reads it to decide when to activate the skill, so it must be clear
        and concise.  The body is only loaded after the skill triggers.
        """
        m = self.manifest
        tags_str = ", ".join(m.tags) if m.tags else ""
        lines: list[str] = [
            "---",
            f"name: {m.name}",
            # description must be single-line for the YAML parser
            f"description: {m.description.replace(chr(10), ' ').strip()}",
            "---",
            "",
            f"# {m.name.replace('-', ' ').title()}",
            "",
            m.description.strip(),
            "",
        ]
        if tags_str:
            lines += [f"**Tags**: {tags_str}  ", ""]
        lines += [
            f"**Risk level**: {m.risk_level.value}  ",
            "",
            "## Instructions",
            "",
            f"Use this skill for tasks related to: {m.description.strip()}",
            "",
            "Always verify that operations completed successfully before reporting done.",
        ]
        return "\n".join(lines)

    def __repr__(self) -> str:
        return f"<Skill {self.manifest.name} v{self.manifest.version}>"
