"""ArchitectAgent — designs systems, contracts, schemas, and change plans."""
from __future__ import annotations

import json
import logging

from manch_backend.agents.base import AgentContext, AgentResult, BaseAgent
from manch_backend.agents.llm import LLMMessage
from manch_backend.agents.registry import register_agent
from manch_backend.agents.tools import execute_tool
from manch_backend.models import AgentTier, ModelClass, RiskLevel

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """\
You are Architect, the systems design agent for Manch.
Your job is to analyze a codebase and produce a structured design plan for proposed changes.

When given a task, you should:
1. Understand the existing architecture from the scout report and repo context
2. Identify affected service boundaries, modules, and data flows
3. Design the change plan with clear API contracts, schema changes, and rollout steps
4. Assess risks and tradeoffs

Respond in JSON:
{
  "design_summary": "High-level description of the design",
  "modules_affected": ["module1", "module2"],
  "api_contracts": [{"endpoint": "/api/v1/...", "method": "POST", "description": "..."}],
  "schema_changes": [{"table": "...", "change": "add column X", "migration_notes": "..."}],
  "rollout_plan": ["step 1", "step 2"],
  "risks": ["risk 1"],
  "tradeoffs": ["tradeoff 1"],
  "estimated_complexity": "LOW" | "MEDIUM" | "HIGH"
}

Guidelines:
- Prefer modular monolith over premature microservices
- Design for extensibility but don't over-engineer
- Specify clear contracts so implementation is unambiguous
- Consider backward compatibility and migration paths
"""


@register_agent
class ArchitectAgent(BaseAgent):
    name = "architect"
    tier = AgentTier.SPECIALIST
    model_class = ModelClass.REASONING
    parallel_safe = True
    purpose = "Designs resilient systems, contracts, schemas, and change plans."

    def run(self, ctx: AgentContext) -> AgentResult:
        self._logger.info("Designing architecture for task=%s", ctx.task_id)

        system_prompt = self.build_system_prompt() or _SYSTEM_PROMPT
        from manch_backend.agents.llm import llm_client as llm

        # Gather context
        scout_report = ctx.extra.get("scout_report", "")
        design_input = f"Task: {ctx.prompt}\n\n"
        if scout_report:
            design_input += f"## Scout Report\n{scout_report[:4000]}\n\n"
        if ctx.repo_context:
            design_input += f"## Repository Context\n{json.dumps(ctx.repo_context, indent=2)[:2000]}\n\n"
        design_input += "Produce your architecture design document."

        messages = [
            LLMMessage(role="system", content=system_prompt),
            LLMMessage(role="user", content=design_input),
        ]

        try:
            resp = llm.chat(messages, model_class=self.model_class, response_format="json")
            design = json.loads(resp.content)

            complexity = design.get("estimated_complexity", "MEDIUM").upper()
            risk_map = {"LOW": RiskLevel.LOW, "MEDIUM": RiskLevel.MEDIUM, "HIGH": RiskLevel.HIGH}
            risk = risk_map.get(complexity, RiskLevel.MEDIUM)

            return AgentResult(
                success=True,
                output=resp.content,
                risk_level=risk,
                metadata={
                    "design_summary": design.get("design_summary", ""),
                    "modules_affected": design.get("modules_affected", []),
                    "estimated_complexity": complexity,
                    "usage": resp.usage,
                },
                artifacts=[{"type": "architecture_design", "content": resp.content}],
            )
        except Exception as exc:
            self._logger.exception("Architect design failed")
            return AgentResult(success=False, output="", error=str(exc))
