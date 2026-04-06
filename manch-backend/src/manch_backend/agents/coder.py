"""CoderAgent — generates and applies code changes within the sandbox."""
from __future__ import annotations

import json
import logging

from manch_backend.agents.base import AgentContext, AgentResult, BaseAgent
from manch_backend.agents.llm import LLMMessage
from manch_backend.agents.registry import register_agent
from manch_backend.agents.tools import execute_tool, ToolResult as ToolExecResult
from manch_backend.models import AgentTier, ModelClass, RiskLevel

logger = logging.getLogger(__name__)

_MAX_ITERATIONS = 8

_SYSTEM_PROMPT = """\
You are Coder, the implementation agent for Manch.
Your job is to make code changes in a sandboxed environment to fulfil the user's task.

You work inside a sandbox where you can run commands, read/write files, search code, and apply patches.

For each step, respond with a JSON object describing ONE action to take:
{
  "action": "run_command" | "read_file" | "write_file" | "search_code" | "apply_patch" | "done",
  "params": { ... action-specific parameters ... },
  "reasoning": "Why you're taking this action"
}

Actions:
- run_command: {"command": "shell command"}
- read_file: {"path": "/path/to/file"}
- write_file: {"path": "/path/to/file", "content": "full file content"}
- search_code: {"pattern": "search pattern", "path": "."}
- apply_patch: {"patch": "unified diff content"}
- done: {"summary": "what was accomplished", "files_changed": ["list of files"]}

Guidelines:
- Read relevant files before modifying them
- Make targeted, minimal changes
- Prefer editing existing files over creating new ones when appropriate
- After writing files, verify the change (e.g. run linter or cat the file)
- When done, provide a clear summary of changes
"""


@register_agent
class CoderAgent(BaseAgent):
    name = "coder"
    tier = AgentTier.SPECIALIST
    model_class = ModelClass.BALANCED
    parallel_safe = False
    purpose = "Generates and applies code changes to fulfil tasks within a sandbox."

    def run(self, ctx: AgentContext) -> AgentResult:
        self._logger.info("Coding for task=%s", ctx.task_id)

        if not ctx.sandbox_session_id:
            return AgentResult(
                success=False,
                output="",
                error="No sandbox session available for code changes.",
            )

        system_prompt = self.build_system_prompt() or _SYSTEM_PROMPT
        from manch_backend.agents.llm import llm_client as llm

        # Build initial context from scout report if available
        scout_context = ctx.extra.get("scout_report", "")
        initial_context = (
            f"Task: {ctx.prompt}\n\n"
            f"Repository context:\n{json.dumps(ctx.repo_context, indent=2)[:2000]}\n\n"
        )
        if scout_context:
            initial_context += f"Scout report:\n{scout_context[:3000]}\n\n"

        conversation: list[LLMMessage] = [
            LLMMessage(role="system", content=system_prompt),
            LLMMessage(role="user", content=initial_context + "Begin implementing. What is your first action?"),
        ]

        tool_calls_log: list[dict] = []
        files_changed: set[str] = set()
        resp = None  # initialised so except blocks can safely reference it

        for iteration in range(1, _MAX_ITERATIONS + 1):
            self._logger.debug("Coder iteration %d/%d", iteration, _MAX_ITERATIONS)

            try:
                resp = llm.chat(conversation, model_class=self.model_class, response_format="json")
                action_data = json.loads(resp.content)
            except (json.JSONDecodeError, Exception) as exc:
                self._logger.warning("Failed to parse coder LLM response: %s", exc)
                conversation.append(LLMMessage(role="model", content=getattr(resp, 'content', '') if resp else ""))
                conversation.append(
                    LLMMessage(role="user", content="Please respond with valid JSON as specified.")
                )
                continue

            action = action_data.get("action", "done")
            params = action_data.get("params", {})
            reasoning = action_data.get("reasoning", "")

            self._logger.info("Coder action=%s reasoning=%s", action, reasoning[:80])

            # Terminal action
            if action == "done":
                summary = params.get("summary", "Task completed")
                return AgentResult(
                    success=True,
                    output=summary,
                    tool_calls=tool_calls_log,
                    risk_level=RiskLevel.MEDIUM,
                    metadata={
                        "files_changed": list(files_changed),
                        "iterations": iteration,
                        "usage": resp.usage,
                    },
                )

            # Execute the requested tool action
            tool_result = self._execute_action(
                action, params, ctx.sandbox_session_id
            )
            tool_calls_log.append({
                "iteration": iteration,
                "action": action,
                "params": params,
                "success": tool_result.success,
                "output_preview": tool_result.output[:500] if tool_result.output else "",
                "duration_ms": tool_result.duration_ms,
            })

            if action == "write_file" and tool_result.success:
                files_changed.add(params.get("path", "unknown"))

            # Feed result back to LLM for next step
            conversation.append(LLMMessage(role="model", content=resp.content))
            result_text = (
                f"Result of {action}:\n"
                f"Success: {tool_result.success}\n"
                f"Output: {tool_result.output[:3000]}\n"
            )
            if tool_result.error:
                result_text += f"Error: {tool_result.error}\n"
            result_text += "\nWhat is your next action?"
            conversation.append(LLMMessage(role="user", content=result_text))

        # Exceeded max iterations
        return AgentResult(
            success=True,
            output=f"Completed {_MAX_ITERATIONS} iterations. Files changed: {list(files_changed)}",
            tool_calls=tool_calls_log,
            risk_level=RiskLevel.MEDIUM,
            metadata={"files_changed": list(files_changed), "iterations": _MAX_ITERATIONS},
        )

    @staticmethod
    def _execute_action(action: str, params: dict, sandbox_session_id: str) -> ToolExecResult:
        """Map a coder action to a tool execution."""
        tool_map = {
            "run_command": "run_command",
            "read_file": "read_file",
            "write_file": "write_file",
            "search_code": "search_code",
            "apply_patch": "apply_patch",
        }
        tool_name = tool_map.get(action)
        if not tool_name:
            return ToolExecResult(success=False, error=f"Unknown action: {action}")

        return execute_tool(tool_name, sandbox_session_id=sandbox_session_id, **params)
