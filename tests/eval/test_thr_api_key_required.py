from batch.eval.e2e_kernel import evaluate_scenario


def test_api_key_required_without_pytest_bypass(tmp_path):
    rows = evaluate_scenario("thr.api_key_required", sqlite_root=tmp_path)
    for row in rows:
        assert row.status == "pass"
        assert row.observed["missing_status"] == 401
        assert row.observed["wrong_status"] == 401
        assert row.observed["pytest_loaded"] is False
