# Random Forest Hyperparameter Tuning Report — Run 2

**Date:** 2026-05-13  
**Experiment ID:** `train_evaluate_2026-05-13_20-42-29`  
**Framework:** Ray Tune (BasicVariantGenerator / FIFOScheduler)  
**Dataset:** Local CSV — 581,012 rows × 55 columns (first 20,000 samples used)  
**Total Trials:** 27  
**Total Tuning Time:** ~168.07 seconds (~2 min 47s)  
**Cluster:** 2 CPUs across 2 nodes (192.168.2.42, 192.168.2.197)

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
| 423c9_00000 | 10 | 50 | 0.000 | 0.6486 | 2.56 |
| 423c9_00001 | 10 | 50 | 0.001 | 0.6144 | 2.49 |
| 423c9_00002 | 10 | 50 | 0.010 | 0.5724 | 2.59 |
| 423c9_00003 | 20 | 50 | 0.000 | 0.6949 | 3.74 |
| 423c9_00004 | 20 | 50 | 0.001 | 0.6248 | 4.83 |
| 423c9_00005 | 20 | 50 | 0.010 | 0.5585 | 5.01 |
| 423c9_00006 | 30 | 50 | 0.000 | 0.6999 | 3.80 |
| 423c9_00007 | 30 | 50 | 0.001 | 0.6221 | 5.77 |
| 423c9_00008 | 30 | 50 | 0.010 | 0.5497 | 5.57 |
| 423c9_00009 | 10 | 100 | 0.000 | 0.6514 | 4.89 |
| 423c9_00010 | 10 | 100 | 0.001 | 0.6182 | 4.74 |
| 423c9_00011 | 10 | 100 | 0.010 | 0.5652 | 5.14 |
| 423c9_00012 | 20 | 100 | 0.000 | 0.6971 | 7.15 |
| 423c9_00013 | 20 | 100 | 0.001 | 0.6287 | 10.13 |
| 423c9_00014 | 20 | 100 | 0.010 | 0.5593 | 9.65 |
| **423c9_00015** | **30** | **100** | **0.000** | **0.7034** | 7.87 |
| 423c9_00016 | 30 | 100 | 0.001 | 0.6243 | 10.93 |
| 423c9_00017 | 30 | 100 | 0.010 | 0.5598 | 12.54 |
| 423c9_00018 | 10 | 150 | 0.000 | 0.6524 | 6.90 |
| 423c9_00019 | 10 | 150 | 0.001 | 0.6162 | 7.46 |
| 423c9_00020 | 10 | 150 | 0.010 | 0.5718 | 7.06 |
| 423c9_00021 | 20 | 150 | 0.000 | 0.7004 | 11.27 |
| 423c9_00022 | 20 | 150 | 0.001 | 0.6301 | 14.56 |
| 423c9_00023 | 20 | 150 | 0.010 | 0.5603 | 15.08 |
| **423c9_00024** | **30** | **150** | **0.000** | **0.7038** ✅ | 11.43 |
| 423c9_00025 | 30 | 150 | 0.001 | 0.6261 | 17.16 |
| 423c9_00026 | 30 | 150 | 0.010 | 0.5585 | 16.66 |

---

## Comparison with Run 1

| Metric | Run 1 | Run 2 | Δ |
|---|---|---|---|
| Cluster CPUs | 1 | 2 | +1 |
| Total wall time | 307.83 s | 168.07 s | **−139.76 s (−45%)** |
| Best accuracy | 0.7038 | 0.7038 | 0 |
| Best config | depth=30, n=150, α=0 | depth=30, n=150, α=0 | identical |
| Max parallel trials | 1 | 2 | +1 |

Adding a second CPU node cut total tuning time nearly in half (from ~5m 7s to ~2m 47s) while producing identical results — consistent with a purely compute-bound, embarrassingly parallel workload.

---

## Notes

**Performance bottleneck warnings** were raised by Ray Tune during this run, with `callbacks.on_trial_result` and `process_trial_result` occasionally taking 0.5–1.7 s. This was not present in Run 1. The likely cause is increased result reporting overhead when two trials complete in close succession on parallel workers. Consider reducing reporting frequency or batching results if scaling to more workers.

---

*Generated from Ray Tune experiment `train_evaluate_2026-05-13_20-42-29`*
