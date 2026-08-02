# Scoring-config governance — Series F (2026-07-30)

**Plan:** Phases 1–2 (cadence + volume delta)  
**Status:** **Not CALIBRATED.** Sweep ran with `enabled: true` **only inside the harness**; committed YAML remains `enabled: false`.

## Headline @ thr=45

| Metric | Value |
|---|---|
| P / R / F1 | 0.0067 / 0.4615 / 0.0132 |
| TP / FP / FN | 54 / 7995 / 63 |

## Cadence dimension dominance check (H4)

| Dimension | mean delta_last_build | max | n |
|---|---:|---:|---:|
| embedding | 0.01928712627882209 | 0.1636601220715191 | 1300 |
| cadence | 0.2875928499581832 | 1.0 | 1300 |
| total_volume_delta | 0.04111765020654019 | 0.2644640753123387 | 1300 |

Cadence/embedding mean ratio: 14.911130139380576.

This sweep **reports evidence only** — it does **not** authorize flipping `enabled: true` in committed YAML.

## Cross-series rule

Compare decomposition against Series E predecessor, not Series D headline FP/P/R.
