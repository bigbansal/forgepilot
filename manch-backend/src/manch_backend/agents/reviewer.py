"""ReviewerAgent — reviews diffs for maintainability, clarity, and engineering quality."""
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
You are Reviewer, the code review agent for Manch.
You act like a strong senior reviewer who protects long-term code health.

When given a diff and context, you should:
1. Inspect changes for readability and maintainability
2. Detect hidden coupling and unnecessary complexity
3. Check naming, cohesion, and boundary discipline
4. Flag missing tests or weak failure handling
5. Assess whether the implementation matches the design intent

Review lens: correctness, simplicity, operational safety, scalability,
consistency with Manch architecture, observability.

Respond in JSON:
{
  "verdict": "approve" | "request_changes" | "comment",
  "summary": "Overall assessment",
  "blocking_issues": [
    {"file": "path", "line": 42, "severity": "HIGH", "issue": "description", "suggestion": "fix"}
  ],
  "improvements": [
    {"file": "path", "issue": "description", "suggestion": "fix"}
  ],
  "architectural_concerns": ["concern 1"],
  "positive_notes": ["what was done well"],
  "test_coverage_assessment": "Comment on test coverage"
}

Guidelines:
- Do not nitpick style over substance
- Do not request abstractions without real payoff
- Be specific: cite file paths and line numbers
- Provide actionable suggestions, not vague complaints
"""


@register_agent
class ReviewerAgent(BaseAgent):
    name = "reviewer"
    tier = AgentTier.SPECIALIST
    model_class = ModelClass.BALANCED
    parallel_safe = True
    purpose = "Reviews diffs for maintainability, clarity, and engineering quality."

    def run(self, ctx: AgentContext) -> AgentResult:
        self._logger.info("Reviewing changes for task=%s", ctx.task_id)

        system_prompt = self.build_system_prompt() or _SYSTEM_PROMPT
        from manch_backend.agents.llm import llm_client as llm

        # Gather diff context
        diff_output = ""
        if ctx.sandbox_session_id:
            diff_result = execute_tool("git_diff", sandbox_session_id=ctx.sandbox_session_id)
            status_result = execute_tool("git_status", sandbox_session_id=ctx.sandbox_session_id)
            diff_output = (
                f"## Git Status\n{status_result.output[:1000]}\n\n"
                f"## Git Diff\n{diff_result.output[:6000]}\n\n"
            )

        scout_report = ctx.extra.get("scout_report", "")
        review_input = f"Task: {ctx.prompt}\n\n{diff_output}"
        if scout_report:
            review_input += f"## Codebase Context\n{scout_report[:3000]}\n\n"
        review_input += "Review the changes and provide your assessment."

        messages = [
            LLMMessage(role="system", content=system_prompt),
            LLMMessage(role="user", content=review_input),
        ]

        try:
            resp = llm.chat(messages, model_class=self.model_class, response_format="json")
            review = json.loads(resp.content)

            verdict = review.get("verdict", "comment")
            blocking = review.get("blocking_issues", [])
            risk = RiskLevel.HIGH if blocking else RiskLevel.LOW

            return AgentResult(
                success=verdict != "request_changes",
                output=resp.content,
                risk_level=risk,
                metadata={
                    "verdict": verdict,
                    "blocking_count": len(blocking),
                    "improvement_count": len(review.get("improvements", [])),
                    "usage": resp.usage,
                },
                artifacts=[{"type": "code_review", "content": resp.content}],
            )
        except Exception as exc:
            self._logger.exception("Reviewer analysis failed")
            return AgentResult(success=False, output="", error=str(exc))
