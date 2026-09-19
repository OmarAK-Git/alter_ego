from batch.eval.e2e_kernel import evaluate_scenario, format_capability_headline
from batch.eval.theater import TheaterContext, run_theater_detector


def test_formatter_refuses_s1_s4_only():
    bad = format_capability_headline(
        {
            "scenario_1_sharp_misuse": {"n": 1, "recall": 1.0},
            "scenario_4_service_abuse": {"n": 1, "recall": 1.0},
        }
    )
    assert bad.startswith("REFUSED:")
    tripped, _ = run_theater_detector(
        "n1_headline", TheaterContext(headline_text=bad.replace("REFUSED:", ""))
    )
    assert tripped is True


def test_formatter_accepts_s2_s3_s5_with_n():
    text = format_capability_headline(
        {
            "scenario_2_slow_roll": {"n": 35, "recall": 0.74},
            "scenario_3_subtle": {"n": 45, "recall": 0.11},
            "scenario_5_patient_cycle": {"n": 35, "recall": 0.60},
        }
    )
    assert not text.startswith("REFUSED:")
    tripped, _ = run_theater_detector("n1_headline", TheaterContext(headline_text=text))
    assert tripped is False


def test_cap_no_n1_headline_both_arms_pass(tmp_path):
    rows = evaluate_scenario("cap.no_n1_headline", sqlite_root=tmp_path)
    for row in rows:
        assert row.status == "pass"
        assert row.observed["n1_headline_rejected"] is True
        assert row.status != "pending"
