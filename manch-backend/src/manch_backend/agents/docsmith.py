"""DocSmithAgent — keeps product, API, and operator documentation current and useful."""
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
You are DocSmith, the documentation agent for Manch.
Your job is to ensure the platform remains understandable to builders, operators, and future agents.

When given a task, you should:
1. Survey existing documentation (READMEs, inline docs, API specs)
2. Identify gaps or outdated content
3. Write or update documentation artifacts

Respond with a JSON action plan:
{
  "action": "read_file" | "run_command" | "write_file" | "search_code" | "done",
  "params": { ... },
  "reasoning": "Why this step"
}

When action is "done":
{
  "action": "done",
  "params": {
    "summary": "What documentation was created/updated",
    "artifacts": ["README.md", "docs/api.md"],
    "gaps_remaining": ["areas still needing docs"],
    "audience": "developers | operators | both"
  }
}

Documentation priorities:
1. How the system works
2. How to run it
3. How to operate it safely
4. How to extend it
5. What changed and why

Guidelines:
- Be concise — avoid fluff
- Don't repeat code line-by-line
- Focus on why, not just what
- Keep it actionable
"""


@register_agent
class DocSmithAgent(BaseAgent):
    name = "docsmith"
    tier = AgentTier.SPECIALIST
    model_class = ModelClass.BALANCED
    parallel_safe = True
    purpose = "Keeps product, API, and operator documentation current and useful."

    def run(self, ctx: AgentContext) -> AgentResult:
        self._logger.info("Documentation task for task=%s", ctx.task_id)

        system_prompt = self.build_system_prompt() or _SYSTEM_PROMPT
        from manch_backend.agents.llm import llm_client as llm

        # Gather existing docs
        docs_context = ""
        if ctx.sandbox_session_id:
            readme_result = execute_tool(
                "run_command", sandbox_session_id=ctx.sandbox_session_id,
                command="find . -name 'README.md' -maxdepth 3 2>/dev/null | head -10",
            )
            doc_dir_result = execute_tool(
                "run_command", sandbox_session_id=ctx.sandbox_session_id,
                command="find . -path '*/docs/*' -name '*.md' -maxdepth 4 2>/dev/null | head -20",
            )
            docs_context = (
                f"## README files\n{readme_result.output[:1000]}\n\n"
                f"## Docs directory\n{doc_dir_result.output[:1000]}\n\n"
            )

        scout_report = ctx.extra.get("scout_report", "")
        doc_input = f"Task: {ctx.prompt}\n\n{docs_context}"
        if scout_report:
            doc_input += f"## Codebase Context\n{scout_report[:3000]}\n\n"
        doc_input += "Analyze documentation needs and produce your plan."

        messages = [
            LLMMessage(role="system", content=system_prompt),
            LLMMessage(role="user", content=doc_input),
        ]

        try:
            resp = llm.chat(messages, model_class=self.model_class, response_format="json")
            plan = json.loads(resp.content)

            return AgentResult(
                success=True,
                output=resp.content,
                risk_level=RiskLevel.LOW,
                metadata={
                    "summary": plan.get("summary", plan.get("params", {}).get("summary", "")),
                    "artifacts": plan.get("artifacts", plan.get("params", {}).get("artifacts", [])),
                    "usage": resp.usage,
                },
                artifacts=[{"type": "documentation_plan", "content": resp.content}],
            )
        except Exception as exc:
            self._logger.exception("DocSmith planning failed")
            return AgentResult(success=False, output="", error=str(exc))
