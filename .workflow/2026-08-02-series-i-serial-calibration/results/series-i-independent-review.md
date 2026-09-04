# Series I — independent review

**Reviewer:** external pass over `results/*.json`, `state.json`, and the five fold governance docs.
**Scope:** 12 metrics JSONs (5 folds + 7 cloud weight/solo lanes), config v2.2.
**Status of this doc:** review only. Authorizes nothing.

---

## Bottom line

The campaign is **mechanically sound and epistemically blind.** Every accept/reject decision
follows correctly from the evidence the harness produced. The problem is that the harness
measured something that could not respond to any of the treatments under test.

**Across all 12 runs, `tp` is 54. Every time. And all five per-scenario recalls are
bit-identical in all 12 runs** (S1 1.0, S2 0.743, S3 0.111, S4 1.0, S5 0.60). The only quantity
that moved at all was false positives, across a band of 7840–8010 — a 2.1% spread.

So the honest summary of Series I is: **no configuration under test changed a single detection.**
Five folds were ranked entirely on FP jitter at a precision of 0.0068. That result should have
been the headline finding on day one, not an outcome distributed across five separate reject
notices.

---

## What the process got right

Worth stating plainly, because these are the parts that are hard and they were done well.

1. **Reproducibility is proven.** Each cloud `ws_*` lane and its corresponding `fold_*` lane
   produced bit-identical F1, TP, FP, and per-scenario numbers on separate hosts. That rules out
   nondeterminism as an explanation for the FP deltas, which means the 7995→7840 movement is
   real signal, not noise. Most calibration harnesses cannot make this claim.
2. **The baseline anchor reproduces.** `baseline_ref` from Series E–H is
   F1 `0.01322556943423953`; `fold_02` reproduced it to the last digit. The additive chain is
   correctly anchored.
3. **Honest labeling.** Every document says *Not CALIBRATED*. No fold overclaims.
4. **Conservative defaults.** Four of five folds rejected; flags stay off.
5. **The cadence kill is properly recorded** — mechanism, query timestamp, sources, PID. That is
   how a negative result should look.
6. **Weight probes were correctly demoted** to `archival_evidence_not_gate` rather than being
   treated as authorization.

---

## What the campaign missed

### 1. The reported metrics are the two scenarios that cannot discriminate

`partition_check` gives the attack event counts:

| Scenario | Attack events | Recall | In governance headline? |
|---|---:|---:|---|
| S1 sharp misuse | **1** | 1.000 | **yes** |
| S2 slow roll | 35 | 0.743 | no |
| S3 subtle | **45** | **0.111** | no |
| S4 service abuse | **1** | 1.000 | **yes** |
| S5 patient cycle | **75** | 0.600 | no |

The governance headline table reports S1 and S4 — the two scenarios with **one attack event
each** — and omits the three scenarios carrying 155 of 157 attack events. S1 and S4 are pinned
at 1.0 in every run because they are single-event scenarios; they are structurally incapable of
distinguishing configurations.

Worse, S1 and S4 both have `drift_necessary_tp_fraction: 0.0` — they are caught by the
point-anomaly path and do not exercise drift at all. **Series I tested five drift/gating
features and reported only the two scenarios that drift cannot influence.**

### 2. The optimized metric is dominated by a path the treatments don't touch

`drift_alerts` = 31 against `fp` = 7840. F1@45 is essentially a function of point-anomaly FP
volume. Meanwhile `drift_necessary_tp_fraction` is **1.0** for S2, S3, and S5 — the drift path
carries 100% of the true positives in the three scenarios that matter.

So drift is load-bearing for detection and invisible in the headline. Any drift improvement
would have to overcome 7840 point-anomaly FPs to register as an F1 change. That is why five
consecutive folds came back "inert": not because the features do nothing, but because the
instrument cannot resolve them. `fold_06`'s own operator note concedes the shape of this —
"Stage A gates containment, not the thr=45 point-anomaly path" — and then the fold was accepted
on a thr=45 FP delta anyway.

### 3. `thr=45` is not an operating point, and was never swept

Precision 0.0068 means roughly 145 false alerts per true one. 7840 FPs against 117 positives is
not a configuration anyone would run. Every decision in Series I is a rank ordering *inside* an
unusable regime, and there is no evidence that any of it transfers to a usable one.
`anomaly_threshold: 45.0` is the single highest-leverage uncalibrated constant in the file and
no fold varied it.

### 4. Two uncontrolled confounds, both invariant across folds

- `promotion_coverage_in_window.fraction` = **0.454**. `stale_entity_days` = 550 of 1072
  scored entity-days. Given `max_profile_staleness_days: 14` gates scoring, **over half the
  evaluation window is scoring against stale profiles.**
- `blocked_entity_count` = **53 of 65 entities** (~82%), `blocked_entity_days_estimate` = 714.
  `builder.py:664` applies a `blocked_filter` to cohort histogram construction.

Because both are constant across folds, they don't bias the *comparison* — but they plausibly
dominate the *level*. Recall 0.462 may be mostly a coverage artifact. No fold could have fixed
that, and no fold acknowledged it.

### 5. The stated rationale for the whole capability expansion is contradicted by the data

`per_dimension_drift_decomposition`, identical in all 12 runs:

| Dimension | Weight | Mean delta | Mean contribution |
|---|---:|---:|---:|
| login_hour | 5 | 0.0962 | 0.48 |
| geolocation | 5 | 0.1562 | 0.78 |
| endpoint_set | 5 | **0.0000** | **0.00** |
| process_name | 20 | 0.0873 | **1.75** |
| embedding | 40 | 0.0193 | 0.77 |

**H4 — "embedding weight 40.0 dominates subtle categorical/timing drift" — is false in
practice.** Embedding's mean contribution (0.77) is *less than half* process_name's (1.75),
because its delta magnitude is 4.5× smaller. The premise that justified adding cadence, volume
delta, and geo-velocity to "diversify the spanning set" does not hold against measured data. It
was never checked before three dimensions were built on it.

Total mean raw_drift ≈ 3.78 against `drift_threshold: 5.0` — the average entity sits below
threshold, which is consistent with only 31 drift alerts firing.

---

## Two defects found

**A. `endpoint_set` drift is identically zero — in all 12 runs.**
`mean: 0.0, max: 0.0, n: 1300`. This is not a new dimension; it is one of the four original
accepted drift dimensions, carrying `weight: 5.0`, and it has contributed nothing in every run
of this campaign. Either endpoint histograms are not being populated, or the recent-vs-previous
comparison is being fed identical inputs. A `max` of exactly 0.0 across 1300 observations is not
a data property, it is a wiring failure. **This is the same class of defect as cadence, sitting
undetected in a shipped, weighted, "accepted" dimension.**

**B. Attack event reconciliation gap.**
`attack_event_count: 157` but `tp + fn = 117` in every run. 40 attack events — 25% — are absent
from the recall denominator with no stated reason. Until that is explained, every recall figure
in Series I has an unquantified 25% hole.

---

## Were the decisions right?

Given what the harness reported, yes — the arithmetic checks out in all five cases, including
the two rejections on bit-identical output and the one on a genuine FP regression
(7840→7920). `precision_gate` is the only accept and it did reduce FP by 155 with no recall
cost, which is defensible on its own terms.

But four of the five verdicts read "inert vs prior accepted baseline," and that phrase is
recorded as a property of the *feature*. On this evidence it is at least as likely to be a
property of the *measurement*. Those need to be re-litigated once the instrument can see drift —
the current reject notices will otherwise be read by the next engineer as "we tried fleet drift
and it didn't work," which is not what happened.

---

## What to do from here

Ordered. Do not run another fold until step 3 is done.

**1. Fix the two defects first.** `endpoint_set` returning identical zero and the 157-vs-117 gap
are both correctness bugs, and both silently corrupt every number above. Neither needs a sweep.

**2. Fix coverage before calibrating anything.** 0.454 in-window coverage and 82% blocked
entities are almost certainly worth more recall than every flag in Series I combined. Get
coverage near 1.0, then re-run the baseline. Expect the anchor to move — which is fine, because
the current anchor describes a half-dark system.

**3. Rebuild the instrument, then re-anchor.**
   - Report all five scenarios with their `n` in the governance headline. Drop S1/S4 from the
     decision criteria entirely, or give them more than one event each.
   - Report point-anomaly and drift metrics on separate axes. Judge drift features against
     `drift_alerts` and S2/S3/S5 recall, never against F1@45.
   - Add a rule: if `tp` is unchanged, the verdict is "no detection effect," not an FP ranking.

**4. Sweep `anomaly_threshold` as its own campaign.** Produce a full PR curve. Find where
precision reaches even 0.1. If no threshold does, that is the most important finding the project
could produce right now, and it outranks every feature flag.

**5. Then target S3.** It carries 45 of 157 attack events, sits at 0.111 recall, and 89% of its
attack activity is `early_below_threshold`. Its `attack_raised_cumulative_drift_max` is **25.6**
against a `drift_threshold` of 5.0 — the drift signal is five times the threshold and we still
catch 5 of 45. That is a timing/gating problem, not a missing-dimension problem. No new feature
was ever going to fix it, which is the real lesson of Series I.

---

## Uncalibrated constant inventory

Sweep order should follow what the instrument can currently see — which is why most of this list
is blocked behind steps 1–4 above.

**Tier 1 — blocking, sweep first**

| Constant | Current | Why |
|---|---:|---|
| `anomaly_threshold` | 45.0 | Defines an unusable operating point; never swept |
| `max_profile_staleness_days` | 14 | Directly implicated in 0.454 coverage |

**Tier 2 — high leverage, measurable once the instrument is fixed**

| Constant | Current | Why |
|---|---:|---|
| `features.drift_alert.weight` | 100.0 | 20–100× every other feature weight, never justified |
| `drift_threshold` | 5.0 | Mean raw_drift is 3.78; threshold may be set above the mass |
| `drift_weights.embedding` | 40.0 | H4 premise now contradicted — re-derive |
| `drift_weights.process_name` | 20.0 | Largest actual contributor; weight set before measurement |
| `drift_weights.endpoint_set` | 5.0 | Weighting a dimension that is identically zero |
| `features.*.rarity` weights | 1/2/2/3/2 | Drive the 7840-FP point-anomaly path |

**Tier 3 — drift internals, blocked until `drift_alerts` ≫ 31**

`drift_half_life_days` (7), `recent_drift_window_days` (3), `drift_comparison_history_count` (5),
`cohort_gate_window_days` (7), `laplace_alpha` (1.0)

**Tier 4 — gating and code constants**

`min_cohort_size` (10), `min_clean_observation_count` (5), `max_changed_fraction` (0.2),
`containment_threshold` (85.0), `confidence_floor` (0.6), `confidence_k` (10.0),
`contribution_scale_max` (50.0), `max_calendar_adjustment` (0.3), `age_jitter_hours` (4),
`precision_gate.family_floor_fraction` (0.1), `precision_gate.containment_min_agreement` (2),
`staged_drift.soft_crossing_fraction` (0.5), `gap_correlation_window` (60),
`investigation_context_window` (14)

Plus hardcoded: `cv / 0.3` in `compute_periodicity` / `compute_build_window_cadence_cov`
(DEBT-012), and `ALPHA_PROD` 0.02 / `ALPHA_ANCHOR` 0.05 / `QUIET_WINDOW_DAYS` 3 /
`MIN_DWELL_BUILDS` 2 in `core/attestation.py` (DEBT-018).

**A note on the cleanup goal:** "get rid of uncalibrated" is the right instinct but the wrong
first move. Sweeping a constant against a metric that can't see it produces a *calibrated-looking*
number with no evidential content — which is worse than an honest magic number, because it
launders the uncertainty. Fix the instrument, then sweep. Tier 3 and 4 should stay explicitly
labelled uncalibrated until there is something that can measure them.
