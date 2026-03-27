"""MaestroAgent — decomposes user goals into an executable plan and delegates to specialist agents."""
from __future__ import annotations

import json
import logging

from forgepilot_backend.agents.base import AgentContext, AgentResult, BaseAgent
from forgepilot_backend.agents.llm import LLMMessage
from forgepilot_backend.agents.registry import register_agent
from forgepilot_backend.models import AgentTier, ModelClass, RiskLevel

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """\
You are Maestro, the conductor agent for ForgePilot.
Your job is to decompose a user's goal into a structured execution plan using the available agents.

Available agents:
- guardian: Evaluates risk of operations. Use before any potentially dangerous step.
- scout: Explores the codebase, finds relevant files, understands project structure.
- coder: Makes code changes — writes, edits, and creates files.
- sentinel: Validates changes — runs tests, lint, type checks.

Standard workflow pattern:
1. scout — Explore and understand the codebase
2. guardian — Assess risk of the planned changes
3. coder — Implement the changes
4. sentinel — Validate the result

You may skip or reorder steps based on the task. For simple read-only tasks, you might only
need scout. For risky operations, always include guardian before coder.

Respond with a JSON plan:
{
  "title": "Short title for this task",
  "analysis": "Your analysis of what needs to be done",
  "steps": [
    {
      "order": 1,
      "agent": "scout",
      "description": "What this step should accomplish",
      "depends_on": [],
      "input_context": "Any specific instructions for this agent"
    },
    {
      "order": 2,
      "agent": "guardian",
      "description": "Assess risk of the planned changes",
      "depends_on": [1],
      "input_context": "Evaluate the risk of modifying ..."
    }
  ],
  "estimated_risk": "LOW" | "MEDIUM" | "HIGH" | "CRITICAL"
}

Guidelines:
- Keep plans concise — typically 2-5 steps
- Always start with scout for non-trivial tasks
- Always end with sentinel for code changes
- Include guardian for medium+ risk operations
- Each step should have a clear, specific description
"""


@register_agent
class MaestroAgent(BaseAgent):
    name = "maestro"
    tier = AgentTier.CONDUCTOR
    model_class = ModelClass.REASONING
    parallel_safe = False
    purpose = "Decomposes user goals into structured plans and delegates to specialist agents."

    def run(self, ctx: AgentContext) -> AgentResult:
        self._logger.info("Planning task=%s", ctx.task_id)

        system_prompt = self.build_system_prompt() or _SYSTEM_PROMPT
        from forgepilot_backend.agents.llm import llm_client as llm

        messages = [
            LLMMessage(role="system", content=system_prompt),
        ]

        # Include conversation history for context
        for h in ctx.history[-6:]:
            messages.append(LLMMessage(role=h.get("role", "user"), content=h.get("content", "")))

        # Build planning prompt
        plan_prompt = f"Create an execution plan for this task:\n\n{ctx.prompt}"
        if ctx.repo_context:
            plan_prompt += f"\n\nRepository context:\n{json.dumps(ctx.repo_context, indent=2)[:2000]}"
        messages.append(LLMMessage(role="user", content=plan_prompt))

        resp = None  # initialised so except blocks can safely reference it
        try:
            resp = llm.chat(messages, model_class=self.model_class, response_format="json")
            plan_data = json.loads(resp.content)

            # Validate plan structure
            steps = plan_data.get("steps", [])
            if not steps:
                return AgentResult(
                    success=False,
                    output=resp.content,
                    error="Plan contains no steps",
                )

            # Validate agent names
            valid_agents = {"guardian", "scout", "coder", "sentinel", "maestro"}
            for step in steps:
                if step.get("agent") not in valid_agents:
                    self._logger.warning("Plan contains unknown agent: %s", step.get("agent"))

            # Determine risk level
            risk_str = plan_data.get("estimated_risk", "MEDIUM").upper()
            try:
                risk = RiskLevel(risk_str)
            except ValueError:
                risk = RiskLevel.MEDIUM

            return AgentResult(
                success=True,
                output=resp.content,
                risk_level=risk,
                next_agent=steps[0]["agent"] if steps else None,
                metadata={
                    "title": plan_data.get("title", "Untitled"),
                    "analysis": plan_data.get("analysis", ""),
                    "step_count": len(steps),
                    "plan": plan_data,
                    "usage": resp.usage,
                },
                artifacts=[
                    {
                        "type": "execution_plan",
                        "content": resp.content,
                    }
                ],
            )
        except json.JSONDecodeError:
            self._logger.warning("Maestro returned non-JSON, attempting recovery")
            return AgentResult(
                success=False,
                output=resp.content if resp else "",
                error="Failed to parse plan as JSON",
            )
        except Exception as exc:
            self._logger.exception("Maestro planning failed")
            return AgentResult(
                success=False,
                output="",
                error=str(exc),
            )
