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

print(type(result_a))