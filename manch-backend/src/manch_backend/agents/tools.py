"""Tool registry — tools available to agents for sandbox interaction and code operations."""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable
from uuid import uuid4

from manch_backend.models import RiskLevel

logger = logging.getLogger(__name__)


@dataclass
class ToolSpec:
    """Specification for a registered tool."""
    name: str
    description: str
    risk_level: RiskLevel = RiskLevel.LOW
    parameters: dict[str, Any] = field(default_factory=dict)
    handler: Callable[..., "ToolResult"] | None = None


@dataclass
class ToolResult:
    """Result returned by a tool execution."""
    success: bool
    output: str = ""
    error: str | None = None
    duration_ms: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


_TOOL_REGISTRY: dict[str, ToolSpec] = {}


def register_tool(spec: ToolSpec) -> None:
    """Register a tool in the global registry."""
    _TOOL_REGISTRY[spec.name] = spec
    logger.debug("Registered tool: %s (risk=%s)", spec.name, spec.risk_level.value)


def get_tool(name: str) -> ToolSpec | None:
    return _TOOL_REGISTRY.get(name)


def list_tools() -> list[ToolSpec]:
    return list(_TOOL_REGISTRY.values())


def execute_tool(name: str, **kwargs: Any) -> ToolResult:
    """Execute a registered tool by name."""
    spec = _TOOL_REGISTRY.get(name)
    if not spec:
        return ToolResult(success=False, error=f"Unknown tool: {name}")
    if not spec.handler:
        return ToolResult(success=False, error=f"Tool {name} has no handler")

    start = time.monotonic()
    try:
        result = spec.handler(**kwargs)
        result.duration_ms = int((time.monotonic() - start) * 1000)
        return result
    except Exception as exc:
        duration = int((time.monotonic() - start) * 1000)
        logger.exception("Tool %s failed", name)
        return ToolResult(success=False, error=str(exc), duration_ms=duration)


# ── Built-in tool implementations ────────────────────


def _run_sandbox_command(sandbox_session_id: str, command: str, **_: Any) -> ToolResult:
    """Run a command inside an OpenSandbox session (keeps session alive)."""
    from manch_backend.services.sandbox import OpenSandboxAdapter
    adapter = OpenSandboxAdapter()
    exec_result = adapter.run_command(sandbox_session_id, command, keep_alive=True)
    return ToolResult(
        success=exec_result.exit_code == 0,
        output=exec_result.stdout,
        error=exec_result.stderr if exec_result.exit_code != 0 else None,
    )


def _read_file(sandbox_session_id: str, path: str, **_: Any) -> ToolResult:
    """Read a file from the sandbox."""
    return _run_sandbox_command(sandbox_session_id, f"cat {path}")


def _write_file(sandbox_session_id: str, path: str, content: str, **_: Any) -> ToolResult:
    """Write content to a file in the sandbox."""
    import shlex
    escaped = shlex.quote(content)
    safe_path = shlex.quote(path)
    return _run_sandbox_command(sandbox_session_id, f"printf %s {escaped} > {safe_path}")


def _list_directory(sandbox_session_id: str, path: str = ".", **_: Any) -> ToolResult:
    """List directory contents in the sandbox."""
    return _run_sandbox_command(sandbox_session_id, f"find {path} -maxdepth 2 -type f | head -100")


def _search_code(sandbox_session_id: str, pattern: str, path: str = ".", **_: Any) -> ToolResult:
    """Search code files for a pattern."""
    import shlex
    safe_pattern = shlex.quote(pattern)
    safe_path = shlex.quote(path)
    return _run_sandbox_command(
        sandbox_session_id,
        f"grep -rn --include='*.py' --include='*.ts' --include='*.js' --include='*.java' "
        f"--include='*.go' --include='*.rs' --include='*.md' {safe_pattern} {safe_path} | head -50",
    )


def _git_diff(sandbox_session_id: str, **_: Any) -> ToolResult:
    """Get git diff of current changes."""
    return _run_sandbox_command(sandbox_session_id, "git diff")


def _git_status(sandbox_session_id: str, **_: Any) -> ToolResult:
    """Get git status."""
    return _run_sandbox_command(sandbox_session_id, "git status --porcelain")


def _run_tests(sandbox_session_id: str, command: str = "python -m pytest -x --tb=short 2>&1 | tail -40", **_: Any) -> ToolResult:
    """Run test suite."""
    return _run_sandbox_command(sandbox_session_id, command)


def _apply_patch(sandbox_session_id: str, patch: str, **_: Any) -> ToolResult:
    """Apply a patch/diff to the codebase."""
    import shlex
    escaped = shlex.quote(patch)
    return _run_sandbox_command(sandbox_session_id, f"echo {escaped} | git apply --check && echo {escaped} | git apply")


# ── Register all built-in tools ──────────────────────

_BUILTIN_TOOLS = [
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

for _tool in _BUILTIN_TOOLS:
    register_tool(_tool)
