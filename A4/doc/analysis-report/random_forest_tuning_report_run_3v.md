# Random Forest Hyperparameter Tuning Report — Run 3

**Date:** 2026-05-13  
**Experiment ID:** `train_evaluate_2026-05-13_20-55-30`  
**Framework:** Ray Tune (BasicVariantGenerator / FIFOScheduler)  
**Dataset:** Local CSV — 581,012 rows × 55 columns (first 20,000 samples used)  
**Total Trials:** 27  
**Total Tuning Time:** ~112.84 seconds (~1 min 52s)  
**Cluster:** 3 CPUs across 3 nodes (192.168.2.42, 192.168.2.197, 192.168.2.254)

---

## Summary

| Parameter | Best Value |
|---|---|
| `max_depth` | 30 |
| `n_estimators` | 150 |
| `ccp_alpha` | 0.0 |
| **Best Mean Accuracy** | **0.7038 (70.38%)** |

---

## Search Space

| Hyperparameter | Values Explored |
|---|---|
| `max_depth` | 10, 20, 30 |
| `n_estimators` | 50, 100, 150 |
| `ccp_alpha` | 0.0, 0.001, 0.01 |

All 27 combinations were evaluated exhaustively (3 × 3 × 3 grid).

---

## Full Trial Results

| Trial | max_depth | n_estimators | ccp_alpha | Mean Accuracy | Time (s) |
|---|---|---|---|---|---|
| 13cf2_00000 | 10 | 50 | 0.000 | 0.6486 | 2.47 |
| 13cf2_00001 | 10 | 50 | 0.001 | 0.6144 | 2.10 |
| 13cf2_00002 | 10 | 50 | 0.010 | 0.5724 | 2.57 |
| 13cf2_00003 | 20 | 50 | 0.000 | 0.6949 | 3.62 |
| 13cf2_00004 | 20 | 50 | 0.001 | 0.6248 | 5.10 |
| 13cf2_00005 | 20 | 50 | 0.010 | 0.5585 | 4.87 |
| 13cf2_00006 | 30 | 50 | 0.000 | 0.6999 | 4.03 |
| 13cf2_00007 | 30 | 50 | 0.001 | 0.6221 | 5.89 |
| 13cf2_00008 | 30 | 50 | 0.010 | 0.5497 | 5.54 |
| 13cf2_00009 | 10 | 100 | 0.000 | 0.6514 | 3.34 |
| 13cf2_00010 | 10 | 100 | 0.001 | 0.6182 | 4.84 |
| 13cf2_00011 | 10 | 100 | 0.010 | 0.5652 | 5.05 |
| 13cf2_00012 | 20 | 100 | 0.000 | 0.6971 | 7.34 |
| 13cf2_00013 | 20 | 100 | 0.001 | 0.6287 | 7.08 |
| 13cf2_00014 | 20 | 100 | 0.010 | 0.5593 | 10.21 |
| **13cf2_00015** | **30** | **100** | **0.000** | **0.7034** | 7.65 |
| 13cf2_00016 | 30 | 100 | 0.001 | 0.6243 | 8.00 |
| 13cf2_00017 | 30 | 100 | 0.010 | 0.5598 | 11.80 |
| 13cf2_00018 | 10 | 150 | 0.000 | 0.6524 | 4.88 |
| 13cf2_00019 | 10 | 150 | 0.001 | 0.6162 | 7.22 |
| 13cf2_00020 | 10 | 150 | 0.010 | 0.5718 | 4.92 |
| 13cf2_00021 | 20 | 150 | 0.000 | 0.7004 | 11.27 |
| 13cf2_00022 | 20 | 150 | 0.001 | 0.6301 | 14.63 |
| 13cf2_00023 | 20 | 150 | 0.010 | 0.5603 | 10.45 |
| **13cf2_00024** | **30** | **150** | **0.000** | **0.7038** ✅ | 11.92 |
| 13cf2_00025 | 30 | 150 | 0.001 | 0.6261 | 11.98 |
| 13cf2_00026 | 30 | 150 | 0.010 | 0.5585 | 16.66 |

---

## Scaling Comparison Across All Three Runs

| Metric | Run 1 | Run 2 | Run 3 | R1→R3 Δ |
|---|---|---|---|---|
| Cluster CPUs | 1 | 2 | 3 | +2 |
| Nodes | 1 | 2 | 3 | +2 |
| Total wall time (s) | 307.83 | 168.07 | 112.84 | −195 s (−63%) |
| Max parallel trials | 1 | 2 | 3 | +2 |
| Best accuracy | 0.7038 | 0.7038 | 0.7038 | 0 |
| Best config | depth=30, n=150, α=0 | depth=30, n=150, α=0 | depth=30, n=150, α=0 | identical |

**Speedup relative to Run 1:** Run 2 was 1.83× faster; Run 3 was 2.73× faster. This is near-linear scaling for a 3× CPU increase, confirming the workload is embarrassingly parallel with minimal coordination overhead.

**Diminishing returns:** Going from 1→2 CPUs saved 139.76 s; going from 2→3 CPUs saved only 55.23 s. This is expected — the bottleneck shifts from compute to the slowest individual trial (the longest trials, around 16–17 s each, set the floor for total time regardless of parallelism).

---

## Notes

No Ray Tune callback bottleneck warnings appeared in this run, unlike Run 2. This may be due to slightly better load distribution across three workers, or timing differences in how results were processed.

---

*Generated from Ray Tune experiment `train_evaluate_2026-05-13_20-55-30`*
