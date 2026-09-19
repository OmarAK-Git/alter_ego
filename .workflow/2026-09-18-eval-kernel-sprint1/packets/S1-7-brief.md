# S1-7 review / verify packet

**Task:** gov.integrity_job_sees_decisions
**Claim:** after run_pipeline on mini JSONL, run_integrity_check names skip `decision_audit_count==0`; decision_count > 0; count_check_skipped is True. Both arms pass by naming the skip, not by pretending the job sees decisions.

Controller: `pytest tests/eval/test_gov_integrity_job_sees_decisions.py -v --tb=short`
