# Assignment 4: Distributed Hyperparameter Tuning with Ray Tune
**Course: Data Engineering II**

---

## Overview

Train a `RandomForestClassifier` on the forest cover dataset and tune its hyperparameters
(`max_depth`, `n_estimators`, `ccp_alpha`) using Ray Tune across 1, 2, and 3 VMs of
"small" flavor, measuring the speedup.

### VM Roles

| VM | Flavor | Role |
|---|---|---|
| vm-ray-head | small | Ray head — coordinates the cluster, runs trials, holds the dataset |
| vm-ray-worker-1 | small | Ray worker — executes trials assigned by the head |
| vm-ray-worker-2 | small | Ray worker — executes trials assigned by the head |

### Timing Experiments

| Experiment | VMs active |
|---|---|
| 1 VM | vm-ray-head only (no workers) |
| 2 VMs | vm-ray-head + vm-ray-worker-1 |
| 3 VMs | vm-ray-head + vm-ray-worker-1 + vm-ray-worker-2 |

---

## Phase 1: Provision the 3 VMs

Create all three VMs manually through the cloud dashboard. Use the **"small"** flavor for
all three and name them `vm-ray-head`, `vm-ray-worker-1`, and `vm-ray-worker-2`.

Once the VMs are running:

1. Attach a **floating IP to `vm-ray-head` only** — this is the node you will SSH into and copy files to.
2. Note down the **internal IPs** of all three VMs — workers need the head's internal IP to join the cluster.

### Install packages on each VM

SSH into each VM in turn and run the same commands:

```bash
# Run on vm-ray-head, vm-ray-worker-1, and vm-ray-worker-2
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3-pip python3-dev build-essential
pip3 install "ray[tune]" scikit-learn numpy
```

For `vm-ray-head` you access it directly via its floating IP:

```bash
ssh -i <your-key> ubuntu@<HEAD-FLOATING-IP>
```

For the two workers, which have no floating IP, tunnel through the head:

```bash
ssh -i <your-key> -J ubuntu@<HEAD-FLOATING-IP> ubuntu@<WORKER-INTERNAL-IP>
```

---

## Phase 2: Download the Dataset Locally and Upload to the Head Node

Download the dataset once on your local machine, save it as a compressed file, then
upload it to `vm-ray-head`. This avoids each worker downloading it independently over
the internet during every trial.

### `download_covtype.py` — run locally

```python
import pandas as pd
from sklearn.datasets import fetch_covtype

print("Downloading forest cover dataset...")
covtype_dataset = fetch_covtype()

# Use the first 20 000 rows to keep trial runtime reasonable
feature_matrix = covtype_dataset.data[:20000]
label_vector   = covtype_dataset.target[:20000]

# Combine features and label into a single CSV
column_names = [f"feature_{i}" for i in range(feature_matrix.shape[1])] + ["label"]
covtype_df   = pd.DataFrame(
    data    = list(zip(*feature_matrix.T, label_vector)),
    columns = column_names,
)

covtype_df.to_csv("covtype_subset.csv", index=False)
print(f"Saved covtype_subset.csv  —  {len(covtype_df)} rows, {len(column_names)} columns")
```

Run it:

```bash
python3 download_covtype.py
```

This produces `covtype_subset.csv` in the current directory.

### Upload the dataset to the head node

```bash
scp -i <your-key> covtype_subset.csv ubuntu@<HEAD-FLOATING-IP>:/home/ubuntu/
```

The file now lives at `/home/ubuntu/covtype_subset.csv` on `vm-ray-head`. Workers
reach it over the internal network via Ray's object store (see `tune_forest.py`).

---

## Phase 3: Run the Baseline Script

The baseline measures default `RandomForestClassifier` accuracy **without** any
hyperparameter tuning. It runs entirely on `vm-ray-head` — no cluster needed.

### `baseline_forest.py` — copy to the head node and run there

```python
import pandas as pd
import numpy as np
import time
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import cross_val_score

DATASET_PATH = "/home/ubuntu/covtype_subset.csv"

# ── Load dataset ──────────────────────────────────────────────────────────────
print("Loading dataset from local file...")
covtype_df     = pd.read_csv(DATASET_PATH)
feature_matrix = covtype_df.drop(columns=["label"]).values
label_vector   = covtype_df["label"].values
print(f"Dataset loaded  —  X: {feature_matrix.shape}, y: {label_vector.shape}")

# ── Baseline: default RandomForestClassifier ──────────────────────────────────
default_clf = RandomForestClassifier(random_state=42)
print("\nDefault hyperparameters:", default_clf.get_params())

timer_start     = time.time()
baseline_scores = cross_val_score(default_clf, feature_matrix, label_vector,
                                  cv=3, scoring="accuracy")
timer_elapsed   = time.time() - timer_start

print(f"\nBaseline CV accuracy : {np.mean(baseline_scores):.4f}")
print(f"Elapsed time         : {timer_elapsed:.1f} seconds")
```

Copy and run:

```bash
scp -i <your-key> baseline_forest.py ubuntu@<HEAD-FLOATING-IP>:/home/ubuntu/
ssh -i <your-key> ubuntu@<HEAD-FLOATING-IP> "python3 /home/ubuntu/baseline_forest.py"
```

Note down the printed accuracy — you will compare it against the tuned result.

---

## Phase 4: Start the Ray Cluster Manually

SSH into `vm-ray-head` and start the head node:

```bash
ssh -i <your-key> rayuser@<HEAD-FLOATING-IP>

# On vm-ray-head:
ray stop                        # clear any leftover Ray process
ray start --head --port=6379 --dashboard-host=0.0.0.0
```

For the **2-VM** and **3-VM** experiments, SSH into each worker and connect it to the head:

```bash
# On vm-ray-worker-1:
ray stop
ray start --address='<HEAD-INTERNAL-IP>:6379'

# On vm-ray-worker-2 (3-VM experiment only):
ray stop
ray start --address='<HEAD-INTERNAL-IP>:6379'
```

Verify the cluster from the head node:

```bash
ray status
```

The output should list 1, 2, or 3 nodes depending on the experiment.

---

## Phase 5: Hyperparameter Tuning Script

This script connects to the running Ray cluster, loads the dataset from the local file
on the head node, and distributes the 27-combination grid search across all available
workers. **You run it on `vm-ray-head` for all three experiments without changing a
single line of code** — just add or remove workers before running.

### `tune_forest.py`

```python
import ray
from ray import tune
import pandas as pd
import numpy as np
import time
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import cross_val_score

DATASET_PATH = "/home/ubuntu/covtype_subset.csv"
NUM_CV_FOLDS = 3

# ── Connect to the running Ray cluster ────────────────────────────────────────
ray.init(address="auto")
print(f"Cluster resources: {ray.cluster_resources()}")

# ── Pre-load dataset on the head node and store in Ray object store ───────────
# Storing in the object store avoids each worker reading from disk independently.
print("Loading dataset...")
covtype_df     = pd.read_csv(DATASET_PATH)
feature_matrix = covtype_df.drop(columns=["label"]).values
label_vector   = covtype_df["label"].values

dataset_ref = ray.put({"X": feature_matrix, "y": label_vector})
print(f"Dataset stored in Ray object store  —  X: {feature_matrix.shape}")

# ── Trial function ─────────────────────────────────────────────────────────────
def evaluate_hyperparams(trial_config):
    """Called by Ray Tune once per hyperparameter combination."""
    shared_data    = ray.get(trial_config["dataset_ref"])
    trial_features = shared_data["X"]
    trial_labels   = shared_data["y"]

    forest_clf = RandomForestClassifier(
        max_depth    = trial_config["max_depth"],
        n_estimators = trial_config["n_estimators"],
        ccp_alpha    = trial_config["ccp_alpha"],
        random_state = 42,
        n_jobs       = 1,   # keep to 1 so multiple trials run in parallel on the same VM
    )
    fold_scores = cross_val_score(forest_clf, trial_features, trial_labels,
                                  cv=NUM_CV_FOLDS, scoring="accuracy")
    tune.report(mean_accuracy=float(np.mean(fold_scores)))

# ── Search space: 3 × 3 × 3 = 27 combinations ────────────────────────────────
hyperparam_grid = {
    "dataset_ref" : dataset_ref,
    "max_depth"   : tune.grid_search([5, 10, 20]),
    "n_estimators": tune.grid_search([50, 100, 200]),
    "ccp_alpha"   : tune.grid_search([0.0, 0.001, 0.01]),
}

# ── Run distributed grid search ───────────────────────────────────────────────
print("\nStarting distributed hyperparameter tuning...")
tuning_start = time.time()

tuning_results = tune.run(
    evaluate_hyperparams,
    config              = hyperparam_grid,
    metric              = "mean_accuracy",
    mode                = "max",
    verbose             = 1,
    resources_per_trial = {"cpu": 1},  # 1 CPU per trial → maximises parallelism
)

tuning_elapsed = time.time() - tuning_start

# ── Report ────────────────────────────────────────────────────────────────────
optimal_config   = tuning_results.best_config
optimal_accuracy = tuning_results.best_result["mean_accuracy"]

print(f"\n── Results ───────────────────────────────────────────")
print(f"Time taken        : {tuning_elapsed:.1f} seconds")
print(f"Best hyperparams  : max_depth={optimal_config['max_depth']}, "
      f"n_estimators={optimal_config['n_estimators']}, "
      f"ccp_alpha={optimal_config['ccp_alpha']}")
print(f"Best CV accuracy  : {optimal_accuracy:.4f}")
```

Copy it to the head node:

```bash
scp -i <your-key> tune_forest.py ubuntu@<HEAD-FLOATING-IP>:/home/ubuntu/
```

---

## Phase 6: Run the Three Timing Experiments

All commands run from inside an SSH session on `vm-ray-head`.

```bash
# ── Experiment 1: 1 VM (head only) ────────────────────────────────────────────
# Workers are stopped; only the head runs trials.
ray stop
ray start --head --port=6379 --dashboard-host=0.0.0.0
ray status                                   # confirm: 1 node

time python3 /home/ubuntu/tune_forest.py    # record elapsed time


# ── Experiment 2: 2 VMs ────────────────────────────────────────────────────────
# Start head, then SSH to vm-ray-worker-1 and connect it.
ray stop
ray start --head --port=6379 --dashboard-host=0.0.0.0
# (in a second terminal) ssh into vm-ray-worker-1:
#   ray stop && ray start --address='<HEAD-INTERNAL-IP>:6379'
ray status                                   # confirm: 2 nodes

time python3 /home/ubuntu/tune_forest.py    # record elapsed time


# ── Experiment 3: 3 VMs ────────────────────────────────────────────────────────
# Start head, then connect both workers.
ray stop
ray start --head --port=6379 --dashboard-host=0.0.0.0
# (terminal 2) ssh into vm-ray-worker-1:
#   ray stop && ray start --address='<HEAD-INTERNAL-IP>:6379'
# (terminal 3) ssh into vm-ray-worker-2:
#   ray stop && ray start --address='<HEAD-INTERNAL-IP>:6379'
ray status                                   # confirm: 3 nodes

time python3 /home/ubuntu/tune_forest.py    # record elapsed time
```

Take a **screenshot of the terminal output** after each experiment showing the timing,
best hyperparameters, and best accuracy.

---

## Phase 7: Clean Up

```bash
# Stop Ray on all nodes (run on each VM)
ray stop

# Terminate the VMs through the cloud dashboard or Nova API
```

---

## What to Report

### Question 1 — Hyperparameters and scores

| | Accuracy |
|---|---|
| Default parameters (baseline) | e.g. 0.8234 |
| Best tuned (`max_depth=X, n_estimators=Y, ccp_alpha=Z`) | e.g. 0.8612 |

State which parameters were best and explain why the tuned model outperforms the default.

### Question 2 — Timing comparison

| VMs | Time (seconds) |
|---|---|
| 1 VM (head only) | e.g. 480 s |
| 2 VMs | e.g. 260 s |
| 3 VMs | e.g. 175 s |

Speedup should be close to linear (1× → 2× → 3×) because Ray distributes independent
trials with no communication overhead between them. Minor deviations are expected due to
Ray scheduling overhead and object-store transfer latency.

---

## Key Concepts

### Why a head node?

The Ray head acts as cluster coordinator. It runs the scheduler, which generates all 27
hyperparameter combinations, decides which VM runs which trial, balances load across
nodes, and collects results to find the best combination. Workers simply execute whatever
trial they are assigned; without a head they would have no way to coordinate.

### Why does Ray need no code changes between experiments?

You define only the search space. Ray generates combinations, distributes them, and
collects results automatically. Adding more nodes to the cluster is the only change
between experiments — `tune_forest.py` is identical in all three runs.

### Why store the dataset in the Ray object store?

`ray.put()` places the dataset in shared memory on the head node. Workers fetch it over
the internal network once and cache it locally. This is faster and more reliable than
each trial downloading the dataset from the internet (the original approach), and avoids
repeated disk reads.

### Why upload the dataset manually instead of fetching inside each trial?

Fetching inside `train_evaluate()` means every trial downloads ~100 MB from scikit-learn's
CDN, serially at the start of each trial. Pre-loading it locally and storing it in the
Ray object store means each worker downloads it exactly once from the head over the fast
internal network.

---

## File Summary

| File | Where it runs | Purpose |
|---|---|---|
| `download_covtype.py` | Local machine | Downloads the dataset and saves `covtype_subset.csv` |
| `baseline_forest.py` | vm-ray-head | Measures accuracy with default RandomForestClassifier parameters |
| `tune_forest.py` | vm-ray-head | Connects to Ray cluster, runs distributed grid search, reports best result |
