"""Add decisions.replay_run_id for replay lineage

Revision ID: f5a6b7c8d9e0
Revises: e4f5a6b7c8d9
Create Date: 2026-07-13 01:55:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "f5a6b7c8d9e0"
down_revision: Union[str, Sequence[str], None] = "e4f5a6b7c8d9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("decisions", sa.Column("replay_run_id", sa.String(), nullable=True))
    op.create_index(
        op.f("ix_decisions_replay_run_id"),
        "decisions",
        ["replay_run_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_decisions_replay_run_id"), table_name="decisions")
    op.drop_column("decisions", "replay_run_id")
