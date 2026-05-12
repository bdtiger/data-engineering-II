# Assignment 4: Distributed Hyperparameter Tuning with Ray Tune
**Course: Data Engineering II**

---

## Overview

The goal is to train a `RandomForestClassifier` on the forest cover dataset and tune its
hyperparameters (`max_depth`, `n_estimators`, `ccp_alpha`) using Ray Tune across 1, 2,
and 3 VMs of "small" flavor, measuring the speedup.

### VM Roles

| VM | Flavor | Role |
|---|---|---|
| Client VM | existing (from A3) | creates VMs, runs `tune_forest.py`, runs Ansible |
| VM1 small | small | Ray head — coordinates cluster + runs trials |
| VM2 small | small | Ray worker — runs trials |
| VM3 small | small | Ray worker — runs trials |

### Timing Experiments

| Experiment | Small VMs active |
|---|---|
| 1 VM | VM1 (head only, no workers) |
| 2 VMs | VM1 (head) + VM2 (worker) |
| 3 VMs | VM1 (head) + VM2 + VM3 (workers) |

---

## Phase 1: Create the 3 VMs

Reuse your `start_instance.py` from Assignment 3. Only the CloudInit config changes —
instead of Docker, you install Ray.

### CloudInit config (`cloud-cfg-ray.txt`)

Same file for all 3 VMs:

```yaml
#cloud-config

users:
  - name: appuser
    sudo: ALL=(ALL) NOPASSWD:ALL
    home: /home/appuser
    shell: /bin/bash
    ssh_authorized_keys:
      - ssh-rsa AAAA...  # paste your cluster-key.pub from A3

apt_update: true
apt_upgrade: true
packages:
 - python3-pip
 - python3-dev
 - build-essential

byobu_default: system 

runcmd:
 - pip3 install ray[tune] scikit-learn
```

> **Note:** Do not install Ray in CloudInit. Ansible handles that in Phase 2.

### Modify `start_instance.py`

Add a loop to create all 3 VMs at once:

```python
vm_names = ["ray-head", "ray-worker-1", "ray-worker-2"]
instances = []

# craeting 3 instances with the same configuration but different names.
for vm_name in vm_names:
    instance = nova.servers.create(
        name=vm_name, 
        image=image, flavor=flavor, 
        key_name='de1-course-snic-key',
        userdata=userdata, 
        nics=nics,
        security_groups=secgroups
    )
    instances.append(instance)
    print ("waiting for 10 seconds.. ")
    time.sleep(10)


for instance in instances:
    inst_status = instance.status
    print ("waiting for 10 seconds.. ")
    time.sleep(10)

    while inst_status == 'BUILD':
        print ("Instance: "+instance.name+" is in "+inst_status+" state, sleeping for 5 seconds more...")
        time.sleep(5)
        instance = nova.servers.get(instance.id)
        inst_status = instance.status

    print ("Instance: "+ instance.name +" is in " + inst_status + "state")
```

Run it from the client VM:

```bash
python3 start_instance.py
```

Note down the **internal IPs** of all 3 VMs. Attach a **floating IP only to VM1 (ray-head)**
so Ansible can reach the others via the internal network.

---

## Phase 2: Configure Ansible

Reuse the Ansible setup from Assignment 3.

### Add Ray VMs to the Ansible hosts file

```bash
sudo nano /etc/ansible/hosts
```

```ini
[rayhead]
rayhead ansible_host=<VM1-INTERNAL-IP>

[rayworkers]
rayworker1 ansible_host=<VM2-INTERNAL-IP>
rayworker2 ansible_host=<VM3-INTERNAL-IP>

[raycluster:children]
rayhead
rayworkers

[all:vars]
ansible_python_interpreter=/usr/bin/python3

[rayhead:vars]
ansible_connection=ssh ansible_user=appuser

[rayworkers:vars]
ansible_connection=ssh ansible_user=appuser
```

---

## Phase 3: Install Ray on All VMs

Create `install_ray.yml`:

```yaml
- hosts: raycluster
  become: true
  tasks:
    - name: Update apt
      apt:
        update_cache: yes
        upgrade: dist

    - name: Install pip
      apt:
        pkg: python3-pip
        state: latest

    - name: Install Ray and scikit-learn
      pip:
        name:
          - "ray[tune]"
          - scikit-learn
          - numpy
        executable: pip3
```

Run it:

```bash
ansible-playbook install_ray.yml \
    --private-key=/home/ubuntu/cluster-keys/cluster-key
```

---

## Phase 4: Ray Cluster Playbooks

You need three separate playbooks — one for each VM count experiment.

### `start_ray_1vm.yml` — head only

```yaml
- hosts: rayhead
  become: false
  tasks:
    - name: Stop any existing Ray instance
      shell: ray stop
      ignore_errors: yes

    - name: Start Ray head only
      shell: ray start --head --port=6379 --dashboard-host=0.0.0.0

    - name: Wait for head to be ready
      pause:
        seconds: 5
```

### `start_ray_2vm.yml` — head + 1 worker

```yaml
- hosts: rayhead
  become: false
  tasks:
    - name: Stop any existing Ray instance
      shell: ray stop
      ignore_errors: yes

    - name: Start Ray head
      shell: ray start --head --port=6379 --dashboard-host=0.0.0.0

    - name: Wait for head to be ready
      pause:
        seconds: 5

- hosts: rayworker1
  become: false
  tasks:
    - name: Stop any existing Ray instance
      shell: ray stop
      ignore_errors: yes

    - name: Connect worker 1 to head
      shell: ray start --address='<VM1-INTERNAL-IP>:6379'

    - name: Wait for worker to connect
      pause:
        seconds: 5
```

### `start_ray_3vm.yml` — head + 2 workers

```yaml
- hosts: rayhead
  become: false
  tasks:
    - name: Stop any existing Ray instance
      shell: ray stop
      ignore_errors: yes

    - name: Start Ray head
      shell: ray start --head --port=6379 --dashboard-host=0.0.0.0

    - name: Wait for head to be ready
      pause:
        seconds: 5

- hosts: rayworkers
  become: false
  tasks:
    - name: Stop any existing Ray instance
      shell: ray stop
      ignore_errors: yes

    - name: Connect workers to head
      shell: ray start --address='<VM1-INTERNAL-IP>:6379'

    - name: Wait for workers to connect
      pause:
        seconds: 5
```

### `stop_ray.yml` — stop all nodes

```yaml
- hosts: raycluster
  become: false
  tasks:
    - name: Stop Ray on all nodes
      shell: ray stop
      ignore_errors: yes
```

### `verify_ray.yml` — check cluster status

```yaml
- hosts: rayhead
  become: false
  tasks:
    - name: Check Ray cluster status
      shell: ray status
      register: ray_status

    - name: Print cluster status
      debug:
        msg: "{{ ray_status.stdout }}"
```

---

## Phase 5: Write the Tuning Script

Create `tune_forest.py` on the **client VM**:

```python
import ray
from ray import tune
from sklearn.ensemble import RandomForestClassifier
from sklearn.datasets import fetch_covtype
from sklearn.model_selection import cross_val_score
import numpy as np
import time

# Connect to the running Ray cluster
ray.init(address="auto")

print(f"Cluster resources: {ray.cluster_resources()}")

# Load dataset
print("Loading dataset...")
data = fetch_covtype()
X, y = data.data[:20000], data.target[:20000]  # subset to keep runtime reasonable

# ── Step 1: Baseline with default parameters ──────────────────────────────
rf_default = RandomForestClassifier(random_state=42)
print("Default parameters:", rf_default.get_params())

start = time.time()
default_scores = cross_val_score(rf_default, X, y, cv=3, scoring="accuracy")
print(f"Default CV accuracy: {np.mean(default_scores):.4f} (took {time.time()-start:.1f}s)")

# ── Step 2: Distributed Grid Search with Ray Tune ─────────────────────────
def train_evaluate(config):
    # Data loaded inside the function so Ray can ship it to any worker
    X_local, y_local = fetch_covtype(return_X_y=True)
    X_local, y_local = X_local[:20000], y_local[:20000]

    clf = RandomForestClassifier(
        max_depth=config["max_depth"],
        n_estimators=config["n_estimators"],
        ccp_alpha=config["ccp_alpha"],
        random_state=42,
        n_jobs=1   # 1 so multiple trials run in parallel on same VM
    )
    scores = cross_val_score(clf, X_local, y_local, cv=3, scoring="accuracy")
    tune.report(mean_accuracy=float(np.mean(scores)))

# 3x3x3 = 27 total combinations
search_space = {
    "max_depth":    tune.grid_search([5, 10, 20]),
    "n_estimators": tune.grid_search([50, 100, 200]),
    "ccp_alpha":    tune.grid_search([0.0, 0.001, 0.01]),
}

print("\nStarting distributed hyperparameter tuning...")
start = time.time()

analysis = tune.run(
    train_evaluate,
    config=search_space,
    metric="mean_accuracy",
    mode="max",
    verbose=1,
    resources_per_trial={"cpu": 1}  # 1 trial per CPU → maximises parallelism
)

elapsed = time.time() - start

print(f"\n── Results ──────────────────────────────────────")
print(f"Time taken:        {elapsed:.1f} seconds")
print(f"Best config:       {analysis.best_config}")
print(f"Best CV accuracy:  {analysis.best_result['mean_accuracy']:.4f}")
print(f"Default accuracy:  {np.mean(default_scores):.4f}")
```

> **Why `fetch_covtype()` is inside `train_evaluate()`?**
> Ray serializes and ships the function to worker VMs. Large data objects do not serialize
> well over the network, so each worker downloads the dataset independently instead.

---

## Phase 6: Run the Three Timing Experiments

Run all of this from the **client VM**. You never need to manually SSH into any of the 3 VMs.

```bash
# ── Experiment 1: 1 VM ────────────────────────────────────────────────────
ansible-playbook stop_ray.yml \
    --private-key=/home/ubuntu/cluster-keys/cluster-key

ansible-playbook start_ray_1vm.yml \
    --private-key=/home/ubuntu/cluster-keys/cluster-key

ansible-playbook verify_ray.yml \
    --private-key=/home/ubuntu/cluster-keys/cluster-key

time python3 tune_forest.py   # record the time output


# ── Experiment 2: 2 VMs ───────────────────────────────────────────────────
ansible-playbook stop_ray.yml \
    --private-key=/home/ubuntu/cluster-keys/cluster-key

ansible-playbook start_ray_2vm.yml \
    --private-key=/home/ubuntu/cluster-keys/cluster-key

ansible-playbook verify_ray.yml \
    --private-key=/home/ubuntu/cluster-keys/cluster-key

time python3 tune_forest.py   # record the time output


# ── Experiment 3: 3 VMs ───────────────────────────────────────────────────
ansible-playbook stop_ray.yml \
    --private-key=/home/ubuntu/cluster-keys/cluster-key

ansible-playbook start_ray_3vm.yml \
    --private-key=/home/ubuntu/cluster-keys/cluster-key

ansible-playbook verify_ray.yml \
    --private-key=/home/ubuntu/cluster-keys/cluster-key

time python3 tune_forest.py   # record the time output
```

Take a **screenshot of the terminal output** after each experiment. You need to show the
timing and the best config found.

---

## Phase 7: Clean Up

```bash
# Stop Ray on all VMs
ansible-playbook stop_ray.yml \
    --private-key=/home/ubuntu/cluster-keys/cluster-key

# Terminate the 3 VMs (add termination logic to start_instance.py or use dashboard)
python3 terminate_instances.py
```

---

## What to Report

### Question 1 — Hyperparameters and scores

| | Accuracy |
|---|---|
| Default parameters | e.g. 0.8234 |
| Best tuned (`max_depth=X, n_estimators=Y, ccp_alpha=Z`) | e.g. 0.8612 |

- State which parameters were best and why the tuned model outperforms the default.

### Question 2 — Timing comparison

| VMs | Time (seconds) |
|---|---|
| 1 VM (head only) | e.g. 480s |
| 2 VMs | e.g. 260s |
| 3 VMs | e.g. 175s |

- Speedup should be close to linear (1x → 2x → 3x) because Ray distributes independent
  trials with no communication overhead between them.
- Note: speedup will not be perfectly linear due to Ray scheduling overhead and dataset
  download time on each worker.

---

## Key Concepts to Understand

### Why a head node?

Ray Head acts as the cluster coordinator. It runs the scheduler, which:
- Generates all 27 hyperparameter combinations
- Decides which VM runs which trial
- Balances load across VMs
- Collects results and finds the best combination

Workers just execute whatever trial they are assigned. Without a head node, workers
would have no way to coordinate — they would duplicate work or skip combinations.

### Why Ray handles scheduling automatically?

You only define the search space. Ray handles everything else — generating combinations,
distributing them, collecting results. You change **zero** code between the 3 experiments.
You just add more VMs to the cluster and Ray uses them automatically.

### Why not put `ray start` in CloudInit?

CloudInit runs on all VMs simultaneously, before you know any VM's IP address. Workers
need the head's IP to connect (`ray start --address=<HEAD-IP>:6379`), but that IP is only
known after the head VM is running. Ansible solves this cleanly — it starts the head first,
waits for it to be ready, then starts workers pointing at the head's known IP.

---

## File Summary

| File | Purpose |
|---|---|
| `cloud-cfg-ray.txt` | CloudInit — installs Python/pip on all 3 VMs |
| `start_instance.py` | Creates 3 small VMs (reused from A3) |
| `install_ray.yml` | Ansible — installs Ray + scikit-learn on all VMs |
| `start_ray_1vm.yml` | Ansible — starts Ray head only |
| `start_ray_2vm.yml` | Ansible — starts head + 1 worker |
| `start_ray_3vm.yml` | Ansible — starts head + 2 workers |
| `stop_ray.yml` | Ansible — stops Ray on all VMs |
| `verify_ray.yml` | Ansible — checks cluster status |
| `tune_forest.py` | Python — runs on client VM, submits tuning job to cluster |
