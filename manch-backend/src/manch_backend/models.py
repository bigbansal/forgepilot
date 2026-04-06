from enum import Enum
from datetime import datetime, UTC
from pydantic import BaseModel, Field


class TaskStatus(str, Enum):
    CREATED = "CREATED"
    PLANNING = "PLANNING"
    RUNNING = "RUNNING"
    WAITING_APPROVAL = "WAITING_APPROVAL"
    VALIDATING = "VALIDATING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class StepStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class RiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class AgentTier(str, Enum):
    CONDUCTOR = "conductor"
    SPECIALIST = "specialist"
    SUPPORT = "support"


class ModelClass(str, Enum):
    FAST = "fast"
    BALANCED = "balanced"
    REASONING = "reasoning"


class TaskRunner(str, Enum):
    OPENSANDBOX = "opensandbox"
    GEMINI_CLI = "gemini-cli"
    CODEX_CLI = "codex-cli"
    CLAUDE_CODE = "claude-code"
    AGENT_PIPELINE = "agent-pipeline"


class Task(BaseModel):
    id: str
    prompt: str
    title: str | None = None
    status: TaskStatus = TaskStatus.CREATED
    priority: str | None = "normal"
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class Session(BaseModel):
    id: str
    task_id: str
    sandbox_session_id: str | None = None
    repo_url: str | None = None
    branch: str | None = None
    working_directory: str | None = None
    status: TaskStatus = TaskStatus.CREATED
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class PlanStep(BaseModel):
    id: str
    task_id: str
    order_index: int
    agent_name: str
    description: str
    status: StepStatus = StepStatus.PENDING
    output_summary: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None


class ToolExecution(BaseModel):
    id: str
    task_id: str
    step_id: str | None = None
    tool_name: str
    input_summary: str | None = None
    output_summary: str | None = None
    result_status: str = "pending"
    duration_ms: int | None = None
    cost_estimate: float | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ApprovalRequest(BaseModel):
    id: str
    task_id: str
    step_id: str | None = None
    operation_type: str
    risk_level: RiskLevel
    reason: str
    paused_step_index: int | None = None
    decision: str | None = None
    decided_by: str | None = None
    requested_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    resolved_at: datetime | None = None


class Artifact(BaseModel):
    id: str
    task_id: str
    step_id: str | None = None
    artifact_type: str
    content: str | None = None
    storage_path: str | None = None
    metadata_json: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class AgentDefinition(BaseModel):
    name: str
    tier: str
    model_class: str = "balanced"
    parallel_safe: bool = True
    purpose: str
    file_path: str


# ── Team / Tenant models ─────────────────────────────────────────

class TeamRole(str, Enum):
    OWNER = "owner"
    ADMIN = "admin"
    MEMBER = "member"
    VIEWER = "viewer"


class Team(BaseModel):
    id: str
    name: str
    slug: str
    owner_id: str | None = None
    is_active: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class TeamMember(BaseModel):
    id: str
    team_id: str
    user_id: str
    role: TeamRole = TeamRole.MEMBER
    joined_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    # populated on read
    email: str | None = None
    full_name: str | None = None
