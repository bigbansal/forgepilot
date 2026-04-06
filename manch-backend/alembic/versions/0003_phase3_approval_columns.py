"""Phase 3 — add paused_step_index to approval_requests, conversation_id and
sandbox_session_id to tasks.

Revision ID: 0003
Revises: 0002
Create Date: 2026-03-26
"""
from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add paused_step_index to approval_requests
    op.add_column(
        "approval_requests",
        sa.Column("paused_step_index", sa.Integer(), nullable=True),
    )

    # Add conversation_id and sandbox_session_id to tasks
    op.add_column(
        "tasks",
        sa.Column("conversation_id", sa.String(64), nullable=True),
    )
    op.add_column(
        "tasks",
        sa.Column("sandbox_session_id", sa.String(255), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("tasks", "sandbox_session_id")
    op.drop_column("tasks", "conversation_id")
    op.drop_column("approval_requests", "paused_step_index")
