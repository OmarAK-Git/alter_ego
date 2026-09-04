from pathlib import Path

p = Path("docs/residual-risk-drift-hypotheses.md")
text = p.read_text(encoding="utf-8")
old = "**Status (2026-08-02):** Stage A implemented (`signal_family_agreement_count`, `precision_gate.enabled: false`). Stage B explicitly not built. Series H governance complete (`1cc2e3e`, `docs/scoring-config-governance-series-h.md`) — benign FP agreement mean=0.841 vs TP=1.0."
new = (
    "**Status (2026-08-02):** Stage A implemented (`signal_family_agreement_count`). "
    "Stage B explicitly not built. Series H governance complete (`1cc2e3e`, "
    "`docs/scoring-config-governance-series-h.md`) — benign FP agreement mean=0.841 vs TP=1.0. "
    "**Series I (2026-08-03):** `precision_gate.enabled: true` promoted (fold_06 accept; **not CALIBRATED**). "
    "Standing note: unexpected recall drop without knob changes — investigate Stage A containment gating "
    "(≥2 families at score≥85) before thr=45 anomaly path; see "
    "`.workflow/2026-08-02-series-i-serial-calibration/results/scoring-config-governance-series-i-fold_06_precision_gate.md`."
)
if old not in text:
    raise SystemExit("H14 old status not found")
p.write_text(text.replace(old, new), encoding="utf-8")

ops = Path("OPS.md")
ot = ops.read_text(encoding="utf-8")
bullet = (
    "- **Series I / precision_gate (2026-08-03):** `precision_gate.enabled=true` promoted; **not CALIBRATED**. "
    "Recall regression without intentional knob changes — fold_06 operator note in "
    "`.workflow/2026-08-02-series-i-serial-calibration/results/scoring-config-governance-series-i-fold_06_precision_gate.md`; "
    "H14 in `docs/residual-risk-drift-hypotheses.md`.\n"
)
marker = "- **Standing rule:**"
if "Series I / precision_gate" not in ot:
    ot = ot.replace(marker, bullet + marker)
    ops.write_text(ot, encoding="utf-8")
print("docs updated")
