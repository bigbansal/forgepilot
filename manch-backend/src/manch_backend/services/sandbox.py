from collections.abc import Callable
from dataclasses import dataclass
import os
from datetime import timedelta
from threading import Lock
from urllib.parse import urlparse
from opensandbox import SandboxSync
from opensandbox.config.connection_sync import ConnectionConfigSync
from opensandbox.models import Execution
from opensandbox.models.execd_sync import ExecutionHandlersSync
from manch_backend.config import settings


@dataclass
class ExecResult:
    stdout: str
    stderr: str
    exit_code: int


@dataclass
class SandboxSessionContext:
    sandbox: SandboxSync


class OpenSandboxAdapter:
    """Singleton adapter — ensures all callers share the same session registry."""

    _instance: "OpenSandboxAdapter | None" = None

    def __new__(cls) -> "OpenSandboxAdapter":
        if cls._instance is None:
            inst = super().__new__(cls)
            inst._contexts = {}
            inst._lock = Lock()
            cls._instance = inst
        return cls._instance

    def __init__(self) -> None:
        # __new__ handles initialisation; avoid resetting on subsequent calls
        pass

    def create_session(self) -> str:
        connection_config = self._connection_config()
        sandbox = SandboxSync.create(
            image=settings.opensandbox_image_uri,
            entrypoint=["tail", "-f", "/dev/null"],
            timeout=timedelta(seconds=settings.opensandbox_timeout_seconds),
            ready_timeout=timedelta(seconds=settings.opensandbox_ready_timeout_seconds),
            env=self._sandbox_env(),
            connection_config=connection_config,
        )
        context_id = sandbox.id
        with self._lock:
            self._contexts[context_id] = SandboxSessionContext(
                sandbox=sandbox,
            )
        return context_id

    def run_command(
        self,
        sandbox_session_id: str,
        command: str,
        on_stdout: Callable[[object], None] | None = None,
        keep_alive: bool = False,
    ) -> ExecResult:
        """Run a command in the sandbox.

        Args:
            keep_alive: If True, the sandbox session is NOT destroyed after
                        this command finishes. Use for multi-step agent pipelines.
        """
        with self._lock:
            context = self._contexts.get(sandbox_session_id)
        if not context:
            return ExecResult(stdout="", stderr="Sandbox session not found", exit_code=1)

        try:
            handlers = ExecutionHandlersSync(on_stdout=on_stdout) if on_stdout else None
            execution = context.sandbox.commands.run(command, handlers=handlers)
            return self._execution_to_result(execution)
        except Exception as error:
            return ExecResult(stdout="", stderr=str(error), exit_code=1)
        finally:
            if not keep_alive:
                self._destroy_session(sandbox_session_id)

    def destroy_session(self, sandbox_session_id: str) -> None:
        """Explicitly tear down a sandbox session."""
        self._destroy_session(sandbox_session_id)

    def _destroy_session(self, sandbox_session_id: str) -> None:
        with self._lock:
            context = self._contexts.pop(sandbox_session_id, None)
        if context:
            try:
                context.sandbox.kill()
            except Exception:
                pass
            try:
                context.sandbox.close()
            except Exception:
                pass

    @staticmethod
    def _execution_to_result(execution: Execution) -> ExecResult:
        stdout = "\n".join(line.text for line in execution.logs.stdout if line.text)
        stderr = "\n".join(line.text for line in execution.logs.stderr if line.text)
        if execution.result:
            result_text = "\n".join(item.text for item in execution.result if item.text)
            if result_text:
                stdout = f"{stdout}\n{result_text}".strip()
        if execution.error:
            error_text = execution.error.value or execution.error.name
            stderr = f"{stderr}\n{error_text}".strip() if stderr else error_text
            return ExecResult(stdout=stdout, stderr=stderr, exit_code=1)
        return ExecResult(stdout=stdout, stderr=stderr, exit_code=0)

    @staticmethod
    def _connection_config() -> ConnectionConfigSync:
        parsed = urlparse(settings.opensandbox_base_url)
        protocol = parsed.scheme or "http"
        domain = parsed.netloc or parsed.path
        return ConnectionConfigSync(
            api_key=settings.opensandbox_api_key or None,
            domain=domain,
            protocol=protocol,
            request_timeout=timedelta(seconds=settings.opensandbox_request_timeout_seconds),
            use_server_proxy=settings.opensandbox_use_server_proxy,
        )

    @staticmethod
    def _sandbox_env() -> dict[str, str]:
        gemini_key = settings.gemini_api_key or os.getenv("GEMINI_API_KEY", "")
        openai_key = settings.openai_api_key or os.getenv("OPENAI_API_KEY", "")
        anthropic_key = settings.anthropic_api_key or os.getenv("ANTHROPIC_API_KEY", "")
        env: dict[str, str] = {}
        if gemini_key:
            env["GEMINI_API_KEY"] = gemini_key
        if openai_key:
            env["OPENAI_API_KEY"] = openai_key
            # codex-cli (codex-rs) uses its own ChatGPT OAuth system by default.
            # When built with enable_codex_api_key_env=true (which codex exec does),
            # it reads CODEX_API_KEY env var and uses it as a Bearer token.
            # Without this, codex-cli sends no Authorization header → WSS 500.
            env["CODEX_API_KEY"] = openai_key
        if anthropic_key:
            env["ANTHROPIC_API_KEY"] = anthropic_key
        return env
