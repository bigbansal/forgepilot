"""Add repo_id FK to tasks table for multi-repo selector.

Revision ID: 0006
Revises: 0005
Create Date: 2026-04-04
"""
from alembic import op
import sqlalchemy as sa

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("tasks", sa.Column("repo_id", sa.String(64), nullable=True))
    op.create_index("ix_tasks_repo_id", "tasks", ["repo_id"])
    op.create_foreign_key(
        "fk_tasks_repo_id",
        "tasks",
        "repositories",
        ["repo_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_tasks_repo_id", "tasks", type_="foreignkey")
    op.drop_index("ix_tasks_repo_id", table_name="tasks")
    op.drop_column("tasks", "repo_id")
