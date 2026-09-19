from batch.eval.theater import THEATER_DETECTOR_NAMES, TheaterContext, run_theater_detector


def test_registry_has_exactly_the_ten_named_checks():
    assert THEATER_DETECTOR_NAMES == frozenset(
        {
            "seeded_decision_e2e",
            "n1_headline",
            "unearned_demo_claim",
            "unit_as_e2e",
            "f1_only_usefulness",
            "stage_a_as_fp_win",
            "gt_in_scorer",
            "fake_ingest_api",
            "series_j_fold",
            "auto_resolved_as_precision",
        }
    )


def test_n1_headline_trips_on_s1_s4_only_decision_criterion():
    ctx = TheaterContext(
        headline_text="S1 recall 1.0, S4 recall 1.0 — operating point accepted"
    )
    tripped, detail = run_theater_detector("n1_headline", ctx)
    assert tripped is True
    assert "S1" in detail and "S4" in detail


def test_n1_headline_passes_when_s2_s3_s5_present_with_n():
    ctx = TheaterContext(
        headline_text="attributed S2 n=35 R=0.74; S3 n=45 R=0.11; S5 n=35 R=0.60"
    )
    tripped, _ = run_theater_detector("n1_headline", ctx)
    assert tripped is False


def test_seeded_decision_e2e_trips_when_demo_insert_counted_as_win():
    ctx = TheaterContext(
        decision_insert_path="scripts/demo_path.py",
        used_run_pipeline=False,
    )
    tripped, _ = run_theater_detector("seeded_decision_e2e", ctx)
    assert tripped is True


def test_unit_as_e2e_trips_without_run_pipeline():
    ctx = TheaterContext(used_run_pipeline=False)
    tripped, _ = run_theater_detector("unit_as_e2e", ctx)
    assert tripped is True


def test_gt_in_scorer_trips_on_label_import():
    ctx = TheaterContext(scorer_source="from core.models import EvalGroundTruthModel\n")
    tripped, _ = run_theater_detector("gt_in_scorer", ctx)
    assert tripped is True


def test_fake_ingest_api_trips_on_http_ingest_route():
    ctx = TheaterContext(introduces_http_ingest=True)
    tripped, _ = run_theater_detector("fake_ingest_api", ctx)
    assert tripped is True


def test_unearned_demo_claim_trips_on_series_a_as_current():
    ctx = TheaterContext(
        doc_texts={"README.md": "Current operating point: Precision ~0.019 · FP 3448"}
    )
    tripped, _ = run_theater_detector("unearned_demo_claim", ctx)
    assert tripped is True


def test_f1_only_usefulness_trips_when_flagged():
    tripped, _ = run_theater_detector(
        "f1_only_usefulness", TheaterContext(f1_treated_as_primary=True)
    )
    assert tripped is True


def test_stage_a_as_fp_win_trips_when_flagged():
    tripped, _ = run_theater_detector(
        "stage_a_as_fp_win", TheaterContext(stage_a_cited_as_fp_win=True)
    )
    assert tripped is True


def test_series_j_fold_trips_when_flagged():
    tripped, _ = run_theater_detector(
        "series_j_fold", TheaterContext(staffs_series_j=True)
    )
    assert tripped is True


def test_auto_resolved_as_precision_trips_when_flagged():
    tripped, _ = run_theater_detector(
        "auto_resolved_as_precision",
        TheaterContext(auto_resolved_used_as_fp_down=True),
    )
    assert tripped is True
