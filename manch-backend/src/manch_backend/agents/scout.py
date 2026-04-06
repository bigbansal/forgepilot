"""ScoutAgent — explores repository structure and gathers context."""
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
You are Scout, the exploration agent for Manch.
Your job is to understand the codebase structure and gather context needed for a task.

When given a task, you should:
1. List the project structure to understand the layout
2. Search for relevant files and patterns related to the task
3. Read key files to understand existing code
4. Summarize what you found in a clear, structured report

Output a JSON object:
{
  "summary": "High-level summary of what you found",
  "project_type": "e.g. python-fastapi, angular, monorepo",
  "relevant_files": ["path/to/file1.py", "path/to/file2.ts"],
  "key_findings": ["finding 1", "finding 2"],
  "suggested_approach": "How the coder should approach this task",
  "dependencies": ["any dependencies or prerequisites noticed"]
}
"""


@register_agent
class ScoutAgent(BaseAgent):
    name = "scout"
    tier = AgentTier.SPECIALIST
    model_class = ModelClass.FAST
    parallel_safe = True
    purpose = "Explores the codebase, gathers context, and identifies relevant files for a task."

    def run(self, ctx: AgentContext) -> AgentResult:
        self._logger.info("Scouting repo for task=%s", ctx.task_id)

        if not ctx.sandbox_session_id:
            return AgentResult(
                success=False,
                output="",
                error="No sandbox session available for exploration.",
            )

        # Step 1: List project structure
        tree_result = execute_tool(
            "list_directory",
            sandbox_session_id=ctx.sandbox_session_id,
            path=".",
        )

        # Step 2: Search for patterns related to the prompt
        search_terms = self._extract_search_terms(ctx.prompt)
        search_results = []
        for term in search_terms[:3]:  # limit to 3 searches
            sr = execute_tool(
                "search_code",
                sandbox_session_id=ctx.sandbox_session_id,
                pattern=term,
            )
            if sr.success and sr.output:
                search_results.append({"term": term, "matches": sr.output[:2000]})

        # Step 3: Ask LLM to synthesize findings
        system_prompt = self.build_system_prompt() or _SYSTEM_PROMPT
        from manch_backend.agents.llm import llm_client as llm

        exploration_data = (
            f"## Project Structure\n{tree_result.output[:3000]}\n\n"
            f"## Search Results\n{json.dumps(search_results, indent=2)[:3000]}\n\n"
            f"## Repository Context\n{json.dumps(ctx.repo_context, indent=2)[:1000]}"
        )

        messages = [
            LLMMessage(role="system", content=system_prompt),
            LLMMessage(
                role="user",
                content=(
                    f"Task: {ctx.prompt}\n\n"
                    f"Here is what I found exploring the codebase:\n\n{exploration_data}\n\n"
                    "Analyze the codebase and provide your structured report."
                ),
            ),
        ]

        try:
            resp = llm.chat(messages, model_class=self.model_class, response_format="json")
            report = json.loads(resp.content)

            return AgentResult(
                success=True,
                output=resp.content,
                risk_level=RiskLevel.LOW,
                metadata={
                    "relevant_files": report.get("relevant_files", []),
                    "project_type": report.get("project_type", "unknown"),
                    "usage": resp.usage,
                },
                artifacts=[
                    {
                        "type": "scout_report",
                        "content": resp.content,
                    }
                ],
            )
        except Exception as exc:
            self._logger.exception("Scout exploration failed")
            return AgentResult(
                success=False,
                output="",
                error=str(exc),
            )

    @staticmethod
    def _extract_search_terms(prompt: str) -> list[str]:
        """Extract likely search terms from the user prompt."""
        # Simple heuristic: split on common delimiters, keep meaningful words
        import re

        words = re.findall(r'\b[a-zA-Z_][a-zA-Z0-9_]{2,}\b', prompt)
        # Filter out common English stop words
        stop = {"the", "and", "for", "that", "this", "with", "from", "are", "was", "will",
                "can", "has", "had", "have", "not", "but", "they", "all", "been", "would",
                "could", "should", "into", "about", "than", "its", "also", "just", "add",
                "use", "make", "like", "need", "want", "create", "implement", "update", "fix"}
        meaningful = [w for w in words if w.lower() not in stop]
        # Deduplicate while preserving order
        seen: set[str] = set()
        unique: list[str] = []
        for w in meaningful:
            lw = w.lower()
            if lw not in seen:
                seen.add(lw)
                unique.append(w)
        return unique[:5]
