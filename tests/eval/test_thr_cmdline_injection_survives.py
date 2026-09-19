from batch.eval.e2e_kernel import evaluate_scenario


def test_cmdline_injection_survives_ingest_both_arms(tmp_path):
    rows = evaluate_scenario("thr.cmdline_injection_survives", sqlite_root=tmp_path)
    for row in rows:
        assert row.status == "pass"
        assert row.observed["ingested"] is True
        assert row.observed["scored"] is True
        assert row.observed["payload_persisted"] is True
        assert row.observed["slot_escaped"] is True
        assert row.observed["introduces_http_ingest"] is False
