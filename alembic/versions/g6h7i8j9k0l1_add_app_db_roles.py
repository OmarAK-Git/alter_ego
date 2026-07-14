"""Add alter_ego_app runtime role with least-privilege grants

Revision ID: g6h7i8j9k0l1
Revises: f5a6b7c8d9e0
Create Date: 2026-07-13 06:00:00.000000

"""
import os
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "g6h7i8j9k0l1"
down_revision: Union[str, Sequence[str], None] = "f5a6b7c8d9e0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

APP_ROLE = "alter_ego_app"
APP_PASSWORD = os.environ.get("ALTER_EGO_APP_PASSWORD", "alter_ego_app_dev")

APPEND_ONLY_TABLES = (
    "audit_logs",
    "decisions",
    "explanations",
    "scoring_configs",
)

INSERT_ONLY_OPERATIONAL_TABLES = (
    "events",
    "resolved_events",
    "containment_queue",
    "eval_ground_truth",
)

SEQUENCES = (
    "audit_logs_log_id_seq",
    "containment_queue_queue_id_seq",
)


def _sql_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def upgrade() -> None:
    password = _sql_literal(APP_PASSWORD)
    op.execute(
        f"""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{APP_ROLE}') THEN
                CREATE ROLE {APP_ROLE} LOGIN PASSWORD {password};
            ELSE
                ALTER ROLE {APP_ROLE} WITH LOGIN PASSWORD {password};
            END IF;
        END
        $$;
        """
    )
    op.execute(f"GRANT CONNECT ON DATABASE alter_ego TO {APP_ROLE}")
    op.execute(f"GRANT USAGE ON SCHEMA public TO {APP_ROLE}")

    for table in APPEND_ONLY_TABLES:
        op.execute(f"GRANT SELECT, INSERT ON TABLE {table} TO {APP_ROLE}")
        op.execute(f"REVOKE UPDATE, DELETE ON TABLE {table} FROM {APP_ROLE}")

    for table in INSERT_ONLY_OPERATIONAL_TABLES:
        op.execute(f"GRANT SELECT, INSERT ON TABLE {table} TO {APP_ROLE}")
        op.execute(f"REVOKE UPDATE, DELETE ON TABLE {table} FROM {APP_ROLE}")

    op.execute(f"GRANT SELECT, INSERT ON TABLE profiles TO {APP_ROLE}")
    op.execute(f"REVOKE UPDATE ON TABLE profiles FROM {APP_ROLE}")
    op.execute(
        f"GRANT UPDATE (promoted_at, superseded_at) ON TABLE profiles TO {APP_ROLE}"
    )
    op.execute(f"REVOKE DELETE ON TABLE profiles FROM {APP_ROLE}")

    op.execute(f"GRANT SELECT, INSERT, UPDATE ON TABLE alert_workflow_state TO {APP_ROLE}")
    op.execute(f"REVOKE DELETE ON TABLE alert_workflow_state FROM {APP_ROLE}")

    for sequence in SEQUENCES:
        op.execute(f"GRANT USAGE, SELECT ON SEQUENCE {sequence} TO {APP_ROLE}")


def downgrade() -> None:
    for sequence in SEQUENCES:
        op.execute(f"REVOKE ALL ON SEQUENCE {sequence} FROM {APP_ROLE}")

    op.execute(f"REVOKE ALL ON TABLE alert_workflow_state FROM {APP_ROLE}")

    op.execute(f"REVOKE ALL ON TABLE profiles FROM {APP_ROLE}")

    for table in INSERT_ONLY_OPERATIONAL_TABLES:
        op.execute(f"REVOKE ALL ON TABLE {table} FROM {APP_ROLE}")

    for table in APPEND_ONLY_TABLES:
        op.execute(f"REVOKE ALL ON TABLE {table} FROM {APP_ROLE}")

    op.execute(f"REVOKE USAGE ON SCHEMA public FROM {APP_ROLE}")
    op.execute(f"REVOKE CONNECT ON DATABASE alter_ego FROM {APP_ROLE}")
    op.execute(f"DROP ROLE IF EXISTS {APP_ROLE}")
