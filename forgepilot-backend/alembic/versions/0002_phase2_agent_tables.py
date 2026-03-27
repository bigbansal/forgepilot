"""Phase 2 — add plan_steps, tool_executions, approval_requests, artifacts tables
and extend tasks/sessions with new columns.

Revision ID: 0002
Revises: 0001_add_users_and_user_scoping
Create Date: 2026-03-25
"""
from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── Extend existing tables ──────────────────────────
    op.add_column("tasks", sa.Column("title", sa.String(255), nullable=True))
    op.add_column("tasks", sa.Column("priority", sa.String(16), nullable=True, server_default="normal"))

    op.add_column("sessions", sa.Column("repo_url", sa.String(512), nullable=True))
    op.add_column("sessions", sa.Column("branch", sa.String(255), nullable=True))
    op.add_column("sessions", sa.Column("working_directory", sa.String(512), nullable=True))

    # ── Plan Steps ──────────────────────────────────────
    op.create_table(
        "plan_steps",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("task_id", sa.String(64), sa.ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("order_index", sa.Integer, nullable=False),
        sa.Column("agent_name", sa.String(64), nullable=False),
        sa.Column("description", sa.String(2000), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("output_summary", sa.Text, nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
    )

    # ── Tool Executions ─────────────────────────────────
    op.create_table(
        "tool_executions",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("task_id", sa.String(64), sa.ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("step_id", sa.String(64), sa.ForeignKey("plan_steps.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("tool_name", sa.String(128), nullable=False),
        sa.Column("input_summary", sa.Text, nullable=True),
        sa.Column("output_summary", sa.Text, nullable=True),
        sa.Column("result_status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("duration_ms", sa.Integer, nullable=True),
        sa.Column("cost_estimate", sa.Float, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # ── Approval Requests ───────────────────────────────
    op.create_table(
        "approval_requests",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("task_id", sa.String(64), sa.ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("step_id", sa.String(64), sa.ForeignKey("plan_steps.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("operation_type", sa.String(128), nullable=False),
        sa.Column("risk_level", sa.String(16), nullable=False),
        sa.Column("reason", sa.String(2000), nullable=False),
        sa.Column("decision", sa.String(16), nullable=True),
        sa.Column("decided_by", sa.String(64), nullable=True),
        sa.Column("requested_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
    )

    # ── Artifacts ───────────────────────────────────────
    op.create_table(
        "artifacts",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("task_id", sa.String(64), sa.ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("step_id", sa.String(64), sa.ForeignKey("plan_steps.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("artifact_type", sa.String(64), nullable=False),
        sa.Column("content", sa.Text, nullable=True),
        sa.Column("storage_path", sa.String(512), nullable=True),
        sa.Column("metadata_json", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("artifacts")
    op.drop_table("approval_requests")
    op.drop_table("tool_executions")
    op.drop_table("plan_steps")
    op.drop_column("sessions", "working_directory")
    op.drop_column("sessions", "branch")
    op.drop_column("sessions", "repo_url")
    op.drop_column("tasks", "priority")
    op.drop_column("tasks", "title")
