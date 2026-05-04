"""Initial schema

Revision ID: 607152f795d1
Revises: 
Create Date: 2026-05-03 21:07:07.967252

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '607152f795d1'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


from sqlalchemy.dialects import postgresql
import pgvector.sqlalchemy

def upgrade() -> None:
    # Ensure pgvector extension is available
    op.execute("CREATE EXTENSION IF NOT EXISTS vector;")

    op.create_table('events',
        sa.Column('event_id', sa.String(), nullable=False),
        sa.Column('timestamp', sa.DateTime(), nullable=False),
        sa.Column('event_type', sa.String(), nullable=False),
        sa.Column('raw_entity_id', sa.String(), nullable=False),
        sa.Column('event_data', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.PrimaryKeyConstraint('event_id')
    )
    op.create_table('resolved_events',
        sa.Column('event_id', sa.String(), nullable=False),
        sa.Column('timestamp', sa.DateTime(), nullable=False),
        sa.Column('event_type', sa.String(), nullable=False),
        sa.Column('raw_entity_id', sa.String(), nullable=False),
        sa.Column('entity_id', sa.String(), nullable=False),
        sa.Column('entity_type', sa.String(), nullable=False),
        sa.Column('resolution_confidence', sa.Float(), nullable=False),
        sa.Column('event_data', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.PrimaryKeyConstraint('event_id')
    )
    op.create_index(op.f('ix_resolved_events_entity_id'), 'resolved_events', ['entity_id'], unique=False)
    
    op.create_table('profiles',
        sa.Column('profile_version', sa.String(), nullable=False),
        sa.Column('entity_id', sa.String(), nullable=False),
        sa.Column('entity_type', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('data_window_start', sa.DateTime(), nullable=False),
        sa.Column('data_window_end', sa.DateTime(), nullable=False),
        sa.Column('features', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('embedding', pgvector.sqlalchemy.Vector(dim=1536), nullable=True),
        sa.PrimaryKeyConstraint('profile_version')
    )
    op.create_index(op.f('ix_profiles_entity_id'), 'profiles', ['entity_id'], unique=False)

    op.create_table('decisions',
        sa.Column('decision_id', sa.String(), nullable=False),
        sa.Column('event_id', sa.String(), nullable=False),
        sa.Column('entity_id', sa.String(), nullable=False),
        sa.Column('timestamp', sa.DateTime(), nullable=False),
        sa.Column('score', sa.Float(), nullable=False),
        sa.Column('confidence', sa.Float(), nullable=False),
        sa.Column('profile_version', sa.String(), nullable=False),
        sa.Column('scoring_config_version', sa.String(), nullable=False),
        sa.Column('contributions', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('is_anomaly', sa.Boolean(), nullable=False),
        sa.Column('flags', postgresql.ARRAY(sa.String()), nullable=False),
        sa.PrimaryKeyConstraint('decision_id')
    )
    op.create_index(op.f('ix_decisions_entity_id'), 'decisions', ['entity_id'], unique=False)
    op.create_index(op.f('ix_decisions_event_id'), 'decisions', ['event_id'], unique=False)
    op.create_index(op.f('ix_decisions_is_anomaly'), 'decisions', ['is_anomaly'], unique=False)

    op.create_table('explanations',
        sa.Column('decision_id', sa.String(), nullable=False),
        sa.Column('generated_at', sa.DateTime(), nullable=False),
        sa.Column('model_id', sa.String(), nullable=False),
        sa.Column('summary', sa.String(), nullable=False),
        sa.Column('claims', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('counterfactual', sa.String(), nullable=True),
        sa.PrimaryKeyConstraint('decision_id')
    )

    op.create_table('audit_logs',
        sa.Column('log_id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('timestamp', sa.DateTime(), nullable=False),
        sa.Column('action', sa.String(), nullable=False),
        sa.Column('entity_id', sa.String(), nullable=True),
        sa.Column('details', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.PrimaryKeyConstraint('log_id')
    )

    op.create_table('eval_ground_truth',
        sa.Column('event_id', sa.String(), nullable=False),
        sa.Column('is_malicious', sa.Boolean(), nullable=False),
        sa.Column('scenario', sa.String(), nullable=False),
        sa.PrimaryKeyConstraint('event_id')
    )

    op.create_table('containment_queue',
        sa.Column('queue_id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('decision_id', sa.String(), nullable=False),
        sa.Column('entity_id', sa.String(), nullable=False),
        sa.Column('action', sa.String(), nullable=False),
        sa.Column('status', sa.String(), nullable=False),
        sa.Column('queued_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('queue_id')
    )

def downgrade() -> None:
    op.drop_table('containment_queue')
    op.drop_table('eval_ground_truth')
    op.drop_table('audit_logs')
    op.drop_table('explanations')
    op.drop_index(op.f('ix_decisions_is_anomaly'), table_name='decisions')
    op.drop_index(op.f('ix_decisions_event_id'), table_name='decisions')
    op.drop_index(op.f('ix_decisions_entity_id'), table_name='decisions')
    op.drop_table('decisions')
    op.drop_index(op.f('ix_profiles_entity_id'), table_name='profiles')
    op.drop_table('profiles')
    op.drop_index(op.f('ix_resolved_events_entity_id'), table_name='resolved_events')
    op.drop_table('resolved_events')
    op.drop_table('events')
