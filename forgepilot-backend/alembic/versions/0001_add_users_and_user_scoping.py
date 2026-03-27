"""add users table and user scoping to conversations and tasks

Revision ID: 0001
Revises:
Create Date: 2026-03-25
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.engine.reflection import Inspector

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_column(inspector: Inspector, table: str, column: str) -> bool:
    return any(c["name"] == column for c in inspector.get_columns(table))


def upgrade() -> None:
    bind = op.get_bind()
    inspector = Inspector.from_engine(bind)  # type: ignore[arg-type]
    existing_tables = inspector.get_table_names()

    # ── 1. Create users table ──────────────────────────────────────────────────
    if "users" not in existing_tables:
        op.create_table(
            "users",
            sa.Column("id", sa.String(64), nullable=False, primary_key=True),
            sa.Column("email", sa.String(255), nullable=False),
            sa.Column("hashed_password", sa.String(255), nullable=False),
            sa.Column("full_name", sa.String(255), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("now()"),
            ),
        )
        op.create_index("ix_users_email", "users", ["email"], unique=True)

    # ── 2. Ensure base tables exist (idempotent for fresh DBs) ────────────────
    if "tasks" not in existing_tables:
        op.create_table(
            "tasks",
            sa.Column("id", sa.String(64), nullable=False, primary_key=True),
            sa.Column("prompt", sa.String(8000), nullable=False),
            sa.Column("status", sa.String(32), nullable=False),
            sa.Column("user_id", sa.String(64), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        )
        op.create_index("ix_tasks_status", "tasks", ["status"])
        op.create_index("ix_tasks_user_id", "tasks", ["user_id"])

    if "sessions" not in existing_tables:
        op.create_table(
            "sessions",
            sa.Column("id", sa.String(64), nullable=False, primary_key=True),
            sa.Column("task_id", sa.String(64), sa.ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False),
            sa.Column("sandbox_session_id", sa.String(128), nullable=True),
            sa.Column("status", sa.String(32), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        )
        op.create_index("ix_sessions_task_id", "sessions", ["task_id"])
        op.create_index("ix_sessions_status", "sessions", ["status"])

    if "conversations" not in existing_tables:
        op.create_table(
            "conversations",
            sa.Column("id", sa.String(64), nullable=False, primary_key=True),
            sa.Column("title", sa.String(255), nullable=False),
            sa.Column("user_id", sa.String(64), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        )
        op.create_index("ix_conversations_updated_at", "conversations", ["updated_at"])
        op.create_index("ix_conversations_user_id", "conversations", ["user_id"])

    if "chat_messages" not in existing_tables:
        op.create_table(
            "chat_messages",
            sa.Column("id", sa.String(64), nullable=False, primary_key=True),
            sa.Column(
                "conversation_id",
                sa.String(64),
                sa.ForeignKey("conversations.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("role", sa.String(32), nullable=False),
            sa.Column("content", sa.String(12000), nullable=False),
            sa.Column("task_id", sa.String(64), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        )
        op.create_index("ix_chat_messages_conversation_id", "chat_messages", ["conversation_id"])

    # ── 3. Add user_id to existing tables (if tables already existed) ─────────
    if "conversations" in existing_tables and not _has_column(inspector, "conversations", "user_id"):
        op.add_column(
            "conversations",
            sa.Column("user_id", sa.String(64), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=True),
        )
        op.create_index("ix_conversations_user_id", "conversations", ["user_id"])

    if "tasks" in existing_tables and not _has_column(inspector, "tasks", "user_id"):
        op.add_column(
            "tasks",
            sa.Column("user_id", sa.String(64), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        )
        op.create_index("ix_tasks_user_id", "tasks", ["user_id"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = Inspector.from_engine(bind)  # type: ignore[arg-type]

    if _has_column(inspector, "conversations", "user_id"):
        op.drop_index("ix_conversations_user_id", table_name="conversations")
        op.drop_column("conversations", "user_id")

    if _has_column(inspector, "tasks", "user_id"):
        op.drop_index("ix_tasks_user_id", table_name="tasks")
        op.drop_column("tasks", "user_id")

    op.drop_table("users")
