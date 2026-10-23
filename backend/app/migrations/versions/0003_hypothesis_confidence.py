"""hypotheses.confidence (low/medium/high)

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-23

Phase 3's state_hypothesis tool requires Gemini to state a confidence level
alongside its evidence — low confidence pauses the turn to confirm with the
user instead of barreling on to propose_fix. A dedicated enum column, not a
field inside the existing `evidence` jsonb blob, since it drives backend
control flow and should be queryable/typed.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

hypothesis_confidence = postgresql.ENUM("low", "medium", "high", name="hypothesis_confidence", create_type=False)


def upgrade() -> None:
    hypothesis_confidence.create(op.get_bind(), checkfirst=True)
    op.add_column(
        "hypotheses",
        sa.Column("confidence", hypothesis_confidence, nullable=False, server_default="medium"),
    )


def downgrade() -> None:
    op.drop_column("hypotheses", "confidence")
    hypothesis_confidence.drop(op.get_bind(), checkfirst=True)
