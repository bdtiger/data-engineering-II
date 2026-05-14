# Random Forest Hyperparameter Tuning Report

**Date:** 2026-05-13  
**Framework:** Ray Tune (BasicVariantGenerator / FIFOScheduler)  
**Dataset:** Local CSV — 581,012 rows × 55 columns (first 20,000 samples used)  
**Total Trials:** 27  
**Total Tuning Time:** ~307.83 seconds (~5 min 7s)

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
| e834c_00000 | 10 | 50 | 0.000 | 0.6486 | 2.38 |
| e834c_00001 | 10 | 50 | 0.001 | 0.6144 | 2.50 |
| e834c_00002 | 10 | 50 | 0.010 | 0.5724 | 2.43 |
| e834c_00003 | 20 | 50 | 0.000 | 0.6949 | 3.66 |
| e834c_00004 | 20 | 50 | 0.001 | 0.6248 | 4.91 |
| e834c_00005 | 20 | 50 | 0.010 | 0.5585 | 4.94 |
| e834c_00006 | 30 | 50 | 0.000 | 0.6999 | 3.85 |
| e834c_00007 | 30 | 50 | 0.001 | 0.6221 | 5.62 |
| e834c_00008 | 30 | 50 | 0.010 | 0.5497 | 5.62 |
| e834c_00009 | 10 | 100 | 0.000 | 0.6514 | 4.75 |
| e834c_00010 | 10 | 100 | 0.001 | 0.6182 | 4.93 |
| e834c_00011 | 10 | 100 | 0.010 | 0.5652 | 4.83 |
| e834c_00012 | 20 | 100 | 0.000 | 0.6971 | 7.36 |
| e834c_00013 | 20 | 100 | 0.001 | 0.6287 | 9.85 |
| e834c_00014 | 20 | 100 | 0.010 | 0.5593 | 9.86 |
| **e834c_00015** | **30** | **100** | **0.000** | **0.7034** | 7.70 |
| e834c_00016 | 30 | 100 | 0.001 | 0.6243 | 11.35 |
| e834c_00017 | 30 | 100 | 0.010 | 0.5598 | 11.26 |
| e834c_00018 | 10 | 150 | 0.000 | 0.6524 | 7.15 |
| e834c_00019 | 10 | 150 | 0.001 | 0.6162 | 7.42 |
| e834c_00020 | 10 | 150 | 0.010 | 0.5718 | 7.26 |
| e834c_00021 | 20 | 150 | 0.000 | 0.7004 | 11.07 |
| e834c_00022 | 20 | 150 | 0.001 | 0.6301 | 14.95 |
| e834c_00023 | 20 | 150 | 0.010 | 0.5603 | 14.90 |
| **e834c_00024** | **30** | **150** | **0.000** | **0.7038** ✅ | 11.84 |
| e834c_00025 | 30 | 150 | 0.001 | 0.6261 | 17.06 |
| e834c_00026 | 30 | 150 | 0.010 | 0.5585 | 16.98 |

---

## Key Observations

**Effect of `max_depth`**  
Deeper trees consistently outperformed shallower ones. Accuracy improved markedly from depth 10 (~0.65) to depth 20 (~0.69–0.70) and depth 30 (~0.70), suggesting the data has complex decision boundaries that benefit from deeper splitting.

**Effect of `n_estimators`**  
More estimators provided modest but consistent gains. Going from 50 → 100 → 150 trees at max_depth=30 with ccp_alpha=0 raised accuracy from 0.6999 → 0.7034 → 0.7038. Returns were diminishing — the jump from 100 to 150 trees added only ~0.0004.

**Effect of `ccp_alpha` (pruning)**  
Any regularization via cost-complexity pruning hurt performance across all configurations. Even the lightest pruning (ccp_alpha=0.001) reduced accuracy by ~5–7 percentage points compared to no pruning, and ccp_alpha=0.01 dropped accuracy even further (~0.55–0.57). The optimal model uses no pruning.

**Top 5 Configurations**

| Rank | max_depth | n_estimators | ccp_alpha | Accuracy |
|---|---|---|---|---|
| 1 | 30 | 150 | 0.000 | 0.7038 |
| 2 | 30 | 100 | 0.000 | 0.7034 |
| 3 | 20 | 150 | 0.000 | 0.7004 |
| 4 | 30 | 50 | 0.000 | 0.6999 |
| 5 | 20 | 50 | 0.000 | 0.6949 |

---

## Recommendations

- **Use the best configuration** (`max_depth=30`, `n_estimators=150`, `ccp_alpha=0.0`) for production.
- **Consider expanding the search** to `n_estimators` values above 150 and `max_depth` beyond 30 (or `None` for unlimited depth), as the accuracy curve had not plateaued at the search boundaries.
- **Avoid pruning** (`ccp_alpha > 0`) for this dataset — it consistently degraded performance.
- **Parallelism note:** The cluster had only 1 CPU available during this run, so trials executed sequentially. Scaling to more workers would significantly reduce total tuning time.

---

*Generated from Ray Tune experiment `train_evaluate_2026-05-13_19-42-42`*
