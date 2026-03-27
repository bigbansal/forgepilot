from datetime import datetime, UTC
import shlex
from threading import Thread
from uuid import uuid4
from sqlalchemy import select
from forgepilot_backend.models import Task, Session, TaskStatus, TaskRunner
from forgepilot_backend.db.models import TaskRecord, SessionRecord
from forgepilot_backend.db.session import SessionLocal
from forgepilot_backend.services.policy import PolicyEngine
from forgepilot_backend.services.sandbox import OpenSandboxAdapter
from forgepilot_backend.services.events import event_broker


class OrchestratorService:
    def __init__(self) -> None:
        self.policy = PolicyEngine()
        self.sandbox = OpenSandboxAdapter()

    def create_task(self, prompt: str, user_id: str | None = None) -> Task:
        task_id = str(uuid4())
        with SessionLocal() as db:
            record = TaskRecord(
                id=task_id,
                prompt=prompt,
                status=TaskStatus.CREATED.value,
                user_id=user_id,
            )
            db.add(record)
            db.commit()
            db.refresh(record)
        task = self._to_task(record)
        self._emit("task.created", {"task_id": task.id, "status": task.status.value}, user_id=user_id)
        return task

    def start_task(
        self,
        task_id: str,
        runner: TaskRunner = TaskRunner.OPENSANDBOX,
        approval_mode: str = "yolo",
        user_id: str | None = None,
    ) -> tuple[Task | None, Session | None, str, dict | None]:
        with SessionLocal() as db:
            record = db.get(TaskRecord, task_id)
            if not record:
                return None, None, "Task not found", None

            # Resolve user_id from stored record if not passed explicitly
            effective_user_id = user_id or record.user_id

            session_record: SessionRecord | None = None

            risk = self.policy.classify_risk(record.prompt)
            if self.policy.requires_approval(risk):
                record.status = TaskStatus.WAITING_APPROVAL.value
                record.updated_at = datetime.now(UTC)
                db.add(record)
                db.commit()
                db.refresh(record)
                updated = self._to_task(record)
                self._emit("task.waiting_approval", {"task_id": task_id, "risk": risk.value}, user_id=effective_user_id)
                return updated, None, f"Approval required (risk={risk.value})", {
                    "risk": risk.value,
                    "runner": runner.value,
                    "stdout": "",
                    "stderr": "Awaiting approval before execution.",
                    "exit_code": 0,
                }

            record.status = TaskStatus.RUNNING.value
            record.updated_at = datetime.now(UTC)
            db.add(record)
            db.commit()
            db.refresh(record)
            self._emit("task.running", {"task_id": task_id}, user_id=effective_user_id)
            try:
                sandbox_session_id = self.sandbox.create_session()
                session_record = SessionRecord(
                    id=str(uuid4()),
                    task_id=task_id,
                    sandbox_session_id=sandbox_session_id,
                    status=TaskStatus.RUNNING.value,
                )
                db.add(session_record)
                db.commit()
                db.refresh(session_record)
                self._emit("session.created", {"task_id": task_id, "session_id": session_record.id}, user_id=effective_user_id)

                command = self._build_command(record.prompt.strip(), runner, approval_mode)

                def _on_stdout(msg: object) -> None:
                    text = getattr(msg, "text", str(msg))
                    if text:
                        self._emit("task.log", {"task_id": task_id, "text": text}, user_id=effective_user_id)

                exec_result = self.sandbox.run_command(
                    sandbox_session_id,
                    command,
                    on_stdout=_on_stdout,
                )
                self._emit(
                    "sandbox.exec",
                    {
                        "task_id": task_id,
                        "session_id": session_record.id,
                        "runner": runner.value,
                        "command": command,
                        "exit_code": exec_result.exit_code,
                        "stdout": exec_result.stdout,
                    },
                    user_id=effective_user_id,
                )

                record.status = TaskStatus.COMPLETED.value
                record.updated_at = datetime.now(UTC)
                session_record.status = TaskStatus.COMPLETED.value
                db.add(record)
                db.add(session_record)
                db.commit()
                db.refresh(record)
                db.refresh(session_record)

                self._emit("task.completed", {"task_id": task_id, "status": TaskStatus.COMPLETED.value}, user_id=effective_user_id)

                return (
                    self._to_task(record),
                    self._to_session(session_record),
                    "Task completed",
                    {
                        "risk": risk.value,
                        "runner": runner.value,
                        "command": command,
                        "stdout": exec_result.stdout,
                        "stderr": exec_result.stderr,
                        "exit_code": exec_result.exit_code,
                    },
                )
            except Exception as exc:  # noqa: BLE001
                record.status = TaskStatus.FAILED.value
                record.updated_at = datetime.now(UTC)
                db.add(record)

                if session_record:
                    session_record.status = TaskStatus.FAILED.value
                    db.add(session_record)

                db.commit()
                db.refresh(record)

                self._emit("task.failed", {"task_id": task_id, "error": str(exc)}, user_id=effective_user_id)

                return (
                    self._to_task(record),
                    self._to_session(session_record) if session_record else None,
                    f"Task failed: {exc}",
                    {
                        "risk": risk.value,
                        "runner": runner.value,
                        "stdout": "",
                        "stderr": str(exc),
                        "exit_code": 1,
                    },
                )

    def get_task(self, task_id: str) -> Task | None:
        with SessionLocal() as db:
            record = db.get(TaskRecord, task_id)
            return self._to_task(record) if record else None

    # ── Phase 2: Agent-based execution ────────────────

    def start_task_v2(
        self,
        task_id: str,
        user_id: str | None = None,
        history: list[dict[str, str]] | None = None,
        conversation_id: str | None = None,
    ) -> tuple[Task | None, str]:
        """Start a task using the Phase 2 agent pipeline (Maestro → agents → validate).

        Returns (task, message). Execution runs in a background thread.
        """
        with SessionLocal() as db:
            record = db.get(TaskRecord, task_id)
            if not record:
                return None, "Task not found"

            effective_user_id = user_id or record.user_id
            prompt = record.prompt

            # Create a persistent sandbox session for the entire pipeline
            try:
                sandbox_session_id = self.sandbox.create_session()
            except Exception as exc:
                return self._to_task(record), f"Failed to create sandbox: {exc}"

            session_record = SessionRecord(
                id=str(uuid4()),
                task_id=task_id,
                sandbox_session_id=sandbox_session_id,
                status=TaskStatus.RUNNING.value,
            )
            db.add(session_record)
            db.commit()
            db.refresh(session_record)

        self._emit("task.agent_start", {"task_id": task_id}, user_id=effective_user_id)

        # Run the agent pipeline in a background thread
        def _run_pipeline() -> None:
            from forgepilot_backend.agents.engine import PlanExecutionEngine
            engine = PlanExecutionEngine()
            result: dict = {}
            try:
                result = engine.run_task(
                    task_id=task_id,
                    prompt=prompt,
                    user_id=effective_user_id,
                    sandbox_session_id=sandbox_session_id,
                    history=history or [],
                )
                self._emit("task.agent_done", {
                    "task_id": task_id,
                    "status": result.get("status", "unknown"),
                    "step_count": len(result.get("steps", [])),
                }, user_id=effective_user_id)
            except Exception as exc:
                result = {"status": "failed", "error": str(exc), "steps": []}
                self._emit("task.agent_error", {
                    "task_id": task_id,
                    "error": str(exc),
                }, user_id=effective_user_id)
            finally:
                # Post final result message to the conversation
                self._post_pipeline_result(conversation_id, task_id, result)
                # Clean up the sandbox session
                try:
                    self.sandbox.destroy_session(sandbox_session_id)
                except Exception:
                    pass

        thread = Thread(target=_run_pipeline, daemon=True)
        thread.start()

        with SessionLocal() as db:
            record = db.get(TaskRecord, task_id)
            return self._to_task(record) if record else None, "Agent pipeline started"

    def list_tasks(self, user_id: str | None = None) -> list[Task]:
        with SessionLocal() as db:
            query = select(TaskRecord).order_by(TaskRecord.created_at.desc())
            if user_id is not None:
                query = query.where(TaskRecord.user_id == user_id)
            rows = db.execute(query).scalars().all()
            return [self._to_task(row) for row in rows]

    def list_sessions(self) -> list[Session]:
        with SessionLocal() as db:
            rows = db.execute(select(SessionRecord).order_by(SessionRecord.created_at.desc())).scalars().all()
            return [self._to_session(row) for row in rows]

    @staticmethod
    def _to_task(record: TaskRecord) -> Task:
        return Task(
            id=record.id,
            prompt=record.prompt,
            title=record.title,
            status=TaskStatus(record.status),
            priority=record.priority,
            created_at=record.created_at,
            updated_at=record.updated_at,
        )

    @staticmethod
    def _to_session(record: SessionRecord) -> Session:
        return Session(
            id=record.id,
            task_id=record.task_id,
            sandbox_session_id=record.sandbox_session_id,
            repo_url=record.repo_url,
            branch=record.branch,
            working_directory=record.working_directory,
            status=TaskStatus(record.status),
            created_at=record.created_at,
        )

    @staticmethod
    def _post_pipeline_result(
        conversation_id: str | None, task_id: str, result: dict
    ) -> None:
        """Post a final assistant message with the pipeline outcome to the conversation."""
        if not conversation_id:
            return
        from forgepilot_backend.db.models import ChatMessageRecord, ConversationRecord

        status = result.get("status", "unknown")
        steps = result.get("steps", [])
        error = result.get("error")

        lines = [f"**Pipeline {status}** — {len(steps)} step(s) executed."]
        for s in steps:
            icon = "✅" if s.get("success") else "❌"
            lines.append(f"{icon} Step {s.get('step_index')}: **{s.get('agent')}** — {s.get('description', '')[:80]}")
            if s.get("output_preview"):
                lines.append(f"  _{s['output_preview'][:200]}_")
        if error:
            lines.append(f"\n**Error**: {error}")

        content = "\n".join(lines)

        try:
            with SessionLocal() as db:
                msg = ChatMessageRecord(
                    id=str(uuid4()),
                    conversation_id=conversation_id,
                    role="assistant",
                    content=content,
                    task_id=task_id,
                    created_at=datetime.now(UTC),
                )
                db.add(msg)
                conv = db.get(ConversationRecord, conversation_id)
                if conv:
                    conv.updated_at = datetime.now(UTC)
                    db.add(conv)
                db.commit()
        except Exception:
            pass  # best-effort; SSE events still carry the info

    @staticmethod
    def _emit(event_type: str, payload: dict, user_id: str | None = None) -> None:
        import asyncio

        try:
            loop = asyncio.get_running_loop()
            loop.create_task(event_broker.publish(event_type, payload, user_id=user_id))
        except RuntimeError:
            # Called from a background thread — use the registered main loop
            event_broker.publish_threadsafe(event_type, payload, user_id=user_id)

    @staticmethod
    def _build_command(prompt: str, runner: TaskRunner, approval_mode: str = "yolo") -> str:
        escaped_prompt = shlex.quote(prompt)
        if approval_mode == "yolo":
            approval_flag = "--yolo"
        else:
            approval_flag = f"--approval-mode {approval_mode}"
        if runner == TaskRunner.GEMINI_CLI or runner == TaskRunner.OPENSANDBOX:
            return f"mkdir -p /root/.gemini && gemini {approval_flag} --prompt {escaped_prompt}"
        if runner == TaskRunner.CODEX_CLI:
            return f"codex-cli exec --skip-git-repo-check --sandbox workspace-write {escaped_prompt}"
        return f"mkdir -p /root/.gemini && gemini {approval_flag} --prompt {escaped_prompt}"


orchestrator = OrchestratorService()
