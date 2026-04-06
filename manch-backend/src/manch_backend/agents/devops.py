"""DevOpsAgent — builds delivery, environment, and runtime operations capabilities."""
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
You are DevOps, the infrastructure and delivery agent for Manch.
Your job is to create reliable paths to build, run, observe, and ship the platform.

When given a task, you should:
1. Analyze the existing infrastructure (Docker, CI/CD, compose files)
2. Identify gaps or improvements needed
3. Implement infrastructure changes using the sandbox

Respond with a JSON action plan:
{
  "action": "run_command" | "read_file" | "write_file" | "done",
  "params": { ... },
  "reasoning": "Why this step"
}

When action is "done":
{
  "action": "done",
  "params": {
    "summary": "What was accomplished",
    "assets_created": ["Dockerfile", "docker-compose.yml"],
    "deployment_notes": "How to deploy",
    "operational_risks": ["risk 1"]
  }
}

Focus areas:
- Docker and Compose assets
- CI/CD workflows (GitHub Actions)
- Health checks and metrics exposure
- Environment configuration
- Secret management (never hardcode secrets)
"""


@register_agent
class DevOpsAgent(BaseAgent):
    name = "devops"
    tier = AgentTier.SPECIALIST
    model_class = ModelClass.BALANCED
    parallel_safe = True
    purpose = "Builds delivery, environment, and runtime operations capabilities."

    def run(self, ctx: AgentContext) -> AgentResult:
        self._logger.info("DevOps task for task=%s", ctx.task_id)

        system_prompt = self.build_system_prompt() or _SYSTEM_PROMPT
        from manch_backend.agents.llm import llm_client as llm

        # Gather infra context from sandbox
        infra_context = ""
        if ctx.sandbox_session_id:
            compose_result = execute_tool(
                "run_command", sandbox_session_id=ctx.sandbox_session_id,
                command="cat docker-compose.yml 2>/dev/null || echo 'No docker-compose.yml found'",
            )
            dockerfile_result = execute_tool(
                "run_command", sandbox_session_id=ctx.sandbox_session_id,
                command="find . -name 'Dockerfile*' -maxdepth 3 2>/dev/null | head -10",
            )
            ci_result = execute_tool(
                "run_command", sandbox_session_id=ctx.sandbox_session_id,
                command="find . -path './.github/workflows/*.yml' 2>/dev/null | head -10",
            )
            infra_context = (
                f"## docker-compose.yml\n{compose_result.output[:3000]}\n\n"
                f"## Dockerfiles found\n{dockerfile_result.output[:1000]}\n\n"
                f"## CI workflows\n{ci_result.output[:1000]}\n\n"
            )

        scout_report = ctx.extra.get("scout_report", "")
        devops_input = f"Task: {ctx.prompt}\n\n{infra_context}"
        if scout_report:
            devops_input += f"## Scout Report\n{scout_report[:3000]}\n\n"
        devops_input += "Analyze the infrastructure and produce your DevOps plan."

        messages = [
            LLMMessage(role="system", content=system_prompt),
            LLMMessage(role="user", content=devops_input),
        ]

        try:
            resp = llm.chat(messages, model_class=self.model_class, response_format="json")
            plan = json.loads(resp.content)

            return AgentResult(
                success=True,
                output=resp.content,
                risk_level=RiskLevel.MEDIUM,
                metadata={
                    "summary": plan.get("summary", plan.get("params", {}).get("summary", "")),
                    "assets": plan.get("assets_created", plan.get("params", {}).get("assets_created", [])),
                    "usage": resp.usage,
                },
                artifacts=[{"type": "devops_plan", "content": resp.content}],
            )
        except Exception as exc:
            self._logger.exception("DevOps planning failed")
            return AgentResult(success=False, output="", error=str(exc))
