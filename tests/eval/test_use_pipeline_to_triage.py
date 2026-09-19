from batch.eval.e2e_kernel import evaluate_scenario


def test_pipeline_anomaly_reaches_alerts_api(tmp_path):
    rows = evaluate_scenario("use.pipeline_to_triage", sqlite_root=tmp_path)
    for row in rows:
        assert row.status == "pass"
        assert row.observed["alert_visible"] is True
        assert row.observed["contributions_reconstruct"] is True
        assert row.observed["seeded_decision_insert"] is False
