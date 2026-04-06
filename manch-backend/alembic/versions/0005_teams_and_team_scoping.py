"""Phase 5b — teams & team scoping: teams, team_members tables; team_id FK on tasks, conversations, repositories, audit_logs, memory_entries.

Revision ID: 0005
Revises: 0004
Create Date: 2026-04-03
"""
from alembic import op
import sqlalchemy as sa

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── teams ────────────────────────────────────────
    op.create_table(
        "teams",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(255), nullable=False, unique=True),
        sa.Column("owner_id", sa.String(64), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_teams_slug", "teams", ["slug"], unique=True)
    op.create_index("ix_teams_owner_id", "teams", ["owner_id"])

    # ── team_members ─────────────────────────────────
    op.create_table(
        "team_members",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("team_id", sa.String(64), sa.ForeignKey("teams.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.String(64), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.String(32), nullable=False, server_default="member"),
        sa.Column("joined_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("team_id", "user_id", name="uq_team_user"),
    )
    op.create_index("ix_team_members_team_id", "team_members", ["team_id"])
    op.create_index("ix_team_members_user_id", "team_members", ["user_id"])

    # ── Add team_id FK to existing tables ────────────
    for table in ("tasks", "conversations", "repositories", "audit_logs", "memory_entries"):
        op.add_column(table, sa.Column("team_id", sa.String(64), nullable=True))
        op.create_foreign_key(
            f"fk_{table}_team_id", table, "teams", ["team_id"], ["id"], ondelete="SET NULL"
        )
        op.create_index(f"ix_{table}_team_id", table, ["team_id"])


def downgrade() -> None:
    for table in ("memory_entries", "audit_logs", "repositories", "conversations", "tasks"):
        op.drop_constraint(f"fk_{table}_team_id", table, type_="foreignkey")
        op.drop_index(f"ix_{table}_team_id", table_name=table)
        op.drop_column(table, "team_id")

    op.drop_table("team_members")
    op.drop_table("teams")
