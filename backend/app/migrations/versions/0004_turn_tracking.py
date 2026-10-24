"""sessions.turn_started_at + sessions.deadline_hit

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-24

Production-readiness fix for the stuck-session bug: a session could sit in
`investigating` indefinitely if Gemini's retries/failovers/cooldowns
compounded past any single call's timeout, with no overall turn deadline and
no durable record of "a turn is currently running." These two columns back
that fix — see CLAUDE.md "Turn deadline & crash recovery" and
app/services/conversation_engine.py.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("sessions", sa.Column("turn_started_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "sessions", sa.Column("deadline_hit", sa.Boolean(), nullable=False, server_default=sa.false())
    )


def downgrade() -> None:
    op.drop_column("sessions", "deadline_hit")
    op.drop_column("sessions", "turn_started_at")
