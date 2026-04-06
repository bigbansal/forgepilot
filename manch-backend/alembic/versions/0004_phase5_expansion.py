"""Phase 5 — expansion tables: audit_logs, repositories, memory_entries.

Revision ID: 0004
Revises: 0003
Create Date: 2026-03-27
"""
from alembic import op
import sqlalchemy as sa

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── audit_logs ───────────────────────────────────
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("user_id", sa.String(64), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("action", sa.String(128), nullable=False, index=True),
        sa.Column("resource_type", sa.String(64), nullable=True, index=True),
        sa.Column("resource_id", sa.String(64), nullable=True),
        sa.Column("detail", sa.Text(), nullable=True),
        sa.Column("ip_address", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now(), index=True),
    )

    # ── repositories ─────────────────────────────────
    op.create_table(
        "repositories",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("url", sa.String(512), nullable=False),
        sa.Column("default_branch", sa.String(128), nullable=False, server_default="main"),
        sa.Column("description", sa.String(2000), nullable=True),
        sa.Column("owner_id", sa.String(64), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # ── memory_entries ───────────────────────────────
    op.create_table(
        "memory_entries",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("key", sa.String(255), nullable=False, index=True),
        sa.Column("category", sa.String(64), nullable=False, index=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("tags_json", sa.Text(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=False, server_default=sa.text("0.5")),
        sa.Column("retention_value", sa.String(16), nullable=False, server_default="MEDIUM"),
        sa.Column("source_task_id", sa.String(64), nullable=True, index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now(), index=True),
    )


def downgrade() -> None:
    op.drop_table("memory_entries")
    op.drop_table("repositories")
    op.drop_table("audit_logs")
