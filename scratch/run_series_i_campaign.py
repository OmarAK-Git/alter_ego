"""Series I overnight campaign orchestrator.

Runs weight search then serial additive folds. Stops cleanly near budget with RESUME.md.
"""
from __future__ import annotations

import json
import logging
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
WF = REPO_ROOT / ".workflow" / "2026-08-02-series-i-serial-calibration"
RESULTS = WF / "results"
STATE_PATH = WF / "state.json"
RESUME_PATH = WF / "RESUME.md"
RESULTS_MD = WF / "RESULTS.md"
CONFIG_PATH = REPO_ROOT / "config" / "scoring_config.yaml"
SWEEP_SCRIPT = REPO_ROOT / "scratch" / "run_series_i_sweep.py"

# ~8h overnight budget from start; leave 20 min for docs/commit at end.
BUDGET_SECONDS = 8 * 3600
RESERVE_SECONDS = 20 * 60
# Estimate ~2.5h/sweep from Series F cloud; stop scheduling if remaining < this.
MIN_SWEEP_SECONDS = 2.0 * 3600

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

BASELINE = {
    "precision": 0.006708907938874394,
    "recall": 0.46153846153846156,
    "f1": 0.01322556943423953,
    "tp": 54,
    "fp": 7995,
    "fn": 63,
    "s1": 1.0,
    "s2": 0.7428571428571429,
    "s3": 0.1111111111111111,
    "s4": 1.0,
    "s5": 0.6,
}


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load_state() -> dict:
    return json.loads(STATE_PATH.read_text(encoding="utf-8"))


def save_state(state: dict) -> None:
    state["updated_at"] = utc_now()
    STATE_PATH.write_text(json.dumps(state, indent=2), encoding="utf-8")


def load_metrics(step: str) -> dict:
    path = RESULTS / f"series_i_{step}_metrics.json"
    return json.loads(path.read_text(encoding="utf-8"))


def headline_of(payload: dict) -> dict:
    h = dict(payload.get("headline") or {})
    m = payload.get("metrics") or {}
    if not h:
        scenarios = m.get("scenarios") or {}
        h = {
            "precision": m.get("precision"),
            "recall": m.get("recall"),
            "f1": m.get("f1"),
            "tp": m.get("tp"),
            "fp": m.get("fp"),
            "fn": m.get("fn"),
            "s1": (scenarios.get("scenario_1_sharp_misuse") or {}).get("recall"),
            "s2": (scenarios.get("scenario_2_slow_roll") or {}).get("recall"),
            "s3": (scenarios.get("scenario_3_subtle") or {}).get("recall"),
            "s4": (scenarios.get("scenario_4_service_abuse") or {}).get("recall"),
            "s5": (scenarios.get("scenario_5_patient_cycle") or {}).get("recall"),
        }
    return h


def rank_key(h: dict) -> tuple:
    """Higher F1, then higher recall, then lower FP. None-safe."""
    f1 = float(h.get("f1") or 0.0)
    recall = float(h.get("recall") or 0.0)
    fp = float(h.get("fp") if h.get("fp") is not None else 1e18)
    return (f1, recall, -fp)


def floors_ok(h: dict) -> bool:
    s1 = h.get("s1")
    s4 = h.get("s4")
    if s1 is None or s4 is None:
        return False
    return float(s1) >= 1.0 - 1e-9 and float(s4) >= 1.0 - 1e-9


def is_inert_vs_baseline(h: dict, tol_fp: int = 5, tol_tp: int = 0) -> bool:
    """True if headline is essentially identical to Series E–H baseline."""
    return (
        abs(int(h.get("tp") or -1) - BASELINE["tp"]) <= tol_tp
        and abs(int(h.get("fp") or -1) - BASELINE["fp"]) <= tol_fp
        and abs(float(h.get("f1") or 0) - BASELINE["f1"]) < 1e-6
        and abs(float(h.get("recall") or 0) - BASELINE["recall"]) < 1e-6
    )


def better_than_baseline(h: dict) -> bool:
    return rank_key(h) > rank_key(BASELINE)


def run_sweep(step: str, sets: list[str]) -> int:
    cmd = [sys.executable, str(SWEEP_SCRIPT), "--step", step]
    for s in sets:
        cmd.extend(["--set", s])
    logger.info("LAUNCH %s", " ".join(cmd))
    proc = subprocess.run(cmd, cwd=str(REPO_ROOT))
    return proc.returncode


def write_governance(
    step: str,
    decision: str,
    reason: str,
    headline: dict,
    overrides: list[str],
) -> Path:
    path = RESULTS / f"scoring-config-governance-series-i-{step}.md"
    lines = [
        f"# Scoring-config governance — Series I / {step}",
        "",
        f"**Timestamp:** {utc_now()}",
        f"**Status:** **Not CALIBRATED.** Decision: **{decision}**",
        "",
        "## Overrides under test",
        "",
        "```",
        *overrides,
        "```",
        "",
        "## Headline @ thr=45",
        "",
        "| Metric | Value | Baseline |",
        "|---|---:|---:|",
        f"| P | {headline.get('precision')} | {BASELINE['precision']} |",
        f"| R | {headline.get('recall')} | {BASELINE['recall']} |",
        f"| F1 | {headline.get('f1')} | {BASELINE['f1']} |",
        f"| TP / FP / FN | {headline.get('tp')} / {headline.get('fp')} / {headline.get('fn')} | "
        f"{BASELINE['tp']} / {BASELINE['fp']} / {BASELINE['fn']} |",
        f"| S1 / S4 | {headline.get('s1')} / {headline.get('s4')} | {BASELINE['s1']} / {BASELINE['s4']} |",
        f"| S2 / S3 / S5 | {headline.get('s2')} / {headline.get('s3')} / {headline.get('s5')} | "
        f"{BASELINE['s2']} / {BASELINE['s3']} / {BASELINE['s5']} |",
        "",
        "## Decision reason",
        "",
        reason,
        "",
        "Evidence report for Series I serial campaign. calibrated: false.",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def apply_accepted_yaml(accepted: dict[str, Any]) -> None:
    """Persist accepted flag/weight state into committed YAML on this branch."""
    with open(CONFIG_PATH, encoding="utf-8") as f:
        config = yaml.safe_load(f)

    # Reset all Series-I-managed knobs to disabled/zero first, then apply accepted.
    config.setdefault("drift_weights", {})
    for dim in ("cadence", "total_volume_delta", "geo_velocity"):
        node = config["drift_weights"].setdefault(dim, {})
        if not isinstance(node, dict):
            node = {"weight": float(node), "enabled": False}
            config["drift_weights"][dim] = node
        node["enabled"] = False
        if dim != "geo_velocity":
            node.setdefault("weight", 0.0)
        else:
            node.setdefault("weight", 0.0)
            node.setdefault("vpn_allowlist", node.get("vpn_allowlist", []))

    feat_vol = config.setdefault("features", {}).setdefault("total_volume_delta", {})
    feat_vol["enabled"] = False
    feat_vol.setdefault("weight", 1.0)

    config.setdefault("cohort_gating_constants", {})["fleet_drift_enabled"] = False
    config.setdefault("precision_gate", {})["enabled"] = False
    config.setdefault("staged_drift", {})["enabled"] = False

    for path, value in accepted.items():
        parts = path.split(".")
        node = config
        for p in parts[:-1]:
            node = node.setdefault(p, {})
        node[parts[-1]] = value

    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        yaml.safe_dump(config, f, default_flow_style=False, sort_keys=False)


def git_commit(message: str, paths: list[str]) -> None:
    subprocess.run(["git", "add", "--"] + paths, cwd=str(REPO_ROOT), check=False)
    # Only commit if there is something staged
    staged = subprocess.run(
        ["git", "diff", "--cached", "--quiet"], cwd=str(REPO_ROOT)
    )
    if staged.returncode == 0:
        logger.info("Nothing to commit for: %s", message)
        return
    subprocess.run(
        ["git", "commit", "-m", message],
        cwd=str(REPO_ROOT),
        check=False,
    )


def remaining_budget(t0: float) -> float:
    return BUDGET_SECONDS - (time.time() - t0)


def write_resume(state: dict, reason: str) -> None:
    next_steps = state.get("sweeps_queued") or []
    done = state.get("sweeps_completed") or []
    text = f"""# RESUME — Series I serial calibration

**Stopped:** {utc_now()}
**Reason:** {reason}
**Branch:** `series-i-serial-calibration`
**Phase:** {state.get('phase')}
**Current step pointer:** {state.get('current_step')}

## Completed sweeps

{chr(10).join(f'- `{s}`' for s in done) or '(none)'}

## Remaining queue

{chr(10).join(f'- `{s}`' for s in next_steps) or '(none)'}

## Weight winners so far

```json
{json.dumps(state.get('weight_winners') or {{}}, indent=2)}
```

## Accepted flags so far

```json
{json.dumps(state.get('accepted_flags') or {{}}, indent=2)}
```

## Rejected flags so far

```json
{json.dumps(state.get('rejected_flags') or {{}}, indent=2)}
```

## How to resume

```bash
git checkout series-i-serial-calibration
python scratch/run_series_i_campaign.py --resume
```

Do **not** claim CALIBRATED. Do **not** merge to main without operator review.
"""
    RESUME_PATH.write_text(text, encoding="utf-8")


def write_results_md(state: dict) -> None:
    rows = []
    for step in state.get("sweeps_completed") or []:
        try:
            payload = load_metrics(step)
            h = headline_of(payload)
            rows.append(
                f"| `{step}` | {h.get('f1')} | {h.get('recall')} | {h.get('fp')} | "
                f"{h.get('s1')} | {h.get('s4')} | {h.get('tp')} |"
            )
        except Exception as exc:
            rows.append(f"| `{step}` | ERR | | | | | {exc} |")

    accepted = state.get("accepted_flags") or {}
    rejected = state.get("rejected_flags") or {}
    winners = state.get("weight_winners") or {}
    decision = state.get("merge_recommendation") or "merge-with-gaps"

    text = f"""# Series I — RESULTS

**Branch:** `series-i-serial-calibration`
**Updated:** {utc_now()}
**Calibrated:** false
**Merge recommendation:** **{decision}**

## Objective

Recall–FP tradeoff at thr=45: rank by F1, then higher recall, then lower FP.
Floors: prefer keep S1=1.0 and S4=1.0.

## Baseline (Series E–H)

P≈0.0067 R≈0.4615 F1≈0.0132 TP=54 FP=7995 FN=63; S1=1 S2≈0.74 S3≈0.11 S4=1 S5=0.60

## Weight winners

```json
{json.dumps(winners, indent=2)}
```

## Accepted into branch YAML

```json
{json.dumps(accepted, indent=2)}
```

## Rejected

```json
{json.dumps(rejected, indent=2)}
```

## Sweep table

| Step | F1 | Recall | FP | S1 | S4 | TP |
|---|---:|---:|---:|---:|---:|---:|
| baseline (E–H) | {BASELINE['f1']} | {BASELINE['recall']} | {BASELINE['fp']} | {BASELINE['s1']} | {BASELINE['s4']} | {BASELINE['tp']} |
{chr(10).join(rows)}

## Final YAML state

See committed `config/scoring_config.yaml` on this branch. All newly accepted
flags/weights are persisted there; rejected knobs remain disabled / weight 0.

## Accept/reject reasons

See per-step governance docs under `results/scoring-config-governance-series-i-*.md`.

## Notes

- Never claim CALIBRATED (`"calibrated": false` in all metrics payloads).
- No merge to main; operator review only.
- No DEBT-028 / Stage B / `core/schemas/config.py` edits in this campaign.
"""
    RESULTS_MD.write_text(text, encoding="utf-8")


def pick_weight_winner(dim: str, candidates: list[tuple[str, float]]) -> tuple[float | None, str]:
    """Pick best candidate by rank_key among floor-ok; None => leave disabled."""
    viable: list[tuple[float, dict, str]] = []
    for step, weight in candidates:
        h = headline_of(load_metrics(step))
        if not floors_ok(h):
            logger.info("%s w=%s REJECT floors S1=%s S4=%s", dim, weight, h.get("s1"), h.get("s4"))
            continue
        if is_inert_vs_baseline(h):
            logger.info("%s w=%s inert vs baseline", dim, weight)
            continue
        viable.append((weight, h, step))

    if not viable:
        return None, f"No viable {dim} weight: all inert or collapsed S1/S4 floors"

    viable.sort(key=lambda t: rank_key(t[1]), reverse=True)
    best_w, best_h, best_step = viable[0]
    if better_than_baseline(best_h):
        return best_w, (
            f"Winner {dim}={best_w} from {best_step}: F1={best_h.get('f1')} "
            f"R={best_h.get('recall')} FP={best_h.get('fp')} (floors intact, beats baseline)"
        )
    return None, (
        f"No {dim} weight beats Series E–H baseline on F1/R/FP "
        f"(best was w={best_w} F1={best_h.get('f1')} FP={best_h.get('fp')})"
    )


def decide_fold(
    step: str,
    h: dict,
    flag_label: str,
) -> tuple[str, str]:
    """Return (accept|reject, reason)."""
    if not floors_ok(h):
        return "reject", (
            f"REJECT {flag_label}: S1/S4 floor collapse "
            f"(S1={h.get('s1')}, S4={h.get('s4')})"
        )
    if is_inert_vs_baseline(h) and step.startswith("fold_"):
        # Relative to Series E–H; for additive folds compare also to previous accepted
        # via rank vs baseline — inert means no detectable effect.
        return "reject", f"REJECT {flag_label}: inert vs Series E–H baseline (no score effect)"
    if better_than_baseline(h):
        return "accept", (
            f"ACCEPT {flag_label}: improves rank vs baseline "
            f"(F1={h.get('f1')}, R={h.get('recall')}, FP={h.get('fp')})"
        )
    # Not better than baseline but non-inert and floors ok — reject (prefer baseline)
    return "reject", (
        f"REJECT {flag_label}: does not improve F1/R/FP rank vs baseline "
        f"(F1={h.get('f1')}, R={h.get('recall')}, FP={h.get('fp')})"
    )


def decide_fold_vs_prev(h: dict, prev: dict, flag_label: str) -> tuple[str, str]:
    if not floors_ok(h):
        return "reject", (
            f"REJECT {flag_label}: S1/S4 floor collapse "
            f"(S1={h.get('s1')}, S4={h.get('s4')})"
        )
    if rank_key(h) > rank_key(prev):
        return "accept", (
            f"ACCEPT {flag_label}: improves vs prior accepted baseline "
            f"(F1 {prev.get('f1')}→{h.get('f1')}, R {prev.get('recall')}→{h.get('recall')}, "
            f"FP {prev.get('fp')}→{h.get('fp')})"
        )
    if (
        abs(float(h.get("f1") or 0) - float(prev.get("f1") or 0)) < 1e-9
        and abs(int(h.get("fp") or 0) - int(prev.get("fp") or 0)) <= 5
        and abs(float(h.get("recall") or 0) - float(prev.get("recall") or 0)) < 1e-9
    ):
        return "reject", f"REJECT {flag_label}: inert vs prior accepted baseline"
    return "reject", (
        f"REJECT {flag_label}: worse/equal rank vs prior accepted "
        f"(F1 {prev.get('f1')}→{h.get('f1')}, R {prev.get('recall')}→{h.get('recall')}, "
        f"FP {prev.get('fp')}→{h.get('fp')})"
    )


def sets_from_accepted(accepted: dict[str, Any]) -> list[str]:
    return [f"{k}={v}" if not isinstance(v, bool) else f"{k}={str(v).lower()}" for k, v in accepted.items()]


def main() -> int:
    t0 = time.time()
    state = load_state()
    RESULTS.mkdir(parents=True, exist_ok=True)

    # Ensure events exist once up front.
    gen = subprocess.run(
        [sys.executable, str(SWEEP_SCRIPT), "--step", "_generate", "--generate-only"],
        cwd=str(REPO_ROOT),
    )
    if gen.returncode != 0:
        logger.error("Event generation failed")
        return 1

    git_commit(
        "Series I: scaffold workflow + sweep/campaign harness",
        [
            ".workflow/2026-08-02-series-i-serial-calibration",
            "scratch/run_series_i_sweep.py",
            "scratch/run_series_i_campaign.py",
            "memory-bank/activeContext.md",
            "memory-bank/progress.md",
        ],
    )

    # ---------- Phase A: weight search ----------
    state["phase"] = "A_weight_search"
    save_state(state)

    cadence_grid = [(2.0, "ws_cadence_2"), (5.0, "ws_cadence_5"), (10.0, "ws_cadence_10")]
    volume_grid = [(1.0, "ws_volume_1"), (5.0, "ws_volume_5"), (15.0, "ws_volume_15")]
    geo_grid = [(5.0, "ws_geo_5")]

    def _need(step: str) -> bool:
        return step not in (state.get("sweeps_completed") or [])

    def _budget_ok() -> bool:
        rem = remaining_budget(t0)
        if rem < RESERVE_SECONDS + MIN_SWEEP_SECONDS:
            logger.warning("Budget low (%.0fs remaining); stopping before next sweep", rem)
            return False
        return True

    # Cadence weight search
    for weight, step in cadence_grid:
        if not _need(step):
            continue
        if not _budget_ok():
            write_resume(state, "Budget exhausted during cadence weight search")
            write_results_md(state)
            _finalize_partial(state)
            return 0
        state["current_step"] = step
        save_state(state)
        rc = run_sweep(
            step,
            [
                "drift_weights.cadence.enabled=true",
                f"drift_weights.cadence.weight={weight}",
            ],
        )
        if rc != 0:
            write_resume(state, f"Sweep {step} failed rc={rc}")
            write_results_md(state)
            return rc
        h = headline_of(load_metrics(step))
        write_governance(
            step,
            "evidence",
            f"Cadence weight probe w={weight}. Floors_ok={floors_ok(h)} inert={is_inert_vs_baseline(h)}",
            h,
            [
                "drift_weights.cadence.enabled=true",
                f"drift_weights.cadence.weight={weight}",
            ],
        )
        state.setdefault("sweeps_completed", []).append(step)
        if step in state.get("sweeps_queued", []):
            state["sweeps_queued"].remove(step)
        save_state(state)
        git_commit(
            f"Series I: cadence weight probe {step} (w={weight})",
            [str(RESULTS), str(STATE_PATH)],
        )

    cw, creason = pick_weight_winner(
        "cadence", [(s, w) for w, s in cadence_grid]
    )
    state.setdefault("weight_winners", {})["cadence"] = {
        "weight": cw,
        "reason": creason,
    }
    save_state(state)
    logger.info("Cadence winner: %s (%s)", cw, creason)

    # Volume drift weight search
    for weight, step in volume_grid:
        if not _need(step):
            continue
        if not _budget_ok():
            write_resume(state, "Budget exhausted during volume weight search")
            write_results_md(state)
            _finalize_partial(state)
            return 0
        state["current_step"] = step
        save_state(state)
        rc = run_sweep(
            step,
            [
                "drift_weights.total_volume_delta.enabled=true",
                f"drift_weights.total_volume_delta.weight={weight}",
            ],
        )
        if rc != 0:
            write_resume(state, f"Sweep {step} failed rc={rc}")
            write_results_md(state)
            return rc
        h = headline_of(load_metrics(step))
        write_governance(
            step,
            "evidence",
            f"Volume-drift weight probe w={weight}. Floors_ok={floors_ok(h)} inert={is_inert_vs_baseline(h)}",
            h,
            [
                "drift_weights.total_volume_delta.enabled=true",
                f"drift_weights.total_volume_delta.weight={weight}",
            ],
        )
        state.setdefault("sweeps_completed", []).append(step)
        if step in state.get("sweeps_queued", []):
            state["sweeps_queued"].remove(step)
        save_state(state)
        git_commit(
            f"Series I: volume weight probe {step} (w={weight})",
            [str(RESULTS), str(STATE_PATH)],
        )

    vw, vreason = pick_weight_winner(
        "total_volume_delta", [(s, w) for w, s in volume_grid]
    )
    state.setdefault("weight_winners", {})["total_volume_delta"] = {
        "weight": vw,
        "reason": vreason,
    }
    save_state(state)
    logger.info("Volume winner: %s (%s)", vw, vreason)

    # Geo one-shot
    for weight, step in geo_grid:
        if not _need(step):
            continue
        if not _budget_ok():
            write_resume(state, "Budget exhausted before geo probe")
            write_results_md(state)
            _finalize_partial(state)
            return 0
        state["current_step"] = step
        save_state(state)
        rc = run_sweep(
            step,
            [
                "drift_weights.geo_velocity.enabled=true",
                f"drift_weights.geo_velocity.weight={weight}",
            ],
        )
        if rc != 0:
            write_resume(state, f"Sweep {step} failed rc={rc}")
            write_results_md(state)
            return rc
        h = headline_of(load_metrics(step))
        inert = is_inert_vs_baseline(h)
        decomp = (load_metrics(step).get("metrics") or {}).get(
            "per_dimension_drift_decomposition", {}
        )
        geo_mean = (decomp.get("geo_velocity") or {}).get("mean")
        if inert or (geo_mean is not None and float(geo_mean) == 0.0):
            gw, greason = None, (
                f"REJECT geo_velocity: inert (mean_delta={geo_mean}, "
                f"headline≈baseline). Skip further geo trials."
            )
            decision = "reject"
        elif not floors_ok(h):
            gw, greason = None, "REJECT geo_velocity: S1/S4 floor collapse"
            decision = "reject"
        elif better_than_baseline(h):
            gw, greason = weight, f"ACCEPT geo probe w={weight} improves vs baseline"
            decision = "accept-weight"
        else:
            gw, greason = None, (
                f"REJECT geo_velocity w={weight}: non-inert but no F1/R/FP improvement"
            )
            decision = "reject"
        write_governance(step, decision, greason, h, [
            "drift_weights.geo_velocity.enabled=true",
            f"drift_weights.geo_velocity.weight={weight}",
        ])
        state.setdefault("weight_winners", {})["geo_velocity"] = {
            "weight": gw,
            "reason": greason,
        }
        state.setdefault("sweeps_completed", []).append(step)
        if step in state.get("sweeps_queued", []):
            state["sweeps_queued"].remove(step)
        save_state(state)
        git_commit(
            f"Series I: geo_velocity probe {step} (w={weight})",
            [str(RESULTS), str(STATE_PATH)],
        )

    # ---------- Phase B: serial folds ----------
    state["phase"] = "B_serial_folds"
    save_state(state)

    winners = state.get("weight_winners") or {}
    cadence_w = (winners.get("cadence") or {}).get("weight")
    volume_w = (winners.get("total_volume_delta") or {}).get("weight")
    geo_w = (winners.get("geo_velocity") or {}).get("weight")

    accepted: dict[str, Any] = dict(state.get("accepted_flags") or {})
    rejected: dict[str, Any] = dict(state.get("rejected_flags") or {})
    prev_headline = dict(BASELINE)

    folds: list[tuple[str, list[str], str]] = []

    # 1 cadence
    if cadence_w is not None:
        folds.append((
            "fold_01_cadence",
            [
                "drift_weights.cadence.enabled=true",
                f"drift_weights.cadence.weight={cadence_w}",
            ],
            "drift_weights.cadence",
        ))
    else:
        rejected["drift_weights.cadence"] = "No viable cadence weight from Phase A"
        if "fold_01_cadence" in state.get("sweeps_queued", []):
            state["sweeps_queued"].remove("fold_01_cadence")

    # 2 feature volume
    folds.append((
        "fold_02_feature_volume",
        ["features.total_volume_delta.enabled=true"],
        "features.total_volume_delta",
    ))

    # 3 drift volume
    if volume_w is not None:
        folds.append((
            "fold_03_drift_volume",
            [
                "drift_weights.total_volume_delta.enabled=true",
                f"drift_weights.total_volume_delta.weight={volume_w}",
            ],
            "drift_weights.total_volume_delta",
        ))
    else:
        rejected["drift_weights.total_volume_delta"] = "No viable volume-drift weight from Phase A"
        if "fold_03_drift_volume" in state.get("sweeps_queued", []):
            state["sweeps_queued"].remove("fold_03_drift_volume")

    # 4 geo
    if geo_w is not None:
        folds.append((
            "fold_04_geo",
            [
                "drift_weights.geo_velocity.enabled=true",
                f"drift_weights.geo_velocity.weight={geo_w}",
            ],
            "drift_weights.geo_velocity",
        ))
    else:
        rejected["drift_weights.geo_velocity"] = (winners.get("geo_velocity") or {}).get(
            "reason", "inert/rejected in Phase A"
        )
        if "fold_04_geo" in state.get("sweeps_queued", []):
            state["sweeps_queued"].remove("fold_04_geo")

    folds.append((
        "fold_05_fleet",
        ["cohort_gating_constants.fleet_drift_enabled=true"],
        "cohort_gating_constants.fleet_drift_enabled",
    ))
    folds.append((
        "fold_06_precision_gate",
        ["precision_gate.enabled=true"],
        "precision_gate.enabled",
    ))
    folds.append((
        "fold_07_staged_drift",
        ["staged_drift.enabled=true"],
        "staged_drift.enabled",
    ))

    state["accepted_flags"] = accepted
    state["rejected_flags"] = rejected
    save_state(state)

    for step, new_sets, flag_label in folds:
        if not _need(step):
            continue
        if not _budget_ok():
            state["accepted_flags"] = accepted
            state["rejected_flags"] = rejected
            write_resume(state, f"Budget exhausted before {step}")
            write_results_md(state)
            _finalize_partial(state)
            return 0

        # Additive: prior accepted + new flag sets
        combo = sets_from_accepted(accepted) + new_sets
        # Dedup by key (later wins)
        merged: dict[str, str] = {}
        for item in combo:
            k, v = item.split("=", 1)
            merged[k] = v
        combo = [f"{k}={v}" for k, v in merged.items()]

        state["current_step"] = step
        save_state(state)
        rc = run_sweep(step, combo)
        if rc != 0:
            write_resume(state, f"Sweep {step} failed rc={rc}")
            write_results_md(state)
            return rc

        h = headline_of(load_metrics(step))
        decision, reason = decide_fold_vs_prev(h, prev_headline, flag_label)
        write_governance(step, decision, reason, h, combo)

        if decision == "accept":
            for item in new_sets:
                k, v = item.split("=", 1)
                if v in {"true", "false"}:
                    accepted[k] = v == "true"
                else:
                    try:
                        accepted[k] = float(v) if "." in v else int(v)
                    except ValueError:
                        accepted[k] = float(v)
            apply_accepted_yaml(accepted)
            prev_headline = h
        else:
            rejected[flag_label] = reason

        state["accepted_flags"] = accepted
        state["rejected_flags"] = rejected
        state.setdefault("sweeps_completed", []).append(step)
        if step in state.get("sweeps_queued", []):
            state["sweeps_queued"].remove(step)
        save_state(state)
        git_commit(
            f"Series I: {step} → {decision}",
            [
                str(RESULTS),
                str(STATE_PATH),
                "config/scoring_config.yaml",
            ],
        )

    # Complete
    state["phase"] = "complete"
    state["current_step"] = "done"
    if state.get("sweeps_queued"):
        state["merge_recommendation"] = "merge-with-gaps"
    elif accepted:
        state["merge_recommendation"] = "merge"
    else:
        state["merge_recommendation"] = "do-not-merge"
    state["status"] = "complete"
    save_state(state)
    write_results_md(state)
    _update_memory_bank(state)
    git_commit(
        "Series I: campaign complete — RESULTS + memory-bank",
        [
            str(WF),
            "memory-bank/activeContext.md",
            "memory-bank/progress.md",
            "config/scoring_config.yaml",
        ],
    )
    logger.info("Campaign complete. merge_recommendation=%s", state["merge_recommendation"])
    return 0


def _finalize_partial(state: dict) -> None:
    state["status"] = "paused"
    state["merge_recommendation"] = "merge-with-gaps"
    save_state(state)
    _update_memory_bank(state)
    git_commit(
        "Series I: pause — RESUME + partial RESULTS",
        [
            str(WF),
            "memory-bank/activeContext.md",
            "memory-bank/progress.md",
            "config/scoring_config.yaml",
        ],
    )


def _update_memory_bank(state: dict) -> None:
    active = REPO_ROOT / "memory-bank" / "activeContext.md"
    progress = REPO_ROOT / "memory-bank" / "progress.md"
    active.write_text(
        f"""# Active Context

**Updated:** {utc_now()} — Series I serial calibration ({state.get('status')})

## Current focus

**T3:** `.workflow/2026-08-02-series-i-serial-calibration/`
**Branch:** `series-i-serial-calibration`
**Phase:** {state.get('phase')} / step `{state.get('current_step')}`
**Calibrated:** false
**Merge recommendation:** {state.get('merge_recommendation')}

## Weight winners

```json
{json.dumps(state.get('weight_winners') or {{}}, indent=2)}
```

## Accepted flags

```json
{json.dumps(state.get('accepted_flags') or {{}}, indent=2)}
```

## Queue remaining

{chr(10).join(f'- `{s}`' for s in (state.get('sweeps_queued') or [])) or '(none)'}

## Standing order

All gates on Grok until operator overrides. Do not merge Series I to main without operator review.
""",
        encoding="utf-8",
    )
    prev = progress.read_text(encoding="utf-8") if progress.exists() else ""
    block = f"""
## Series I serial calibration ({utc_now()})

- Branch: `series-i-serial-calibration`
- Status: {state.get('status')} / phase {state.get('phase')}
- Completed sweeps: {', '.join(state.get('sweeps_completed') or []) or '(none)'}
- Merge recommendation: {state.get('merge_recommendation')}
- Artifacts: `.workflow/2026-08-02-series-i-serial-calibration/`
"""
    progress.write_text(prev.rstrip() + "\n" + block + "\n", encoding="utf-8")


if __name__ == "__main__":
    # --resume just re-enters main; completed steps are skipped via sweeps_completed
    raise SystemExit(main())
