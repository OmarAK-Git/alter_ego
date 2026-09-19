from batch.eval.e2e_kernel import evaluate_scenario


def test_production_call_shape_both_arms(tmp_path):
    rows = evaluate_scenario("des.production_call_shape", sqlite_root=tmp_path)
    assert len(rows) == 2
    for row in rows:
        assert row.status == "pass"
        assert row.observed["stages_complete"] is True
        assert row.observed["seeded_decision_insert"] is False
        assert row.failure_class == "none"
