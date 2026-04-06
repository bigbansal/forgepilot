"""Built-in sandbox tools skill.

Wraps the original 9 tools (run_command, read_file, write_file, etc.)
as the first reference skill implementation.
"""
from __future__ import annotations

from manch_backend.models import RiskLevel
from manch_backend.skills import BaseSkill, SkillKind, SkillManifest


class SandboxToolsSkill(BaseSkill):
    manifest = SkillManifest(
        name="sandbox-tools",
        version="1.0.0",
        description="Core sandbox interaction tools — file I/O, shell execution, git operations, testing.",
        kind=SkillKind.TOOL,
        risk_level=RiskLevel.MEDIUM,
        author="Manch",
        tags=["builtin", "sandbox", "core"],
    )

    def register(self) -> None:
        """Register all 9 sandbox tools into the global tool registry."""
        from manch_backend.agents.tools import ToolSpec, register_tool, get_tool

        # Lazy-import handlers from the original tools module
        from manch_backend.agents.tools import (
            _run_sandbox_command,
            _read_file,
            _write_file,
            _list_directory,
            _search_code,
            _git_diff,
            _git_status,
            _run_tests,
            _apply_patch,
        )

        specs = [
            ToolSpec(name="run_command", description="Run a shell command in the sandbox",
                     risk_level=RiskLevel.MEDIUM, handler=_run_sandbox_command),
            ToolSpec(name="read_file", description="Read a file from the sandbox",
                     risk_level=RiskLevel.LOW, handler=_read_file),
            ToolSpec(name="write_file", description="Write content to a file in the sandbox",
                     risk_level=RiskLevel.MEDIUM, handler=_write_file),
            ToolSpec(name="list_directory", description="List files in a directory",
                     risk_level=RiskLevel.LOW, handler=_list_directory),
            ToolSpec(name="search_code", description="Search code for a pattern (grep)",
                     risk_level=RiskLevel.LOW, handler=_search_code),
            ToolSpec(name="git_diff", description="Get git diff of changes",
                     risk_level=RiskLevel.LOW, handler=_git_diff),
            ToolSpec(name="git_status", description="Get git status",
                     risk_level=RiskLevel.LOW, handler=_git_status),
            ToolSpec(name="run_tests", description="Run the test suite",
                     risk_level=RiskLevel.MEDIUM, handler=_run_tests),
            ToolSpec(name="apply_patch", description="Apply a patch to the codebase",
                     risk_level=RiskLevel.HIGH, handler=_apply_patch),
        ]

        for spec in specs:
            # Only register if not already present (avoids double-register)
            if not get_tool(spec.name):
                register_tool(spec)


# Module-level instance — the registry loads this automatically.
skill = SandboxToolsSkill()
