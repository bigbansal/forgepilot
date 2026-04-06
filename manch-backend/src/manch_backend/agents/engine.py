"""Plan execution engine — runs a Maestro-generated plan through the agent pipeline."""
from __future__ import annotations

import json
import logging
from datetime import datetime, UTC
from uuid import uuid4

from sqlalchemy import select

from manch_backend.agents.base import AgentContext, AgentResult
from manch_backend.agents.registry import get_agent
from manch_backend.db.models import (
    ApprovalRequestRecord,
    ArtifactRecord,
    PlanStepRecord,
    TaskRecord,
    ToolExecutionRecord,
)
from manch_backend.db.session import SessionLocal
from manch_backend.models import RiskLevel, StepStatus, TaskStatus
from manch_backend.services.events import event_broker

logger = logging.getLogger(__name__)


class PlanExecutionEngine:
    """Orchestrates execution of a multi-step plan through the agent pipeline.

    Workflow:
    1. Maestro generates a plan (list of steps)
    2. Engine persists the plan to the database
    3. Engine executes each step sequentially via the appropriate agent
    4. Results are recorded and emitted as events
    """

    def __init__(self) -> None:
        self._running = False

    def run_task(
        self,
        task_id: str,
        prompt: str,
        user_id: str | None = None,
        team_id: str | None = None,
        sandbox_session_id: str | None = None,
        repo_context: dict | None = None,
        history: list[dict[str, str]] | None = None,
    ) -> dict:
        """Execute the full agent pipeline for a task.

        Returns a summary dict with plan, results, and final status.
        """
        self._running = True
        repo_context = repo_context or {}
        history = history or []
        summary: dict = {"task_id": task_id, "steps": [], "status": "running"}

        try:
            # Phase 1: Planning — ask Maestro to create a plan
            self._update_task_status(task_id, TaskStatus.PLANNING, user_id)

            maestro_ctx = AgentContext(
                task_id=task_id,
                user_id=user_id,
                team_id=team_id,
                prompt=prompt,
                history=history,
                repo_context=repo_context,
                sandbox_session_id=sandbox_session_id,
            )

            maestro = get_agent("maestro")
            plan_result = maestro.run(maestro_ctx)

            if not plan_result.success:
                self._update_task_status(task_id, TaskStatus.FAILED, user_id)
                summary["status"] = "failed"
                summary["error"] = plan_result.error or "Planning failed"
                return summary

            # Parse and persist the plan
            plan_data = plan_result.metadata.get("plan", {})
            steps = plan_data.get("steps", [])
            plan_step_records = self._persist_plan(task_id, steps)
            summary["plan"] = plan_data

            # Store plan artifact
            self._store_artifact(task_id, None, "execution_plan", plan_result.output)

            self._emit("task.planned", {
                "task_id": task_id,
                "step_count": len(steps),
                "title": plan_data.get("title", ""),
            }, user_id, team_id)

            # Phase 2: Execution — run each step
            self._update_task_status(task_id, TaskStatus.RUNNING, user_id)

            accumulated_context: dict = {
                "scout_report": "",
                "project_type": "default",
                "files_changed": [],
            }

            for i, (step_def, step_record) in enumerate(zip(steps, plan_step_records)):
                if not self._running:
                    logger.info("Execution cancelled for task=%s", task_id)
                    summary["status"] = "cancelled"
                    break

                agent_name = step_def.get("agent", "scout")
                description = step_def.get("description", "")
                input_context = step_def.get("input_context", "")

                logger.info(
                    "Executing step %d/%d: agent=%s desc=%s",
                    i + 1, len(steps), agent_name, description[:60],
                )

                # Update step status
                self._update_step_status(step_record.id, StepStatus.RUNNING)
                self._emit("step.running", {
                    "task_id": task_id,
                    "step_id": step_record.id,
                    "step_index": i + 1,
                    "agent": agent_name,
                    "description": description,
                }, user_id, team_id)

                # Build context for this agent
                step_prompt = f"{prompt}\n\nCurrent step: {description}"
                if input_context:
                    step_prompt += f"\n\nInstructions: {input_context}"

                agent_ctx = AgentContext(
                    task_id=task_id,
                    step_id=step_record.id,
                    user_id=user_id,
                    team_id=team_id,
                    prompt=step_prompt,
                    history=history,
                    repo_context=repo_context,
                    sandbox_session_id=sandbox_session_id,
                    extra=dict(accumulated_context),
                )

                # Execute the agent
                try:
                    agent = get_agent(agent_name)
                    result = agent.run(agent_ctx)
                except Exception as exc:
                    logger.exception("Agent %s failed for step %d", agent_name, i + 1)
                    result = AgentResult(success=False, error=str(exc))

                # Record tool executions
                for tc in result.tool_calls:
                    self._record_tool_execution(task_id, step_record.id, tc)

                # Record artifacts
                for artifact in result.artifacts:
                    self._store_artifact(
                        task_id, step_record.id,
                        artifact.get("type", "unknown"),
                        artifact.get("content", ""),
                    )

                # Update accumulated context
                if agent_name == "scout" and result.success:
                    accumulated_context["scout_report"] = result.output
                    accumulated_context["project_type"] = result.metadata.get("project_type", "default")
                if agent_name == "coder" and result.success:
                    accumulated_context["files_changed"].extend(
                        result.metadata.get("files_changed", [])
                    )

                # Update step status
                step_status = StepStatus.COMPLETED if result.success else StepStatus.FAILED
                self._update_step_status(
                    step_record.id, step_status, result.output[:500]
                )

                step_summary = {
                    "step_index": i + 1,
                    "agent": agent_name,
                    "description": description,
                    "success": result.success,
                    "output_preview": result.output[:300],
                    "risk_level": result.risk_level.value,
                    "error": result.error,
                }
                summary["steps"].append(step_summary)

                self._emit("step.completed", {
                    "task_id": task_id,
                    "step_id": step_record.id,
                    "step_index": i + 1,
                    "agent": agent_name,
                    "success": result.success,
                }, user_id, team_id)

                # Handle approval requirement from Guardian
                if (
                    agent_name == "guardian"
                    and result.metadata.get("requires_approval")
                    and result.risk_level in (RiskLevel.HIGH, RiskLevel.CRITICAL)
                ):
                    approval_id = self._create_approval_request(
                        task_id=task_id,
                        step_id=step_record.id,
                        operation_type=description,
                        risk_level=result.risk_level,
                        reason=result.metadata.get("reason", "Risk assessment requires approval"),
                        paused_step_index=i + 1,
                    )
                    self._update_task_status(task_id, TaskStatus.WAITING_APPROVAL, user_id)
                    self._emit("task.waiting_approval", {
                        "task_id": task_id,
                        "approval_id": approval_id,
                        "risk_level": result.risk_level.value,
                        "reason": result.metadata.get("reason", ""),
                    }, user_id, team_id)
                    summary["status"] = "waiting_approval"
                    summary["approval_id"] = approval_id
                    summary["approval_reason"] = result.metadata.get("reason", "")
                    return summary

                # If a step fails, stop the pipeline
                if not result.success:
                    logger.warning("Step %d failed, aborting plan", i + 1)
                    self._update_task_status(task_id, TaskStatus.FAILED, user_id)
                    summary["status"] = "failed"
                    summary["error"] = result.error or f"Step {i+1} ({agent_name}) failed"
                    return summary

            # Phase 3: Validation complete — mark task as done
            if summary.get("status") != "cancelled":
                self._update_task_status(task_id, TaskStatus.COMPLETED, user_id)
                summary["status"] = "completed"

            return summary

        except Exception as exc:
            logger.exception("Plan execution failed for task=%s", task_id)
            self._update_task_status(task_id, TaskStatus.FAILED, user_id)
            summary["status"] = "failed"
            summary["error"] = str(exc)
            return summary
        finally:
            self._running = False

    def resume_task(
        self,
        task_id: str,
        prompt: str,
        user_id: str | None = None,
        team_id: str | None = None,
        sandbox_session_id: str | None = None,
        start_index: int = 0,
        repo_context: dict | None = None,
        history: list[dict[str, str]] | None = None,
    ) -> dict:
        """Resume execution of an existing plan from *start_index*.

        Called after an approval gate is resolved.  Loads persisted plan
        steps from the DB and continues execution from the given index.
        """
        self._running = True
        repo_context = repo_context or {}
        history = history or []
        summary: dict = {"task_id": task_id, "steps": [], "status": "running"}

        try:
            # Load existing plan steps for this task
            with SessionLocal() as db:
                step_records = (
                    db.execute(
                        select(PlanStepRecord)
                        .where(PlanStepRecord.task_id == task_id)
                        .order_by(PlanStepRecord.order_index)
                    )
                    .scalars()
                    .all()
                )
                if not step_records:
                    summary["status"] = "failed"
                    summary["error"] = "No plan steps found — cannot resume"
                    return summary

                # Rebuild step definitions from persisted records
                steps = [
                    {
                        "agent": s.agent_name,
                        "description": s.description or "",
                        "order": s.order_index,
                        "input_context": "",
                    }
                    for s in step_records
                ]
                plan_step_records = list(step_records)

            # Mark task as running again
            self._update_task_status(task_id, TaskStatus.RUNNING, user_id)
            self._emit("task.resumed", {
                "task_id": task_id,
                "start_index": start_index,
            }, user_id, team_id)

            accumulated_context: dict = {
                "scout_report": "",
                "project_type": "default",
                "files_changed": [],
            }

            for i, (step_def, step_record) in enumerate(zip(steps, plan_step_records)):
                # Skip steps before start_index — they already ran
                if i < start_index:
                    continue

                if not self._running:
                    logger.info("Execution cancelled for task=%s", task_id)
                    summary["status"] = "cancelled"
                    break

                agent_name = step_def.get("agent", "scout")
                description = step_def.get("description", "")
                input_context = step_def.get("input_context", "")

                logger.info(
                    "Resuming step %d/%d: agent=%s desc=%s",
                    i + 1, len(steps), agent_name, description[:60],
                )

                self._update_step_status(step_record.id, StepStatus.RUNNING)
                self._emit("step.running", {
                    "task_id": task_id,
                    "step_id": step_record.id,
                    "step_index": i + 1,
                    "agent": agent_name,
                    "description": description,
                }, user_id, team_id)

                step_prompt = f"{prompt}\n\nCurrent step: {description}"
                if input_context:
                    step_prompt += f"\n\nInstructions: {input_context}"

                agent_ctx = AgentContext(
                    task_id=task_id,
                    step_id=step_record.id,
                    user_id=user_id,
                    team_id=team_id,
                    prompt=step_prompt,
                    history=history,
                    repo_context=repo_context,
                    sandbox_session_id=sandbox_session_id,
                    extra=dict(accumulated_context),
                )

                try:
                    agent = get_agent(agent_name)
                    result = agent.run(agent_ctx)
                except Exception as exc:
                    logger.exception("Agent %s failed for step %d", agent_name, i + 1)
                    result = AgentResult(success=False, error=str(exc))

                for tc in result.tool_calls:
                    self._record_tool_execution(task_id, step_record.id, tc)

                for artifact in result.artifacts:
                    self._store_artifact(
                        task_id, step_record.id,
                        artifact.get("type", "unknown"),
                        artifact.get("content", ""),
                    )

                if agent_name == "scout" and result.success:
                    accumulated_context["scout_report"] = result.output
                    accumulated_context["project_type"] = result.metadata.get("project_type", "default")
                if agent_name == "coder" and result.success:
                    accumulated_context["files_changed"].extend(
                        result.metadata.get("files_changed", [])
                    )

                step_status = StepStatus.COMPLETED if result.success else StepStatus.FAILED
                self._update_step_status(step_record.id, step_status, result.output[:500])

                step_summary = {
                    "step_index": i + 1,
                    "agent": agent_name,
                    "description": description,
                    "success": result.success,
                    "output_preview": result.output[:300],
                    "risk_level": result.risk_level.value,
                    "error": result.error,
                }
                summary["steps"].append(step_summary)

                self._emit("step.completed", {
                    "task_id": task_id,
                    "step_id": step_record.id,
                    "step_index": i + 1,
                    "agent": agent_name,
                    "success": result.success,
                }, user_id, team_id)

                if not result.success:
                    logger.warning("Step %d failed, aborting plan", i + 1)
                    self._update_task_status(task_id, TaskStatus.FAILED, user_id)
                    summary["status"] = "failed"
                    summary["error"] = result.error or f"Step {i+1} ({agent_name}) failed"
                    return summary

            if summary.get("status") != "cancelled":
                self._update_task_status(task_id, TaskStatus.COMPLETED, user_id)
                summary["status"] = "completed"

            return summary

        except Exception as exc:
            logger.exception("Resumed plan execution failed for task=%s", task_id)
            self._update_task_status(task_id, TaskStatus.FAILED, user_id)
            summary["status"] = "failed"
            summary["error"] = str(exc)
            return summary
        finally:
            self._running = False

    def cancel(self) -> None:
        """Signal the engine to stop after the current step."""
        self._running = False

    # ── Database helpers ──────────────────────────────

    @staticmethod
    def _update_task_status(task_id: str, status: TaskStatus, user_id: str | None = None) -> None:
        with SessionLocal() as db:
            record = db.get(TaskRecord, task_id)
            if record:
                record.status = status.value
                record.updated_at = datetime.now(UTC)
                db.commit()

    @staticmethod
    def _persist_plan(task_id: str, steps: list[dict]) -> list[PlanStepRecord]:
        """Save plan steps to the database."""
        records = []
        with SessionLocal() as db:
            for dstep in steps:
                record = PlanStepRecord(
                    id=str(uuid4()),
                    task_id=task_id,
                    order_index=dstep.get("order", 0),
                    agent_name=dstep.get("agent", "unknown"),
                    description=dstep.get("description", ""),
                    status=StepStatus.PENDING.value,
                )
                db.add(record)
                records.append(record)
            db.commit()
            for r in records:
                db.refresh(r)
        return records

    @staticmethod
    def _update_step_status(
        step_id: str, status: StepStatus, output_summary: str | None = None
    ) -> None:
        with SessionLocal() as db:
            record = db.get(PlanStepRecord, step_id)
            if record:
                record.status = status.value
                if output_summary:
                    record.output_summary = output_summary[:2000]
                if status == StepStatus.RUNNING:
                    record.started_at = datetime.now(UTC)
                elif status in (StepStatus.COMPLETED, StepStatus.FAILED):
                    record.finished_at = datetime.now(UTC)
                db.commit()

    @staticmethod
    def _record_tool_execution(task_id: str, step_id: str, tool_call: dict) -> None:
        with SessionLocal() as db:
            record = ToolExecutionRecord(
                id=str(uuid4()),
                task_id=task_id,
                step_id=step_id,
                tool_name=tool_call.get("action", "unknown"),
                input_summary=json.dumps(tool_call.get("params", {}))[:500],
                output_summary=tool_call.get("output_preview", "")[:500],
                result_status="success" if tool_call.get("success") else "failed",
                duration_ms=tool_call.get("duration_ms", 0),
            )
            db.add(record)
            db.commit()

    @staticmethod
    def _store_artifact(
        task_id: str, step_id: str | None, artifact_type: str, content: str
    ) -> None:
        with SessionLocal() as db:
            record = ArtifactRecord(
                id=str(uuid4()),
                task_id=task_id,
                step_id=step_id,
                artifact_type=artifact_type,
                content=content[:10000],
            )
            db.add(record)
            db.commit()

    @staticmethod
    def _create_approval_request(
        task_id: str,
        step_id: str,
        operation_type: str,
        risk_level: RiskLevel,
        reason: str,
        paused_step_index: int | None = None,
    ) -> str:
        """Create an approval request record and return its id."""
        approval_id = str(uuid4())
        with SessionLocal() as db:
            record = ApprovalRequestRecord(
                id=approval_id,
                task_id=task_id,
                step_id=step_id,
                operation_type=operation_type,
                risk_level=risk_level.value,
                reason=reason[:2000],
                paused_step_index=paused_step_index,
            )
            db.add(record)
            db.commit()
        return approval_id

    @staticmethod
    def _emit(event: str, data: dict, user_id: str | None = None, team_id: str | None = None) -> None:
        import asyncio

        try:
            loop = asyncio.get_running_loop()
            loop.create_task(event_broker.publish(event, data, user_id=user_id, team_id=team_id))
        except RuntimeError:
            # Called from a background thread — use the registered main loop
            event_broker.publish_threadsafe(event, data, user_id=user_id, team_id=team_id)
