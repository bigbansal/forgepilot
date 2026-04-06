"""FixerAgent — diagnoses failures, proposes focused fixes, and verifies resolution."""
from __future__ import annotations

import json
import logging

from manch_backend.agents.base import AgentContext, AgentResult, BaseAgent
from manch_backend.agents.llm import LLMMessage
from manch_backend.agents.registry import register_agent
from manch_backend.agents.tools import execute_tool
from manch_backend.models import AgentTier, ModelClass, RiskLevel

logger = logging.getLogger(__name__)

_MAX_FIX_ITERATIONS = 6

_SYSTEM_PROMPT = """\
You are Fixer, the debugging and repair agent for Manch.
Your job is to diagnose concrete failures and resolve them with the smallest reliable change.

For each step, respond with a JSON object:
{
  "action": "read_file" | "run_command" | "search_code" | "write_file" | "done",
  "params": { ... },
  "reasoning": "Why you're taking this step",
  "diagnosis": "Current root cause hypothesis"
}

When action is "done":
{
  "action": "done",
  "params": {
    "root_cause": "Identified root cause",
    "fix_summary": "What was changed to fix it",
    "files_changed": ["list of modified files"],
    "confidence": "HIGH" | "MEDIUM" | "LOW",
    "regression_risk": "Description of regression risk",
    "recommended_tests": ["test suggestions"]
  },
  "reasoning": "Final reasoning",
  "diagnosis": "Confirmed root cause"
}

Guidelines:
- Restate the failure exactly before investigating
- Separate symptom from root cause
- Make the smallest change that fixes the issue
- Always verify the fix by re-running the failing path
- Never mix unrelated fixes into one change
"""


@register_agent
class FixerAgent(BaseAgent):
    name = "fixer"
    tier = AgentTier.SPECIALIST
    model_class = ModelClass.REASONING
    parallel_safe = False
    purpose = "Diagnoses failures, proposes focused fixes, and verifies resolution."

    def run(self, ctx: AgentContext) -> AgentResult:
        self._logger.info("Fixing failure for task=%s", ctx.task_id)

        if not ctx.sandbox_session_id:
            return AgentResult(
                success=False, output="",
                error="No sandbox session available for debugging.",
            )

        system_prompt = self.build_system_prompt() or _SYSTEM_PROMPT
        from manch_backend.agents.llm import llm_client as llm

        error_context = ctx.extra.get("error_log", "")
        initial = (
            f"Task: {ctx.prompt}\n\n"
            f"Repository context:\n{json.dumps(ctx.repo_context, indent=2)[:2000]}\n\n"
        )
        if error_context:
            initial += f"Error log / failure detail:\n{error_context[:3000]}\n\n"
        initial += "Begin diagnosing. What is your first investigation step?"

        conversation: list[LLMMessage] = [
            LLMMessage(role="system", content=system_prompt),
            LLMMessage(role="user", content=initial),
        ]
        tool_calls_log: list[dict] = []
        files_changed: set[str] = set()
        resp = None

        for iteration in range(1, _MAX_FIX_ITERATIONS + 1):
            self._logger.debug("Fixer iteration %d/%d", iteration, _MAX_FIX_ITERATIONS)
            try:
                resp = llm.chat(conversation, model_class=self.model_class, response_format="json")
                action_data = json.loads(resp.content)
            except (json.JSONDecodeError, Exception) as exc:
                self._logger.warning("Failed to parse fixer response: %s", exc)
                conversation.append(LLMMessage(role="model", content=getattr(resp, "content", "") if resp else ""))
                conversation.append(LLMMessage(role="user", content="Please respond with valid JSON."))
                continue

            action = action_data.get("action", "done")
            params = action_data.get("params", {})

            if action == "done":
                return AgentResult(
                    success=True,
                    output=json.dumps(params, indent=2),
                    tool_calls=tool_calls_log,
                    risk_level=RiskLevel.MEDIUM,
                    metadata={
                        "root_cause": params.get("root_cause", ""),
                        "confidence": params.get("confidence", "MEDIUM"),
                        "files_changed": list(files_changed),
                        "iterations": iteration,
                        "usage": resp.usage,
                    },
                    artifacts=[{"type": "fix_report", "content": json.dumps(params, indent=2)}],
                )

            # Execute tool
            tool_map = {
                "read_file": "read_file",
                "run_command": "run_command",
                "search_code": "search_code",
                "write_file": "write_file",
            }
            tool_name = tool_map.get(action)
            if not tool_name:
                conversation.append(LLMMessage(role="model", content=resp.content))
                conversation.append(LLMMessage(role="user", content=f"Unknown action '{action}'. Use one of: {list(tool_map.keys())} or 'done'."))
                continue

            result = execute_tool(tool_name, sandbox_session_id=ctx.sandbox_session_id, **params)
            tool_calls_log.append({
                "iteration": iteration, "action": action, "params": params,
                "success": result.success,
                "output_preview": result.output[:500] if result.output else "",
                "duration_ms": result.duration_ms,
            })
            if action == "write_file" and result.success:
                files_changed.add(params.get("path", "unknown"))

            conversation.append(LLMMessage(role="model", content=resp.content))
            feedback = f"Result of {action}: success={result.success}\nOutput: {result.output[:3000]}\n"
            if result.error:
                feedback += f"Error: {result.error}\n"
            feedback += "\nWhat is your next step?"
            conversation.append(LLMMessage(role="user", content=feedback))

        return AgentResult(
            success=True,
            output=f"Completed {_MAX_FIX_ITERATIONS} investigation iterations. Files changed: {list(files_changed)}",
            tool_calls=tool_calls_log,
            risk_level=RiskLevel.MEDIUM,
            metadata={"files_changed": list(files_changed), "iterations": _MAX_FIX_ITERATIONS},
        )
