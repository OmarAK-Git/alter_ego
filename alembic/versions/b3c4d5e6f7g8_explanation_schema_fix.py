"""Explanation schema fix

Revision ID: b3c4d5e6f7g8
Revises: a2b3c4d5e6f7
Create Date: 2026-05-17 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'b3c4d5e6f7g8'
down_revision: Union[str, Sequence[str], None] = 'a2b3c4d5e6f7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop existing explanations table
    op.drop_table('explanations')

    # Recreate explanations table with correct schema matching ExplanationRecordModel
    op.create_table('explanations',
        sa.Column('decision_id', sa.String(), nullable=False),
        sa.Column('summary_text', sa.String(), nullable=False),
        sa.Column('claim_objects', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('counterfactuals', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('validation_status', sa.String(), nullable=False),
        sa.Column('validation_notes', sa.String(), nullable=True),
        sa.Column('llm_model_id', sa.String(), nullable=False),
        sa.Column('prompt_hash', sa.String(), nullable=False),
        sa.Column('response_hash', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('decision_id')
    )


def downgrade() -> None:
    op.drop_table('explanations')
    
    # Revert to original schema (from 607152f795d1)
    op.create_table('explanations',
        sa.Column('decision_id', sa.String(), nullable=False),
        sa.Column('generated_at', sa.DateTime(), nullable=False),
        sa.Column('model_id', sa.String(), nullable=False),
        sa.Column('summary', sa.String(), nullable=False),
        sa.Column('claims', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('counterfactual', sa.String(), nullable=True),
        sa.PrimaryKeyConstraint('decision_id')
    )
