"""
Scheduled audit hash-chain integrity check (SPEC §9.2 item 3).

Runnable as: python -m batch.audit_integrity
Suitable for cron / docker compose exec batch.
"""
from __future__ import annotations

import json
import logging
import sys

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from core.database import SessionLocal
from core.models import (
    AuditIntegrityResult,
    AuditLogModel,
    DecisionRecordModel,
    verify_audit_log_chain,
)

logger = logging.getLogger(__name__)


class AuditIntegrityError(Exception):
    """Raised when audit hash-chain integrity check fails."""

    def __init__(self, message: str, result: AuditIntegrityResult) -> None:
        super().__init__(message)
        self.result = result


def run_integrity_check(
    db: Session,
    *,
    raise_on_failure: bool = False,
) -> AuditIntegrityResult:
    logs = db.query(AuditLogModel).order_by(AuditLogModel.log_id).all()
    decision_count = db.scalar(select(func.count()).select_from(DecisionRecordModel))
    result = verify_audit_log_chain(logs, decision_count=decision_count)

    if not result.ok:
        msg = (
            f"audit integrity check failed: {len(result.breaks)} chain break(s)"
            + (", count mismatch" if result.count_mismatch else "")
        )
        logger.error(msg, extra={"audit_integrity": result.to_dict()})
        if raise_on_failure:
            raise AuditIntegrityError(msg, result)

    return result


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    db = SessionLocal()
    try:
        result = run_integrity_check(db, raise_on_failure=False)
        print(json.dumps(result.to_dict(), indent=2, sort_keys=True))
        if not result.ok:
            return 1
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
