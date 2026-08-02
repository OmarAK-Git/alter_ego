"""Add decisions.signal_family_agreement_count and decisions.precision_gate_version (H14 Stage A)

Revision ID: i8j9k0l1m2n3
Revises: h7i8j9k0l1m2
Create Date: 2026-07-30 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "i8j9k0l1m2n3"
down_revision: Union[str, Sequence[str], None] = "h7i8j9k0l1m2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "decisions",
        sa.Column("signal_family_agreement_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "decisions",
        sa.Column("precision_gate_version", sa.String(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("decisions", "precision_gate_version")
    op.drop_column("decisions", "signal_family_agreement_count")
