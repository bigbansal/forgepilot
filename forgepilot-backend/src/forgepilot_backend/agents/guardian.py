"""GuardianAgent — evaluates risk level of planned operations."""
from __future__ import annotations

import json
import logging

from forgepilot_backend.agents.base import AgentContext, AgentResult, BaseAgent
from forgepilot_backend.agents.llm import LLMMessage
from forgepilot_backend.agents.registry import register_agent
from forgepilot_backend.models import AgentTier, ModelClass, RiskLevel

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """\
You are Guardian, the security-and-risk-assessment agent for ForgePilot.
Your job is to evaluate a planned operation and classify its risk level.

Risk levels:
- LOW: read-only operations, code analysis, grepping, listing files
- MEDIUM: code changes within a sandboxed environment, refactoring, renaming
- HIGH: package installation, database migrations, Docker operations, schema changes
- CRITICAL: destructive operations (delete all, drop table), production deployments, secret handling

Respond in JSON:
{
  "risk_level": "LOW" | "MEDIUM" | "HIGH" | "CRITICAL",
  "reason": "brief explanation",
  "requires_approval": true | false,
  "suggested_safeguards": ["list of recommended safeguards"]
}

Only set requires_approval=true for HIGH and CRITICAL operations.
Be conservative — when uncertain, classify one level higher.
"""


@register_agent
class GuardianAgent(BaseAgent):
    name = "guardian"
    tier = AgentTier.SUPPORT
    model_class = ModelClass.FAST
    parallel_safe = True
    purpose = "Evaluates risk level of planned operations and enforces safety policies."

    def run(self, ctx: AgentContext) -> AgentResult:
        self._logger.info("Assessing risk for task=%s", ctx.task_id)

        system_prompt = self.build_system_prompt() or _SYSTEM_PROMPT
        from forgepilot_backend.agents.llm import llm_client as llm

        messages = [
            LLMMessage(role="system", content=system_prompt),
        ]

        # Include history for additional context
        for h in ctx.history[-4:]:
            messages.append(LLMMessage(role=h.get("role", "user"), content=h.get("content", "")))

        # The prompt to evaluate
        messages.append(LLMMessage(role="user", content=f"Evaluate the risk of this operation:\n\n{ctx.prompt}"))

        try:
            resp = llm.chat(messages, model_class=self.model_class, response_format="json")
            assessment = json.loads(resp.content)

            risk_str = assessment.get("risk_level", "MEDIUM").upper()
            try:
                risk = RiskLevel(risk_str)
            except ValueError:
                risk = RiskLevel.MEDIUM

            return AgentResult(
                success=True,
                output=resp.content,
                risk_level=risk,
                metadata={
                    "reason": assessment.get("reason", ""),
                    "requires_approval": assessment.get("requires_approval", False),
                    "safeguards": assessment.get("suggested_safeguards", []),
                    "usage": resp.usage,
                },
            )
        except Exception as exc:
            self._logger.exception("Guardian assessment failed")
            return AgentResult(
                success=False,
                output="",
                risk_level=RiskLevel.HIGH,  # fail-safe: assume high risk
                error=str(exc),
            )
