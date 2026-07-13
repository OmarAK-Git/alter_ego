"""Align profiles.embedding_model_id server default to alter-ego-ngram-v1

Revision ID: e4f5a6b7c8d9
Revises: d32eb29d44c1
Create Date: 2026-07-12 23:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "e4f5a6b7c8d9"
down_revision: Union[str, Sequence[str], None] = "d32eb29d44c1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SHIPPING_MODEL_ID = "alter-ego-ngram-v1"
LEGACY_MODEL_ID = "nomic-embed-text"


def upgrade() -> None:
    op.alter_column(
        "profiles",
        "embedding_model_id",
        existing_type=sa.String(),
        server_default=SHIPPING_MODEL_ID,
        existing_nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "profiles",
        "embedding_model_id",
        existing_type=sa.String(),
        server_default=LEGACY_MODEL_ID,
        existing_nullable=False,
    )
