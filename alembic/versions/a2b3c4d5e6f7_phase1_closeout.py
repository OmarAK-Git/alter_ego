"""Phase 1 closeout: simulation_partition to string, shadow profiles, embedding model update

Revision ID: a2b3c4d5e6f7
Revises: 607152f795d1
Create Date: 2026-05-04 15:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import pgvector.sqlalchemy


# revision identifiers, used by Alembic.
revision: str = 'a2b3c4d5e6f7'
down_revision: Union[str, Sequence[str], None] = '607152f795d1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. simulation_partition: Boolean -> String (events, resolved_events)
    # Drop the old boolean column and add a new string column with default 'production'
    op.add_column('events', sa.Column('simulation_partition', sa.String(), nullable=False, server_default='production'))
    op.add_column('resolved_events', sa.Column('simulation_partition', sa.String(), nullable=False, server_default='production'))

    # 2. Shadow profiles: add is_shadow to profiles
    op.add_column('profiles', sa.Column('is_shadow', sa.Boolean(), nullable=False, server_default='false'))

    # 3. Embedding model: update dimension from 1536 to 128 and add metadata columns
    #    Add embedding_model_id, embedding_model_version, embedding_dimensionality if missing
    op.add_column('profiles', sa.Column('embedding_model_id', sa.String(), nullable=False, server_default='nomic-embed-text'))
    op.add_column('profiles', sa.Column('embedding_model_version', sa.String(), nullable=False, server_default='1.0'))
    op.add_column('profiles', sa.Column('embedding_dimensionality', sa.Integer(), nullable=False, server_default='128'))

    # Update the embedding vector column dimension from 1536 to 128
    # pgvector ALTER COLUMN requires dropping and re-adding
    op.drop_column('profiles', 'embedding')
    op.add_column('profiles', sa.Column('embedding', pgvector.sqlalchemy.Vector(dim=128), nullable=True))


def downgrade() -> None:
    # Revert embedding column
    op.drop_column('profiles', 'embedding')
    op.add_column('profiles', sa.Column('embedding', pgvector.sqlalchemy.Vector(dim=1536), nullable=True))

    # Remove embedding metadata columns
    op.drop_column('profiles', 'embedding_dimensionality')
    op.drop_column('profiles', 'embedding_model_version')
    op.drop_column('profiles', 'embedding_model_id')

    # Remove is_shadow
    op.drop_column('profiles', 'is_shadow')

    # Remove simulation_partition string columns
    op.drop_column('resolved_events', 'simulation_partition')
    op.drop_column('events', 'simulation_partition')
