from batch.eval.e2e_kernel import evaluate_scenario


def test_integrity_skip_is_named_after_pipeline_decisions(tmp_path):
    rows = evaluate_scenario("gov.integrity_job_sees_decisions", sqlite_root=tmp_path)
    for row in rows:
        assert row.status == "pass"
        assert row.observed["decision_count_gt_0"] is True
        assert row.observed["count_check_skipped"] is True
        assert row.observed["integrity_skip"] == "decision_audit_count==0"
