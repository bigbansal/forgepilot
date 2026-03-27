from uuid import uuid4
from dataclasses import dataclass
import os
import subprocess
from pathlib import Path
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(title="OpenSandbox Mock", version="0.1.0")


@dataclass
class SandboxSession:
    id: str
    workdir: str


sessions: dict[str, SandboxSession] = {}
workspace_root = Path(os.getenv("OPENSANDBOX_WORKSPACE_ROOT", "/workspace/sessions"))
exec_timeout_seconds = int(os.getenv("OPENSANDBOX_EXEC_TIMEOUT_SECONDS", "90"))


class ExecRequest(BaseModel):
    command: str


@app.get("/health")
def health():
    return {"status": "ok", "service": "opensandbox-mock"}


@app.post("/sessions")
def create_session():
    session_id = f"sbx-{uuid4()}"
    session_dir = workspace_root / session_id
    session_dir.mkdir(parents=True, exist_ok=True)
    sessions[session_id] = SandboxSession(id=session_id, workdir=str(session_dir))
    return {"session_id": session_id}


@app.post("/sessions/{session_id}/exec")
def execute(session_id: str, request: ExecRequest):
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")

    session = sessions[session_id]
    command = request.command.strip()

    if command.startswith("process_prompt:"):
        prompt = command.split(":", 1)[1].strip()
        return {
            "stdout": f"[opensandbox:{session_id}] processed prompt: {prompt}",
            "stderr": "",
            "exit_code": 0,
        }

    try:
        result = subprocess.run(
            command,
            shell=True,
            cwd=session.workdir,
            capture_output=True,
            text=True,
            timeout=exec_timeout_seconds,
        )
    except subprocess.TimeoutExpired as error:
        return {
            "stdout": error.stdout or "",
            "stderr": (error.stderr or "") + f"\nCommand timed out after {exec_timeout_seconds}s",
            "exit_code": 124,
        }

    return {
        "stdout": result.stdout,
        "stderr": result.stderr,
        "exit_code": result.returncode,
    }
