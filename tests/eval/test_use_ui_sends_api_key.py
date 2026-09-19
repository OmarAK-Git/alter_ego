from pathlib import Path

from batch.eval.e2e_kernel import evaluate_scenario


def test_kernel_names_missing_ui_api_key(tmp_path):
    source = Path("web/static/app.js").read_text(encoding="utf-8")
    rows = evaluate_scenario("use.ui_sends_api_key", sqlite_root=tmp_path)
    for row in rows:
        assert row.status == "pass"
        assert row.observed["named_gap"] == "app.js omits X-API-KEY"
        if "X-API-KEY" in source:
            assert row.observed["ui_sends_api_key"] is True
        else:
            assert row.observed["ui_sends_api_key"] is False
