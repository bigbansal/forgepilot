from datetime import datetime, UTC
import re
import shlex
from threading import Thread
from uuid import uuid4
from sqlalchemy import select
from manch_backend.models import Task, Session, TaskStatus, TaskRunner
from manch_backend.db.models import TaskRecord, SessionRecord, ApprovalRequestRecord, PortMappingRecord
from manch_backend.db.session import SessionLocal
from manch_backend.config import settings
from manch_backend.services.policy import PolicyEngine
from manch_backend.services.sandbox import OpenSandboxAdapter
from manch_backend.services.state_machine import TaskStateMachine
from manch_backend.services.events import event_broker


class OrchestratorService:
    _sm = TaskStateMachine()

    def __init__(self) -> None:
        self.policy = PolicyEngine()
        self.sandbox = OpenSandboxAdapter()

    # ── State transition helper ──────────────────────

    @staticmethod
    def _transition(record: TaskRecord, target: TaskStatus) -> None:
        """Validate and apply a state transition on *record*.

        Uses ``TaskStateMachine`` to guard invalid transitions.
        On invalid transition the error is logged and the status is
        forced (best-effort) to avoid crashing the task pipeline.
        """
        import logging

        current = TaskStatus(record.status)
        try:
            TaskStateMachine.transition(current, target)
        except Exception:
            logging.getLogger(__name__).warning(
                "Invalid transition %s → %s for task %s — rejecting.",
                current.value, target.value, record.id,
            )
            return  # reject invalid transitions instead of forcing
        record.status = target.value
        record.updated_at = datetime.now(UTC)

    def create_task(
        self,
        prompt: str,
        user_id: str | None = None,
        team_id: str | None = None,
        conversation_id: str | None = None,
        repo_id: str | None = None,
    ) -> Task:
        task_id = str(uuid4())
        with SessionLocal() as db:
            record = TaskRecord(
                id=task_id,
                prompt=prompt,
                status=TaskStatus.CREATED.value,
                user_id=user_id,
                team_id=team_id,
                conversation_id=conversation_id,
                repo_id=repo_id,
            )
            db.add(record)
            db.commit()
            db.refresh(record)
        task = self._to_task(record)
        self._emit("task.created", {"task_id": task.id, "status": task.status.value}, user_id=user_id, team_id=team_id)
        return task

    def start_task(
        self,
        task_id: str,
        runner: TaskRunner = TaskRunner.OPENSANDBOX,
        approval_mode: str = "yolo",
        user_id: str | None = None,
        team_id: str | None = None,
        skip_approval: bool = False,
    ) -> tuple[Task | None, Session | None, str, dict | None]:
        with SessionLocal() as db:
            record = db.get(TaskRecord, task_id)
            if not record:
                return None, None, "Task not found", None

            # Resolve user_id from stored record if not passed explicitly
            effective_user_id = user_id or record.user_id
            effective_team_id = team_id or record.team_id

            session_record: SessionRecord | None = None

            risk = self.policy.classify_risk(record.prompt)
            if not skip_approval and self.policy.requires_approval(risk):
                approval_reason = f"Prompt classified as {risk.value} risk and requires manual approval before execution."
                approval_id = str(uuid4())
                approval = ApprovalRequestRecord(
                    id=approval_id,
                    task_id=task_id,
                    step_id=None,
                    operation_type=f"task_start:{runner.value}",
                    risk_level=risk.value,
                    reason=approval_reason,
                    paused_step_index=0,
                )
                db.add(approval)
                self._transition(record, TaskStatus.WAITING_APPROVAL)
                db.add(record)
                db.commit()
                db.refresh(record)
                updated = self._to_task(record)
                self._emit("task.waiting_approval", {
                    "task_id": task_id,
                    "approval_id": approval_id,
                    "risk_level": risk.value,
                    "reason": approval_reason,
                }, user_id=effective_user_id, team_id=effective_team_id)
                return updated, None, f"Approval required (risk={risk.value})", {
                    "risk": risk.value,
                    "approval_id": approval_id,
                    "reason": approval_reason,
                    "runner": runner.value,
                    "stdout": "",
                    "stderr": "Awaiting approval before execution.",
                    "exit_code": 0,
                }

            self._transition(record, TaskStatus.RUNNING)
            db.add(record)
            db.commit()
            db.refresh(record)
            self._emit("task.running", {"task_id": task_id}, user_id=effective_user_id, team_id=effective_team_id)
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
                self._emit("session.created", {"task_id": task_id, "session_id": session_record.id}, user_id=effective_user_id, team_id=effective_team_id)

                command = self._build_command(record.prompt.strip(), runner, approval_mode)

                def _on_stdout(msg: object) -> None:
                    text = getattr(msg, "text", str(msg))
                    if text:
                        self._emit("task.log", {"task_id": task_id, "text": text}, user_id=effective_user_id, team_id=effective_team_id)

                exec_result = self.sandbox.run_command(
                    sandbox_session_id,
                    command,
                    on_stdout=_on_stdout,
                    keep_alive=True,  # Keep sandbox alive so background processes (servers, etc.) keep running
                )

                # Clean preview URL — hides sandbox session IDs from the user.
                # Pattern: http://localhost:8080/api/v1/preview/{port}
                preview_base = f"http://localhost:{settings.port}{settings.api_prefix}/preview"

                # Also keep the full opensandbox proxy base for internal metadata
                public_proxy_base = (
                    f"{settings.opensandbox_public_url}/sandboxes/{sandbox_session_id}/proxy"
                )

                # Replace internal opensandbox URLs in agent stdout with the
                # clean preview URL so users see simple, clickable links.
                agent_stdout = exec_result.stdout
                internal_proxy = f"{settings.opensandbox_base_url.rstrip('/')}/sandboxes/{sandbox_session_id}/proxy"
                public_proxy = f"{settings.opensandbox_public_url.rstrip('/')}/sandboxes/{sandbox_session_id}/proxy"
                # Replace internal URL → preview URL
                agent_stdout = agent_stdout.replace(internal_proxy, preview_base)
                # Replace any remaining public opensandbox URL → preview URL
                agent_stdout = agent_stdout.replace(public_proxy, preview_base)

                self._emit(
                    "sandbox.exec",
                    {
                        "task_id": task_id,
                        "session_id": session_record.id,
                        "sandbox_session_id": sandbox_session_id,
                        "proxy_base": public_proxy_base,
                        "runner": runner.value,
                        "command": command,
                        "exit_code": exec_result.exit_code,
                        "stdout": agent_stdout,
                    },
                    user_id=effective_user_id,
                    team_id=effective_team_id,
                )

                self._transition(record, TaskStatus.COMPLETED)
                session_record.status = TaskStatus.COMPLETED.value
                db.add(record)
                db.add(session_record)
                db.commit()
                db.refresh(record)
                db.refresh(session_record)

                self._emit("task.completed", {"task_id": task_id, "status": TaskStatus.COMPLETED.value}, user_id=effective_user_id, team_id=effective_team_id)

                # Extract port numbers mentioned in the agent output (e.g. "port 3000", ":8080", "on port 8554")
                detected_ports = list(dict.fromkeys(
                    re.findall(r'(?:(?:port|PORT)\s+(\d{2,5})|(?<![\w:]):(\d{2,5})(?![\d]))', exec_result.stdout)
                ))
                # findall returns tuples; flatten and filter empty strings
                flat_ports = [p for pair in detected_ports for p in pair if p]
                # Deduplicate while preserving order
                seen: set[str] = set()
                unique_ports = [p for p in flat_ports if not (p in seen or seen.add(p))]

                # When the agent shell exits, any background servers it started
                # are killed (SIGHUP). Re-launch them with nohup so they survive.
                if unique_ports:
                    self._restart_sandbox_servers(sandbox_session_id, unique_ports)

                # Persist port → sandbox mappings so the preview proxy can
                # route /preview/{port} to the correct sandbox automatically.
                if unique_ports:
                    self._record_port_mappings(
                        db, sandbox_session_id, task_id, unique_ports,
                    )

                if unique_ports:
                    port_links = "\n".join(
                        f"  - {preview_base}/{p}" for p in unique_ports
                    )
                    proxy_note = (
                        f"\n\n---\n"
                        f"App access:\n{port_links}\n"
                        f"(Sandbox stays alive for up to 30 minutes after task completion)"
                    )
                else:
                    proxy_note = (
                        f"\n\n---\n"
                        f"Preview: `{preview_base}/<port>`\n"
                        f"(Sandbox stays alive for up to 30 minutes after task completion)"
                    )
                return (
                    self._to_task(record),
                    self._to_session(session_record),
                    "Task completed",
                    {
                        "risk": risk.value,
                        "runner": runner.value,
                        "command": command,
                        "sandbox_session_id": sandbox_session_id,
                        "proxy_base": public_proxy_base,
                        "stdout": agent_stdout + proxy_note,
                        "stderr": exec_result.stderr,
                        "exit_code": exec_result.exit_code,
                    },
                )
            except Exception as exc:  # noqa: BLE001
                self._transition(record, TaskStatus.FAILED)
                db.add(record)

                if session_record:
                    session_record.status = TaskStatus.FAILED.value
                    db.add(session_record)

                db.commit()
                db.refresh(record)

                self._emit("task.failed", {"task_id": task_id, "error": str(exc)}, user_id=effective_user_id, team_id=effective_team_id)

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

    def resume_direct_task(
        self,
        task_id: str,
        runner: TaskRunner = TaskRunner.OPENSANDBOX,
        user_id: str | None = None,
        team_id: str | None = None,
    ) -> tuple[Task | None, str]:
        """Resume a direct sandbox task after manual approval.

        Re-runs ``start_task`` with approval bypassed exactly once.
        """
        with SessionLocal() as db:
            record = db.get(TaskRecord, task_id)
            if not record:
                return None, "Task not found"
            effective_user_id = user_id or record.user_id
            effective_team_id = team_id or record.team_id
            conversation_id = record.conversation_id

        self._emit("task.running", {"task_id": task_id}, user_id=effective_user_id, team_id=effective_team_id)

        def _run_direct_resume() -> None:
            task_result: Task | None = None
            message = ""
            output: dict | None = None
            try:
                task_result, _session, message, output = self.start_task(
                    task_id=task_id,
                    runner=runner,
                    approval_mode="yolo",
                    user_id=effective_user_id,
                    team_id=effective_team_id,
                    skip_approval=True,
                )
            finally:
                self._post_direct_result(
                    conversation_id,
                    task_result.id if task_result else task_id,
                    message,
                    output,
                )

        thread = Thread(target=_run_direct_resume, daemon=True)
        thread.start()

        with SessionLocal() as db:
            record = db.get(TaskRecord, task_id)
            return self._to_task(record) if record else None, "Direct task resumed"

    def get_task(self, task_id: str) -> Task | None:
        with SessionLocal() as db:
            record = db.get(TaskRecord, task_id)
            return self._to_task(record) if record else None

    # ── Phase 2: Agent-based execution ────────────────

    def start_task_v2(
        self,
        task_id: str,
        user_id: str | None = None,
        team_id: str | None = None,
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
            effective_team_id = team_id or record.team_id
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

        self._emit("task.agent_start", {"task_id": task_id}, user_id=effective_user_id, team_id=effective_team_id)

        # Run the agent pipeline in a background thread
        def _run_pipeline() -> None:
            from manch_backend.agents.engine import PlanExecutionEngine
            engine = PlanExecutionEngine()
            result: dict = {}
            try:
                result = engine.run_task(
                    task_id=task_id,
                    prompt=prompt,
                    user_id=effective_user_id,
                    team_id=effective_team_id,
                    sandbox_session_id=sandbox_session_id,
                    history=history or [],
                )
                self._emit("task.agent_done", {
                    "task_id": task_id,
                    "status": result.get("status", "unknown"),
                    "step_count": len(result.get("steps", [])),
                }, user_id=effective_user_id, team_id=effective_team_id)
            except Exception as exc:
                result = {"status": "failed", "error": str(exc), "steps": []}
                self._emit("task.agent_error", {
                    "task_id": task_id,
                    "error": str(exc),
                }, user_id=effective_user_id, team_id=effective_team_id)
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

    def list_tasks(self, user_id: str | None = None, team_id: str | None = None) -> list[Task]:
        with SessionLocal() as db:
            query = select(TaskRecord).order_by(TaskRecord.created_at.desc())
            if team_id is not None:
                query = query.where(TaskRecord.team_id == team_id)
            elif user_id is not None:
                query = query.where(TaskRecord.user_id == user_id)
            rows = db.execute(query).scalars().all()
            return [self._to_task(row) for row in rows]

    # ── Phase 3: Resume & cancel ─────────────────────

    def resume_task_v2(
        self,
        task_id: str,
        user_id: str | None = None,
        team_id: str | None = None,
        start_index: int = 0,
    ) -> tuple[Task | None, str]:
        """Resume a task from *start_index* after approval.

        Looks up the existing sandbox session and calls engine.resume_task().
        """
        with SessionLocal() as db:
            record = db.get(TaskRecord, task_id)
            if not record:
                return None, "Task not found"

            effective_user_id = user_id or record.user_id
            effective_team_id = team_id or record.team_id
            prompt = record.prompt

            # Find the sandbox session that was used before the pause
            session_record = db.execute(
                select(SessionRecord)
                .where(SessionRecord.task_id == task_id)
                .order_by(SessionRecord.created_at.desc())
            ).scalars().first()

            if not session_record:
                # Need a fresh sandbox
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
            else:
                sandbox_session_id = session_record.sandbox_session_id

        self._emit("task.agent_resume", {
            "task_id": task_id,
            "start_index": start_index,
        }, user_id=effective_user_id, team_id=effective_team_id)

        def _run_resume() -> None:
            from manch_backend.agents.engine import PlanExecutionEngine
            engine = PlanExecutionEngine()
            result: dict = {}
            try:
                result = engine.resume_task(
                    task_id=task_id,
                    prompt=prompt,
                    user_id=effective_user_id,
                    team_id=effective_team_id,
                    sandbox_session_id=sandbox_session_id,
                    start_index=start_index,
                )
                self._emit("task.agent_done", {
                    "task_id": task_id,
                    "status": result.get("status", "unknown"),
                    "step_count": len(result.get("steps", [])),
                }, user_id=effective_user_id, team_id=effective_team_id)
            except Exception as exc:
                result = {"status": "failed", "error": str(exc), "steps": []}
                self._emit("task.agent_error", {
                    "task_id": task_id,
                    "error": str(exc),
                }, user_id=effective_user_id, team_id=effective_team_id)
            finally:
                # Lookup conversation_id from the task record
                conv_id: str | None = None
                try:
                    with SessionLocal() as db:
                        rec = db.get(TaskRecord, task_id)
                        conv_id = rec.conversation_id if rec else None
                except Exception:
                    pass
                self._post_pipeline_result(conv_id, task_id, result)

        thread = Thread(target=_run_resume, daemon=True)
        thread.start()

        with SessionLocal() as db:
            record = db.get(TaskRecord, task_id)
            return self._to_task(record) if record else None, "Agent pipeline resumed"

    def cancel_task(
        self,
        task_id: str,
        user_id: str | None = None,
        team_id: str | None = None,
        reason: str = "Cancelled",
    ) -> Task | None:
        """Cancel a task and post a rejection message."""
        with SessionLocal() as db:
            record = db.get(TaskRecord, task_id)
            if not record:
                return None
            self._transition(record, TaskStatus.CANCELLED)
            db.add(record)
            db.commit()
            db.refresh(record)
            effective_user_id = user_id or record.user_id
            effective_team_id = team_id or record.team_id

        self._emit("task.failed", {
            "task_id": task_id,
            "status": TaskStatus.CANCELLED.value,
            "reason": reason,
        }, user_id=effective_user_id, team_id=effective_team_id)

        # Post rejection message to conversation
        conv_id: str | None = None
        with SessionLocal() as db:
            rec = db.get(TaskRecord, task_id)
            conv_id = rec.conversation_id if rec else None
        if conv_id:
            self._post_pipeline_result(conv_id, task_id, {
                "status": "cancelled",
                "error": reason,
                "steps": [],
            })

        with SessionLocal() as db:
            record = db.get(TaskRecord, task_id)
            return self._to_task(record) if record else None

    def list_sessions(self, user_id: str | None = None, team_id: str | None = None) -> list[Session]:
        with SessionLocal() as db:
            q = select(SessionRecord).order_by(SessionRecord.created_at.desc())
            if team_id is not None:
                q = q.join(TaskRecord, SessionRecord.task_id == TaskRecord.id).where(TaskRecord.team_id == team_id)
            elif user_id is not None:
                q = q.join(TaskRecord, SessionRecord.task_id == TaskRecord.id).where(TaskRecord.user_id == user_id)
            rows = db.execute(q).scalars().all()
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
        from manch_backend.db.models import ChatMessageRecord, ConversationRecord

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
    def _post_direct_result(
        conversation_id: str | None,
        task_id: str,
        message: str,
        output: dict | None,
    ) -> None:
        """Post the final assistant message for a direct-runner task."""
        if not conversation_id:
            return
        from manch_backend.db.models import ChatMessageRecord, ConversationRecord

        output_text = [
            message,
            output.get("stdout") if output else None,
            f"stderr: {output.get('stderr')}" if output and output.get("stderr") else None,
            f"risk: {output.get('risk')}" if output and output.get("risk") else None,
        ]
        assistant_text = "\n\n".join(part for part in output_text if part) or "Task completed."

        try:
            with SessionLocal() as db:
                msg = ChatMessageRecord(
                    id=str(uuid4()),
                    conversation_id=conversation_id,
                    role="assistant",
                    content=assistant_text,
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
            pass

    @staticmethod
    def _record_port_mappings(
        db: object,
        sandbox_session_id: str,
        task_id: str,
        ports: list[str],
    ) -> None:
        """Upsert port→sandbox mappings.

        If a port was previously mapped to an older sandbox, the old row is
        replaced so ``/preview/{port}`` always points to the latest sandbox
        that has that port running.
        """
        from sqlalchemy import delete

        for port_str in ports:
            port_int = int(port_str)
            # Remove stale mapping for this port (if any)
            db.execute(
                delete(PortMappingRecord).where(PortMappingRecord.port == port_int)
            )
            db.add(PortMappingRecord(
                id=str(uuid4()),
                port=port_int,
                sandbox_session_id=sandbox_session_id,
                task_id=task_id,
            ))
        db.commit()

    def _restart_sandbox_servers(
        self,
        sandbox_session_id: str,
        ports: list[str],
    ) -> None:
        """After the agent exits its shell kills any background processes.

        Scan common directories for server entry-points that reference each
        detected port and re-launch them with ``nohup … & disown`` so they
        survive future shell exits.
        """
        for port in ports:
            # Build a small shell script that:
            # 1. Finds the first JS/TS/PY file referencing this port
            # 2. Determines the runtime (node vs python)
            # 3. Starts it with nohup + disown
            # 4. Waits briefly and verifies the port is up
            restart_script = (
                f'SERVER_FILE=$(grep -rl "port.*{port}\\|{port}" '
                f'/app/ /my-app/ /root/ /home/ 2>/dev/null '
                f'| grep -E "\\.(js|ts|py)$" | head -1); '
                f'if [ -n "$SERVER_FILE" ]; then '
                f'DIR=$(dirname "$SERVER_FILE"); cd "$DIR"; '
                f'if [ -f package.json ]; then '
                f'nohup node "$SERVER_FILE" > /tmp/server-{port}.log 2>&1 & disown; '
                f'elif echo "$SERVER_FILE" | grep -q ".py$"; then '
                f'nohup python3 "$SERVER_FILE" > /tmp/server-{port}.log 2>&1 & disown; '
                f'fi; fi; '
                f'sleep 1; '
                f'curl -s http://localhost:{port} > /dev/null && '
                f'echo "Server on port {port}: RUNNING" || '
                f'echo "Server on port {port}: NOT_RUNNING"'
            )
            try:
                self.sandbox.run_command(
                    sandbox_session_id, restart_script, keep_alive=True,
                )
            except Exception:  # noqa: BLE001
                pass  # best-effort; don't fail the task

    @staticmethod
    def _emit(event_type: str, payload: dict, user_id: str | None = None, team_id: str | None = None) -> None:
        import asyncio

        try:
            loop = asyncio.get_running_loop()
            loop.create_task(event_broker.publish(event_type, payload, user_id=user_id, team_id=team_id))
        except RuntimeError:
            # Called from a background thread — use the registered main loop
            event_broker.publish_threadsafe(event_type, payload, user_id=user_id, team_id=team_id)

    @staticmethod
    def _build_command(prompt: str, runner: TaskRunner, approval_mode: str = "yolo") -> str:
        escaped_prompt = shlex.quote(prompt)
        if approval_mode == "yolo":
            approval_flag = "--yolo"
        else:
            approval_flag = f"--approval-mode {approval_mode}"

        # Lazy import avoids circular-import issues at module load time.
        try:
            from manch_backend.skills.registry import skill_registry
        except Exception:  # noqa: BLE001
            skill_registry = None  # type: ignore[assignment]

        if runner == TaskRunner.GEMINI_CLI or runner == TaskRunner.OPENSANDBOX:
            skill_setup = (
                skill_registry.build_skill_injection_cmd("gemini-cli")
                if skill_registry else ""
            )
            return (
                f"{skill_setup}"
                f"mkdir -p /root/.gemini && "
                f"gemini {approval_flag} --prompt {escaped_prompt}"
            )
        if runner == TaskRunner.CODEX_CLI:
            # --dangerously-bypass-approvals-and-sandbox: we are already inside
            # OpenSandbox so the inner bubblewrap sandbox is redundant.
            # -m gpt-4.1: explicit model selection for reliability.
            # Auth note: codex-cli uses ChatGPT OAuth by default. The sandbox
            # sets CODEX_API_KEY (= OPENAI_API_KEY) so codex-cli uses it as a
            # Bearer token (enable_codex_api_key_env=true in exec mode).
            skill_setup = (
                skill_registry.build_skill_injection_cmd("codex-cli")
                if skill_registry else ""
            )
            return (
                f"{skill_setup}"
                f"codex-cli exec --skip-git-repo-check "
                f"--dangerously-bypass-approvals-and-sandbox "
                f"-m gpt-4.1 "
                f"{escaped_prompt}"
            )
        if runner == TaskRunner.CLAUDE_CODE:
            # Claude Code CLI refuses --dangerously-skip-permissions as root.
            # Run as the 'node' user (built into the node:22 base image) via su.
            # The prompt is passed through an env-var so shell quoting stays simple.
            setup = (
                "mkdir -p /home/node/.claude /workspace && "
                "chown -R node:node /home/node /workspace"
            )
            inner = 'export HOME=/home/node && cd /workspace && claude'
            if approval_mode == "yolo":
                inner += ' --dangerously-skip-permissions'
            elif approval_mode == "plan":
                inner += ' --plan'
            inner += ' -p "$CLAUDE_PROMPT"'
            return (
                f"{setup} && export CLAUDE_PROMPT={escaped_prompt} && "
                f"su -m -s /bin/bash node -c '{inner}'"
            )
        return f"mkdir -p /root/.gemini && gemini {approval_flag} --prompt {escaped_prompt}"


orchestrator = OrchestratorService()
