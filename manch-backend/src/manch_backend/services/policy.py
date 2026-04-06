"""Structured command-level policy engine.

Classifies risk at two levels:
  1. Prompt-level: keyword/pattern matching on the user prompt
  2. Command-level: intercepts specific shell commands before execution
"""
from __future__ import annotations

import re
import logging
from dataclasses import dataclass
from manch_backend.models import RiskLevel

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CommandRule:
    """A single command-level policy rule."""
    pattern: re.Pattern[str]
    risk: RiskLevel
    label: str


# Command-level rules (ordered high->low so first match wins)
_COMMAND_RULES: list[CommandRule] = [
    # CRITICAL: destructive / credential-touching
    CommandRule(re.compile(r"\brm\s+-rf\s+/", re.I), RiskLevel.CRITICAL, "recursive delete from root"),
    CommandRule(re.compile(r"\bdrop\s+(table|database)\b", re.I), RiskLevel.CRITICAL, "drop table/database"),
    CommandRule(re.compile(r"\btruncate\s+table\b", re.I), RiskLevel.CRITICAL, "truncate table"),
    CommandRule(re.compile(r"\bdelete\s+from\b.*\bwhere\b.*=\s*1\s*=\s*1", re.I), RiskLevel.CRITICAL, "delete all rows"),
    CommandRule(re.compile(r"\bcurl\b.*\|\s*(bash|sh)\b", re.I), RiskLevel.CRITICAL, "pipe curl to shell"),
    CommandRule(re.compile(r"\bchmod\s+777\b", re.I), RiskLevel.CRITICAL, "world-writable permission"),
    CommandRule(re.compile(r"\bpasswd\b|\b/etc/shadow\b", re.I), RiskLevel.CRITICAL, "password/shadow access"),
    CommandRule(re.compile(r"\bsudo\b", re.I), RiskLevel.CRITICAL, "sudo escalation"),
    # HIGH: system-modifying
    CommandRule(re.compile(r"\b(pip|npm|yarn|pnpm)\s+install\b", re.I), RiskLevel.HIGH, "package install"),
    CommandRule(re.compile(r"\balembic\s+upgrade\b", re.I), RiskLevel.HIGH, "database migration"),
    CommandRule(re.compile(r"\bdocker\s+(build|push|run)\b", re.I), RiskLevel.HIGH, "docker operation"),
    CommandRule(re.compile(r"\bgit\s+push\b", re.I), RiskLevel.HIGH, "git push"),
    CommandRule(re.compile(r"\bgit\s+checkout\s+-b\b", re.I), RiskLevel.HIGH, "git branch creation"),
    CommandRule(re.compile(r"\bdeploy\b", re.I), RiskLevel.HIGH, "deployment command"),
    CommandRule(re.compile(r"\bsystemctl\s+(start|stop|restart)\b", re.I), RiskLevel.HIGH, "systemd service control"),
    # MEDIUM: code modification
    CommandRule(re.compile(r"\bsed\s+-i\b", re.I), RiskLevel.MEDIUM, "in-place file edit"),
    CommandRule(re.compile(r"\bmv\b.*\.(py|ts|js|rs|go)\b", re.I), RiskLevel.MEDIUM, "rename source file"),
    CommandRule(re.compile(r"\bgit\s+commit\b", re.I), RiskLevel.MEDIUM, "git commit"),
]

# Prompt-level keyword rules
_PROMPT_CRITICAL = {"delete all", "drop table", "secret", "production", "destroy", "rm -rf"}
_PROMPT_HIGH = {"install", "migration", "schema", "docker", "deploy", "push to"}
_PROMPT_MEDIUM = {"refactor", "rename", "update", "modify", "rewrite"}


class PolicyEngine:
    """Classifies risk for prompts and individual commands."""

    @staticmethod
    def classify_risk(prompt: str) -> RiskLevel:
        """Classify prompt-level risk."""
        text = prompt.lower()
        if any(word in text for word in _PROMPT_CRITICAL):
            return RiskLevel.CRITICAL
        if any(word in text for word in _PROMPT_HIGH):
            return RiskLevel.HIGH
        if any(word in text for word in _PROMPT_MEDIUM):
            return RiskLevel.MEDIUM
        return RiskLevel.LOW

    @staticmethod
    def classify_command(command: str) -> tuple[RiskLevel, str]:
        """Classify a specific shell command. Returns (risk, label)."""
        for rule in _COMMAND_RULES:
            if rule.pattern.search(command):
                logger.info("Command matched rule: %s -> %s", rule.label, rule.risk.value)
                return rule.risk, rule.label
        return RiskLevel.LOW, "no matching rule"

    @staticmethod
    def requires_approval(risk: RiskLevel) -> bool:
        return risk in {RiskLevel.HIGH, RiskLevel.CRITICAL}

    @staticmethod
    def should_block(risk: RiskLevel) -> bool:
        """CRITICAL commands should be blocked outright (not just need approval)."""
        return risk == RiskLevel.CRITICAL
