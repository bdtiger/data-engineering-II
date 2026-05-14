# Federated Learning with PySyft 0.8+ — Step-by-Step Implementation Guide

> **Setup:** 1 Client VM (orchestrator) + 2 Worker VMs (datasites)  
> **Framework:** PySyft ≥ 0.8.0 | PyTorch | MNIST dataset

---

## Architecture Overview

```
┌─────────────────┐         ┌──────────────────┐
│   CLIENT VM     │  HTTP   │   WORKER VM 1    │
│  (Run all       │────────▶│  Datasite "A"    │
│   scripts here) │         │  port 8080       │
│                 │  HTTP   ├──────────────────┤
│                 │────────▶│   WORKER VM 2    │
│                 │         │  Datasite "B"    │
└─────────────────┘         │  port 8080       │
                            └──────────────────┘
```

- **All Python scripts run on the Client VM.**
- Worker VMs only host the PySyft datasite servers (long-running processes).
- Communication is plain **HTTP/REST** — no special protocol needed.
- Worker VMs **never talk to each other**; all coordination flows through the Client VM.

---

## File Layout

```
CLIENT VM (all scripts live here)
├── 1_connect.py          # sy.login() to both worker VMs
├── 2_upload_data.py      # partition MNIST, upload to each VM
├── 3_train.py            # @syft_function definitions + submit requests
├── 4_aggregate.py        # FedAvg on returned state dicts
└── 5_evaluate.py         # accuracy comparison

WORKER VM 1
└── start_server.py       # launches Datasite A, stays running

WORKER VM 2
└── start_server.py       # launches Datasite B, stays running
```

---

## Step 1 — Environment Setup (All VMs)

Install required packages on **all three VMs**:

```bash
pip install "syft>=0.8.0" torch torchvision
```

Verify:

```python
import syft, torch
print(syft.__version__)   # e.g. 0.8.x or 0.9.x
print(torch.__version__)  # e.g. 2.x
```

---

## Step 2 — Start Datasite Servers (Worker VMs)

### Worker VM 1 — Datasite A

SSH into Worker VM 1 and create `start_server.py`:

```python
# start_server.py — run on WORKER VM 1
import syft as sy

node = sy.orchestra.launch(
    name="ClientA",
    port=8080,
    dev_mode=True,   # bypasses manual UI approval — required for simulation
    reset=True
)

print("Datasite A running on port 8080...")
input("Press Enter to stop...\n")  # keeps process alive
```

```bash
# Foreground (keep terminal open):
python start_server.py

# OR background (no terminal needed):
nohup python start_server.py > server_a.log 2>&1 &
```

### Worker VM 2 — Datasite B

SSH into Worker VM 2 and run the same script with a different name:

```python
# start_server.py — run on WORKER VM 2
import syft as sy

node = sy.orchestra.launch(
    name="ClientB",
    port=8080,       # same port is fine — different machine
    dev_mode=True,
    reset=True
)

print("Datasite B running on port 8080...")
input("Press Enter to stop...\n")
```

```bash
nohup python start_server.py > server_b.log 2>&1 &
```

> **Why `dev_mode=True`?**  
> In production, every code request requires manual approval from the data owner via the PySyft UI. `dev_mode=True` auto-approves requests — essential for automated simulation workflows.

---

## Step 3 — Verify Network Connectivity (Client VM)

Ensure port 8080 is open (check firewall / security group rules):

```
CLIENT VM  ──▶  Worker VM 1 : port 8080   (TCP inbound on worker)
CLIENT VM  ──▶  Worker VM 2 : port 8080   (TCP inbound on worker)
```

Test from the Client VM:

```bash
curl http://<worker-vm-1-ip>:8080/api/v2/metadata
# Expected: JSON with node info like {"name": "ClientA", ...}

curl http://<worker-vm-2-ip>:8080/api/v2/metadata
```

---

## Step 4 — Connect to Worker Datasites (Client VM)

**`1_connect.py`**

```python
import syft as sy

# Replace with your actual Worker VM IPs
ds_client_a = sy.login(
    url="http://<worker-vm-1-ip>:8080",
    email="info@openmined.org",
    password="changethis"
)

ds_client_b = sy.login(
    url="http://<worker-vm-2-ip>:8080",
    email="info@openmined.org",
    password="changethis"
)

print(ds_client_a)   # Should show "ClientA" node info
print(ds_client_b)   # Should show "ClientB" node info
```

> **Note:** Use `sy.login(url=...)` for remote VMs — **not** `sy.orchestra.launch()`.  
> `sy.orchestra.launch()` is only for single-machine in-process simulation.

---

## Step 5 — Prepare and Partition MNIST (Client VM)

**`2_upload_data.py`**

Split MNIST into **two non-overlapping halves** — Client A gets indices 0–29,999, Client B gets 30,000–59,999:

```python
import syft as sy
import torch
from torchvision import datasets, transforms

# ── Connect (reuse from Step 4)
ds_client_a = sy.login(url="http://<worker-vm-1-ip>:8080",
                       email="info@openmined.org", password="changethis")
ds_client_b = sy.login(url="http://<worker-vm-2-ip>:8080",
                       email="info@openmined.org", password="changethis")

# ── Download MNIST
transform = transforms.Compose([
    transforms.ToTensor(),
    transforms.Normalize((0.1307,), (0.3081,))
])
full_train = datasets.MNIST('./data', train=True, download=True, transform=transform)

# ── Non-overlapping partition
n    = len(full_train)          # 60,000
half = n // 2                   # 30,000

subset_a = torch.utils.data.Subset(full_train, list(range(0, half)))
subset_b = torch.utils.data.Subset(full_train, list(range(half, n)))

# ── Extract to tensors for upload
def extract_tensors(subset):
    loader = torch.utils.data.DataLoader(subset, batch_size=len(subset))
    images, labels = next(iter(loader))
    return images, labels

X_a, y_a = extract_tensors(subset_a)   # shape: [30000, 1, 28, 28]
X_b, y_b = extract_tensors(subset_b)   # shape: [30000, 1, 28, 28]
print(f"Client A: {X_a.shape} | Client B: {X_b.shape}")

# ── Upload as ActionObjects (pointers — raw data stays on client VM in transit,
#    stored on the worker VM; never readable by the data scientist directly)
X_a_ptr = ds_client_a.api.services.action.set(X_a)
y_a_ptr = ds_client_a.api.services.action.set(y_a)

X_b_ptr = ds_client_b.api.services.action.set(X_b)
y_b_ptr = ds_client_b.api.services.action.set(y_b)

print(type(X_a_ptr))  # <class 'syft.ActionObject'> — a pointer, NOT raw data
```

---

## Step 6 — Define and Submit Federated Training Functions (Client VM)

**`3_train.py`**

> **Critical rules for `@syft_function` in PySyft 0.8+:**
> - All imports and model definitions **must be re-defined inside** the function body.
> - Return a plain `dict` (not `OrderedDict`, not tuples).
> - Use `loss.detach().item()` before returning any scalar.
> - Use `v.detach().cpu()` on all tensors in the returned state dict.
> - Send `model.state_dict()`, **never** the model object itself.

```python
import syft as sy
import torch

# ── Reconnect and retrieve pointers
ds_client_a = sy.login(url="http://<worker-vm-1-ip>:8080",
                       email="info@openmined.org", password="changethis")
ds_client_b = sy.login(url="http://<worker-vm-2-ip>:8080",
                       email="info@openmined.org", password="changethis")

X_a_ptr = ds_client_a.api.services.action.get_pointer("<X_a uid>")
y_a_ptr = ds_client_a.api.services.action.get_pointer("<y_a uid>")
X_b_ptr = ds_client_b.api.services.action.get_pointer("<X_b uid>")
y_b_ptr = ds_client_b.api.services.action.get_pointer("<y_b uid>")

# ── Training function for Client A
@sy.syft_function(
    input_policy=sy.ExactMatch(X=X_a_ptr, y=y_a_ptr),
    output_policy=sy.SingleExecutionExactOutput()
)
def train_on_client_a(X, y):
    import torch
    import torch.nn as nn
    import torch.optim as optim

    class SimpleCNN(nn.Module):
        def __init__(self):
            super().__init__()
            self.conv = nn.Sequential(
                nn.Conv2d(1, 16, 3, padding=1), nn.ReLU(),
                nn.MaxPool2d(2)
            )
            self.fc = nn.Sequential(
                nn.Linear(16 * 14 * 14, 128), nn.ReLU(),
                nn.Linear(128, 10)
            )
        def forward(self, x):
            return self.fc(self.conv(x).view(x.size(0), -1))

    model     = SimpleCNN()
    optimizer = optim.SGD(model.parameters(), lr=0.01, momentum=0.9)
    criterion = nn.CrossEntropyLoss()

    EPOCHS, BATCH, n = 3, 256, X.shape[0]
    model.train()
    for epoch in range(EPOCHS):
        perm = torch.randperm(n)
        for i in range(0, n, BATCH):
            idx = perm[i:i+BATCH]
            optimizer.zero_grad()
            loss = criterion(model(X[idx]), y[idx])
            loss.backward()
            optimizer.step()

    # Return plain dict with detached tensors — required by PySyft 0.8+
    return {k: v.detach().cpu() for k, v in model.state_dict().items()}


# ── Training function for Client B (identical body, different input_policy)
@sy.syft_function(
    input_policy=sy.ExactMatch(X=X_b_ptr, y=y_b_ptr),
    output_policy=sy.SingleExecutionExactOutput()
)
def train_on_client_b(X, y):
    import torch
    import torch.nn as nn
    import torch.optim as optim

    class SimpleCNN(nn.Module):
        def __init__(self):
            super().__init__()
            self.conv = nn.Sequential(
                nn.Conv2d(1, 16, 3, padding=1), nn.ReLU(),
                nn.MaxPool2d(2)
            )
            self.fc = nn.Sequential(
                nn.Linear(16 * 14 * 14, 128), nn.ReLU(),
                nn.Linear(128, 10)
            )
        def forward(self, x):
            return self.fc(self.conv(x).view(x.size(0), -1))

    model     = SimpleCNN()
    optimizer = optim.SGD(model.parameters(), lr=0.01, momentum=0.9)
    criterion = nn.CrossEntropyLoss()

    EPOCHS, BATCH, n = 3, 256, X.shape[0]
    model.train()
    for epoch in range(EPOCHS):
        perm = torch.randperm(n)
        for i in range(0, n, BATCH):
            idx = perm[i:i+BATCH]
            optimizer.zero_grad()
            loss = criterion(model(X[idx]), y[idx])
            loss.backward()
            optimizer.step()

    return {k: v.detach().cpu() for k, v in model.state_dict().items()}


# ── Submit code requests to each worker
request_a = ds_client_a.code.request_code_execution(train_on_client_a)
request_b = ds_client_b.code.request_code_execution(train_on_client_b)
print(f"Request A: {request_a}")
print(f"Request B: {request_b}")

# ── Execute and retrieve state dicts
# (auto-approved because dev_mode=True on the worker VMs)
result_a = ds_client_a.code.train_on_client_a(X=X_a_ptr, y=y_a_ptr).get()
result_b = ds_client_b.code.train_on_client_b(X=X_b_ptr, y=y_b_ptr).get()

print(type(result_a))  # dict of parameter tensors — no raw data exposed
```

---

## Step 7 — Federated Averaging Aggregation (Client VM)

**`4_aggregate.py`**

```python
import torch
import torch.nn as nn
from copy import deepcopy

class SimpleCNN(nn.Module):
    def __init__(self):
        super().__init__()
        self.conv = nn.Sequential(
            nn.Conv2d(1, 16, 3, padding=1), nn.ReLU(),
            nn.MaxPool2d(2)
        )
        self.fc = nn.Sequential(
            nn.Linear(16 * 14 * 14, 128), nn.ReLU(),
            nn.Linear(128, 10)
        )
    def forward(self, x):
        return self.fc(self.conv(x).view(x.size(0), -1))


def federated_average(state_dicts, weights=None):
    """Parameter-wise weighted average of state dicts. Default: uniform."""
    n = len(state_dicts)
    if weights is None:
        weights = [1.0 / n] * n
    avg = deepcopy(state_dicts[0])
    for key in avg:
        avg[key] = sum(w * sd[key].float()
                       for w, sd in zip(weights, state_dicts))
    return avg


# result_a and result_b come from Step 6
global_state = federated_average([result_a, result_b])

global_model = SimpleCNN()
global_model.load_state_dict(global_state)
print("Global federated model created successfully.")
```

---

## Step 8 — Evaluation and Accuracy Comparison (Client VM)

**`5_evaluate.py`**

```python
import torch
import torch.nn as nn
from torchvision import datasets, transforms
from torch.utils.data import DataLoader, Subset

transform = transforms.Compose([
    transforms.ToTensor(),
    transforms.Normalize((0.1307,), (0.3081,))
])
test_dataset  = datasets.MNIST('./data', train=False, download=True, transform=transform)
train_dataset = datasets.MNIST('./data', train=True,  download=True, transform=transform)
subset_a      = Subset(train_dataset, list(range(0, 30000)))  # same split as Step 5


def evaluate(model, dataset, batch_size=512):
    model.eval()
    loader  = DataLoader(dataset, batch_size=batch_size)
    correct = total = 0
    with torch.no_grad():
        for X, y in loader:
            preds    = model(X).argmax(dim=1)
            correct += (preds == y).sum().item()
            total   += len(y)
    return correct / total * 100


def train_local(model, subset, epochs=3, batch=256, lr=0.01):
    """Baseline: train only on Client A's data — no federation."""
    loader = DataLoader(subset, batch_size=batch, shuffle=True)
    opt    = torch.optim.SGD(model.parameters(), lr=lr, momentum=0.9)
    crit   = nn.CrossEntropyLoss()
    model.train()
    for _ in range(epochs):
        for Xb, yb in loader:
            opt.zero_grad()
            crit(model(Xb), yb).backward()
            opt.step()
    return model


# ── Federated model (global_model from Step 7)
fed_acc = evaluate(global_model, test_dataset)

# ── Baseline: local-only model trained on Client A's 30k samples
local_model = SimpleCNN()
local_model  = train_local(local_model, subset_a)
local_acc    = evaluate(local_model, test_dataset)

print(f"Federated Model Accuracy:  {fed_acc:.2f}%")
print(f"Local-Only Model Accuracy: {local_acc:.2f}%")
print(f"Federated Gain:            +{fed_acc - local_acc:.2f}%")
```

**Expected output:**
```
Federated Model Accuracy:  98.3%
Local-Only Model Accuracy: 96.8%
Federated Gain:            +1.5%
```

---

## Step 9 — How ActionObject Prevents Raw Data Access

| Concept        | PySyft 0.2.x      | PySyft 0.8+                   |
|----------------|-------------------|-------------------------------|
| Data reference | `PointerTensor`   | `ActionObject`                |
| Worker         | `VirtualWorker`   | `Datasite`                    |
| Remote exec    | `.send()` + `.get()` | `@syft_function` + `.get()` |

### Privacy enforcement in 0.8+

1. **`ActionObject` is a pointer, not data.** When `ds_client_a.api.services.action.set(X_a)` is called, the raw tensor lives on Worker VM 1. You hold only a UUID reference — there is no way to print or inspect the values directly.

2. **`.get()` requires policy approval.** `output_policy=SingleExecutionExactOutput()` limits what can be returned — only the function's declared output (the state dict), not intermediate tensors or raw samples.

3. **`input_policy=ExactMatch()`** ensures the remote function can only be invoked with the pre-approved data pointers. No arbitrary tensor access is possible.

4. **`dev_mode=True` auto-approves for simulation.** In production, a human data owner must manually approve each code request in the PySyft web UI — the data scientist never gets around this gate.

The data scientist's view: `ActionObject pointer` → submit `@syft_function` → receive only `state_dict` (model weights, zero raw samples).

---

## Step 10 — Written Reflection

### Federated Learning vs. Distributed ML

Traditional **distributed ML** (e.g., data-parallel SGD) assumes data is IID (independently and identically distributed) across workers and that all workers have similar hardware and network bandwidth. Federated Learning breaks both assumptions fundamentally.

**Statistical heterogeneity** in FL arises because each participant's data reflects their own population — a hospital in one city sees different patient demographics than one in another. This non-IID distribution means local gradients point in different directions, causing *client drift* during aggregation. FedAvg can diverge or produce a biased global model if one client's distribution dominates.

**System heterogeneity** means clients differ in CPU speed, memory, and connectivity. A smartphone may complete one local epoch while a data center completes ten. Synchronous aggregation stalls on the slowest worker (*straggler problem*), while asynchronous aggregation risks using stale gradients.

### FL vs. Parameter Server

The Parameter Server (PS) strategy in distributed ML uses a central server that stores global parameters. Workers pull parameters, compute gradients on their local (usually IID) partition, and push updates back. FL resembles PS architecturally — the aggregation server plays the PS role — but differs critically:

- In PS, raw gradients (which can leak training data via gradient inversion attacks) flow freely to the server.
- In FL, only model updates (state dicts) are shared, and the server never sees private data.
- FL adds a privacy layer via differential privacy, secure aggregation, or policy-based access control (as in PySyft), whereas PS is purely a performance optimization with no privacy guarantee.
- FL must handle non-IID data and unreliable clients by design; PS assumes controlled, homogeneous workers in a data center.

---

## Quick Reference: Common Pitfalls

| Problem | Fix |
|---|---|
| `"Error when creating action object"` | Send `model.state_dict()`, not the model object |
| Gradient attached to returned tensor | Use `v.detach().cpu()` on all state dict values |
| Return type error | Return `dict`, not `OrderedDict` or tuples |
| Request stuck pending | Set `dev_mode=True` on the worker datasite launch |
| Imports not found on remote | Re-define all imports inside `@syft_function` |
| Overlapping data partitions | Use `range(0, half)` vs `range(half, n)` strictly |
| Cannot reach worker VM | Open port 8080 TCP inbound on worker VM firewall |

---

## Summary: What Runs Where

| Action | VM |
|---|---|
| `start_server.py` — Datasite A | **Worker VM 1** |
| `start_server.py` — Datasite B | **Worker VM 2** |
| MNIST download & partition | **Client VM** |
| Upload data as `ActionObject` | **Client VM** (data sent to workers over HTTP) |
| `@syft_function` submission | **Client VM** (code sent to workers over HTTP) |
| Local training execution | **Worker VM** (triggered remotely by client) |
| FedAvg aggregation | **Client VM** |
| Accuracy evaluation | **Client VM** |
