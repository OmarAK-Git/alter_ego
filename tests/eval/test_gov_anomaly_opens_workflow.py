from batch.eval.e2e_kernel import evaluate_scenario


def test_pipeline_anomaly_opens_new_workflow_both_arms(tmp_path):
    rows = evaluate_scenario("gov.anomaly_opens_workflow", sqlite_root=tmp_path)
    assert len(rows) == 2
    for row in rows:
        assert row.status == "pass"
        assert row.observed["anomaly_count_gt_0"] is True
        assert row.observed["all_anomalies_open_new"] is True
        assert row.observed["seeded_decision_insert"] is False
