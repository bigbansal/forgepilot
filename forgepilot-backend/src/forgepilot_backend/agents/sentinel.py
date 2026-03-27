"""SentinelAgent — validates code changes by running tests, linting, and build checks."""
from __future__ import annotations

import json
import logging

from forgepilot_backend.agents.base import AgentContext, AgentResult, BaseAgent
from forgepilot_backend.agents.llm import LLMMessage
from forgepilot_backend.agents.registry import register_agent
from forgepilot_backend.agents.tools import execute_tool
from forgepilot_backend.models import AgentTier, ModelClass, RiskLevel

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """\
You are Sentinel, the validation agent for ForgePilot.
Your job is to verify that code changes are correct and don't break anything.

Given a summary of changes and the project context, you should:
1. Determine which validation checks are appropriate (tests, lint, type-check, build)
2. Run those checks in the sandbox
3. Analyze the results and report whether the changes are valid

Respond in JSON:
{
  "verdict": "pass" | "fail" | "warn",
  "checks_run": [
    {"name": "tests", "passed": true, "details": "..."},
    {"name": "lint", "passed": true, "details": "..."}
  ],
  "issues": ["issue 1 if any"],
  "summary": "Overall assessment"
}
"""

# Common validation commands by project type
_VALIDATION_COMMANDS = {
    "python": [
        ("tests", "python -m pytest -x --tb=short 2>&1 | tail -50"),
        ("lint", "python -m ruff check . 2>&1 | tail -30"),
        ("typecheck", "python -m mypy --ignore-missing-imports . 2>&1 | tail -30"),
    ],
    "node": [
        ("tests", "npm test 2>&1 | tail -50"),
        ("lint", "npm run lint 2>&1 | tail -30"),
        ("build", "npm run build 2>&1 | tail -30"),
    ],
    "default": [
        ("tests", "python -m pytest -x --tb=short 2>&1 | tail -50 || npm test 2>&1 | tail -50"),
    ],
}


@register_agent
class SentinelAgent(BaseAgent):
    name = "sentinel"
    tier = AgentTier.SPECIALIST
    model_class = ModelClass.FAST
    parallel_safe = True
    purpose = "Validates code changes by running tests, linting, and build checks."

    def run(self, ctx: AgentContext) -> AgentResult:
        self._logger.info("Validating changes for task=%s", ctx.task_id)

        if not ctx.sandbox_session_id:
            return AgentResult(
                success=False,
                output="",
                error="No sandbox session available for validation.",
            )

        # Determine project type from context
        project_type = ctx.extra.get("project_type", "default")
        commands = _VALIDATION_COMMANDS.get(project_type, _VALIDATION_COMMANDS["default"])

        # Step 1: Get current git diff to understand what changed
        diff_result = execute_tool("git_diff", sandbox_session_id=ctx.sandbox_session_id)
        status_result = execute_tool("git_status", sandbox_session_id=ctx.sandbox_session_id)

        # Step 2: Run validation checks
        check_results: list[dict] = []
        for check_name, command in commands:
            self._logger.debug("Running check: %s", check_name)
            result = execute_tool("run_command", sandbox_session_id=ctx.sandbox_session_id, command=command)
            check_results.append({
                "name": check_name,
                "command": command,
                "passed": result.success,
                "output": result.output[:2000] if result.output else "",
                "error": result.error[:500] if result.error else None,
            })

        # Step 3: Ask LLM to analyze results
        system_prompt = self.build_system_prompt() or _SYSTEM_PROMPT
        from forgepilot_backend.agents.llm import llm_client as llm

        analysis_input = (
            f"Task: {ctx.prompt}\n\n"
            f"## Git Status\n{status_result.output[:1000]}\n\n"
            f"## Git Diff (summary)\n{diff_result.output[:3000]}\n\n"
            f"## Validation Results\n{json.dumps(check_results, indent=2)[:4000]}\n\n"
            "Analyze the results and provide your verdict."
        )

        messages = [
            LLMMessage(role="system", content=system_prompt),
            LLMMessage(role="user", content=analysis_input),
        ]

        try:
            resp = llm.chat(messages, model_class=self.model_class, response_format="json")
            verdict_data = json.loads(resp.content)

            verdict = verdict_data.get("verdict", "warn")
            passed = verdict == "pass"

            return AgentResult(
                success=passed,
                output=resp.content,
                risk_level=RiskLevel.LOW,
                metadata={
                    "verdict": verdict,
                    "checks_run": verdict_data.get("checks_run", check_results),
                    "issues": verdict_data.get("issues", []),
                    "usage": resp.usage,
                },
                artifacts=[
                    {
                        "type": "validation_report",
                        "content": resp.content,
                    }
                ],
            )
        except Exception as exc:
            self._logger.exception("Sentinel analysis failed")
            # Fall back to raw check results
            all_passed = all(c["passed"] for c in check_results)
            return AgentResult(
                success=all_passed,
                output=json.dumps(check_results, indent=2),
                risk_level=RiskLevel.LOW,
                error=str(exc) if not all_passed else None,
                metadata={"checks_run": check_results, "verdict": "pass" if all_passed else "fail"},
            )
