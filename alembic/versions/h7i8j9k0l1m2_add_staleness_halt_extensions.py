"""Add staleness_halt_extensions table for extend-halt persistence

Revision ID: h7i8j9k0l1m2
Revises: g6h7i8j9k0l1
Create Date: 2026-07-13 07:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "h7i8j9k0l1m2"
down_revision: Union[str, Sequence[str], None] = "g6h7i8j9k0l1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "staleness_halt_extensions",
        sa.Column("extension_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("entity_id", sa.String(), nullable=False),
        sa.Column("justification", sa.String(), nullable=False),
        sa.Column("extended_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("extension_id"),
    )
    op.create_index(
        op.f("ix_staleness_halt_extensions_entity_id"),
        "staleness_halt_extensions",
        ["entity_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_staleness_halt_extensions_entity_id"),
        table_name="staleness_halt_extensions",
    )
    op.drop_table("staleness_halt_extensions")
