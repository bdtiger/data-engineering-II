
## What Assignment 4 is actually asking

There are 3 tasks. Task 1 is mandatory (1 point), Task 2 is extra credit (1 point), Task 3 is optional (0 points). You only *need* Task 1 to pass.

**Task 1 has two parts:**
- **1.1** — Run a machine learning experiment (Random Forest on forest cover data) using distributed hyperparameter tuning with Ray Tune across 1, 2, and 3 VMs
- **1.2** — A *written/theoretical* exercise about deep learning parallelism (read some docs, do a Colab tutorial, write half a page)

**Task 2** — Simulate federated learning using PySyft on MNIST data

Let me show you the full architecture first, then the step-by-step guide.Now here is the complete step-by-step guide:

---

## What you reuse from Assignment 3

Your Assignment 3 report is extremely relevant. You already have:

- `start_instance.py` — creates VMs via OpenStack API. **Reuse this directly.**
- `cloud-cfg.txt` / CloudInit pattern — just change it to install Ray instead of Docker.
- The Ansible playbook (`configuration.yml`) — you can optionally reuse it to set up Ray on all VMs at once.
- SSH key and `appuser` setup — already works, just reuse the same pattern.
- You know how to attach floating IPs, wait for ACTIVE state, etc.

The *only* new thing is replacing Docker/Celery with Ray Tune.

---

## Task 1.1 — Step by step

### Step 1: Create the VMs (reuse your A3 script)

You need up to 3 "small" VMs. Use your existing `start_instance.py`. The only change is the CloudInit config — instead of installing Docker, you install Ray:

```yaml
# cloud-cfg-ray.txt
#cloud-config
apt_update: true
apt_upgrade: true
packages:
  - python3-pip
  - python3-dev

runcmd:
  - pip3 install ray[tune] scikit-learn --break-system-packages
```

Create 3 VMs this way. Note their **internal IPs** (not floating IPs — Ray uses internal network between VMs). Attach a floating IP only to the **head node** so you can SSH into it.

### Step 2: Start the Ray head node

SSH into VM 1 (your head node):

```bash
ray start --head --port=6379
```

Ray prints something like:
```
Ray runtime started.
Next steps: ray start --address='10.x.x.x:6379'
```

**Save that address.**

### Step 3: Connect worker VMs to the head

SSH into VM 2 and VM 3 and run:

```bash
ray start --address='10.x.x.x:6379'   # use the address from step 2
```

You now have a 3-node Ray cluster.

### Step 4: Write your Python script

This runs on the **head node**. Create `tune_forest.py`:

```python
import ray
from ray import tune
from sklearn.ensemble import RandomForestClassifier
from sklearn.datasets import fetch_covtype
from sklearn.model_selection import cross_val_score
import numpy as np

# Connect to the existing Ray cluster
ray.init(address="auto")

# Load data (each worker will do this independently)
data = fetch_covtype()
X, y = data.data, data.target

# 1. Baseline: default parameters
rf_default = RandomForestClassifier(random_state=42)
rf_default.fit(X[:10000], y[:10000])   # use a subset to save time
print("Default params:", rf_default.get_params())

# 2. Distributed hyperparameter tuning
def train_rf(config):
    clf = RandomForestClassifier(
        max_depth=config["max_depth"],
        n_estimators=config["n_estimators"],
        ccp_alpha=config["ccp_alpha"],
        random_state=42
    )
    scores = cross_val_score(clf, X[:10000], y[:10000], cv=3, scoring="accuracy")
    tune.report(mean_accuracy=np.mean(scores))

param_grid = {
    "max_depth":    tune.grid_search([5, 10, 20]),
    "n_estimators": tune.grid_search([50, 100, 200]),
    "ccp_alpha":    tune.grid_search([0.0, 0.001, 0.01]),
}

analysis = tune.run(
    train_rf,
    config=param_grid,
    metric="mean_accuracy",
    mode="max",
    verbose=1
)

print("Best config:", analysis.best_config)
print("Best accuracy:", analysis.best_result["mean_accuracy"])
```

### Step 5: Run it and record results

```bash
# First with 1 VM (stop workers on VM2, VM3 first):
time python3 tune_forest.py

# Then with 2 VMs:
# start ray on VM2, re-run
time python3 tune_forest.py

# Then with 3 VMs:
time python3 tune_forest.py
```

**Take screenshots** of the output each time — you need to show the timing and the best hyperparameters found.

### Step 6: Write up the results

Report these things:
- What default parameters `get_params()` returned
- What best `(max_depth, n_estimators, ccp_alpha)` the tuning found
- The cross-validation accuracy for default vs tuned
- The wall-clock time for 1 VM, 2 VMs, 3 VMs (use the `time` command output)

---

## Task 1.2 — Step by step (theory, no VMs)

This is just reading + a short write-up. It takes maybe 2-3 hours.

1. Read the Wikipedia page on data parallelism and the PyTorch distributed overview linked in the assignment.
2. Go to Google Colab and run the TensorFlow distributed training tutorial linked in the assignment (it's a Jupyter notebook — just click through it).
3. Write **at most half a page (11pt Arial)** answering:
   - *What is the difference between data parallelism and model parallelism?* (Data parallel = same model, different data batches on each GPU. Model parallel = model is too big for one GPU, so different layers live on different GPUs.)
   - *When is each appropriate?* (Data parallel = when model fits in one GPU but you want to go faster or use more data. Model parallel = when the model itself is too large for a single GPU, like very large LLMs.)
   - *When would you distribute individual neural network training rather than distributing hyperparameter tuning cases?* (When a single model is so large/expensive that even one training run won't finish in reasonable time on one machine.)

---

## Task 2 (Extra credit) — Step by step

This runs entirely **locally on your laptop** — no VMs needed.

### Step 1: Set up environment

```bash
# Python 3.10+ works with syft 0.8
pip install "syft>=0.8.0" torch torchvision
```

### Step 2: Write the simulation

The assignment notes warn about API version differences. Using **syft 0.8+** (recommended):

```python
import syft as sy
import torch
import torch.nn as nn
from torchvision import datasets, transforms
from torch.utils.data import DataLoader, Subset

# Launch two simulated Datasites (workers)
client_a = sy.orchestra.launch("ClientA", dev_mode=True, reset=True)
client_b = sy.orchestra.launch("ClientB", dev_mode=True, reset=True)

# Load MNIST and split it in half (non-overlapping)
transform = transforms.ToTensor()
full_dataset = datasets.MNIST(".", download=True, transform=transform)

half = len(full_dataset) // 2
dataset_a = Subset(full_dataset, range(0, half))
dataset_b = Subset(full_dataset, range(half, len(full_dataset)))

# Connect and upload data to each client
ca = client_a.login(email="admin@a.com", password="changethis")
cb = client_b.login(email="admin@b.com", password="changethis")

# ... (upload datasets as ActionObjects, define training function
#      with @sy.syft_function decorator, aggregate weights with FedAvg)
```

The key steps are: upload data to each Datasite → define a `@sy.syft_function` for local training → collect `model.state_dict()` from each → average the weights → evaluate the aggregated model vs single-client model.

### Step 3: Analysis questions to answer

- Explain how PySyft's mechanism prevents the data scientist from seeing raw data (the answer: you only get back the model weights, not the data itself — `ActionObject` wraps data so you can request computations but not read values directly)
- Compare accuracy: federated model trained on both halves vs single-client model trained on only one half
- Write the 0.5-page reflection on FL vs distributed ML (statistical heterogeneity = data distributions differ across clients in FL, unlike in distributed ML where you control the split; system heterogeneity = clients have different hardware/availability)

---

## Suggested order of attack

1. **Start with Task 1.2** — it's pure reading/writing, no setup needed. Do this first while you set up VMs.
2. **Set up VMs for Task 1.1** — reuse your `start_instance.py` from A3, just swap the CloudInit to install Ray.
3. **Run Task 1.1** — start with 1 VM first to verify your script works, then add workers.
4. **Do Task 2 locally** — no VMs, install syft locally.

The biggest difference from A3 is that instead of Flask/Celery/RabbitMQ on the VMs, you're running a **Ray cluster** — but the VM creation and SSH setup is identical to what you already did. Your A3 report even shows you know how to handle floating IPs, CloudInit, and the OpenStack API, so you're well ahead already.