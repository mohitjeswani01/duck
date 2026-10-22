"""repo_files table; repos drops file_tree_cache (unused, superseded by repo_files),
adds last_indexed_at

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-22

Phase 2 replaced "cache the GitHub file tree, call the API per file" with
"download one tarball per connect, store filtered text files in Postgres."
file_tree_cache was never populated under the new approach, so it's dropped
rather than left dead; last_indexed_at drives the cache-reuse/refresh check.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("repos", sa.Column("last_indexed_at", sa.DateTime(timezone=True), nullable=True))
    op.drop_column("repos", "file_tree_cache")

    op.create_table(
        "repo_files",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("repo_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("repos.id"), nullable=False),
        sa.Column("file_path", sa.String(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("language", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_repo_files_repo_id", "repo_files", ["repo_id"])
    op.create_index("ix_repo_files_repo_id_file_path", "repo_files", ["repo_id", "file_path"], unique=True)


def downgrade() -> None:
    op.drop_table("repo_files")
    op.add_column(
        "repos",
        sa.Column("file_tree_cache", postgresql.JSONB(), nullable=True),
    )
    op.drop_column("repos", "last_indexed_at")
