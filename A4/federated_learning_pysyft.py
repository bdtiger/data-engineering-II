import time
from copy import deepcopy

import syft as sy
import torch
import torch.nn as nn
import torch.optim as optim
import torchvision
from torch.utils.data import DataLoader, Subset
from torchvision import datasets, transforms


def extract_tensors(subset):
    loader = DataLoader(subset, batch_size=len(subset))
    images, labels = next(iter(loader))
    return images, labels


def federated_average(state_dicts, weights=None):
    n = len(state_dicts)
    if weights is None:
        weights = [1.0 / n] * n
    avg = deepcopy(state_dicts[0])
    for key in avg:
        avg[key] = sum(w * sd[key].float() for w, sd in zip(weights, state_dicts))
    return avg


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


def evaluate(model, dataset, batch_size=512, label="Model"):
    model.eval()
    loader = DataLoader(dataset, batch_size=batch_size)
    correct = total = 0
    with torch.no_grad():
        for X, y in loader:
            preds = model(X).argmax(dim=1)
            correct += (preds == y).sum().item()
            total += len(y)
    acc = correct / total * 100
    print(f"{label} Accuracy: {acc:.2f}%")
    return acc


def train_local(model, subset, epochs=3, batch=256, lr=0.01, label=""):
    loader = DataLoader(subset, batch_size=batch, shuffle=True)
    opt = torch.optim.SGD(model.parameters(), lr=lr, momentum=0.9)
    crit = nn.CrossEntropyLoss()
    model.train()
    for ep in range(epochs):
        total_loss = 0.0
        for Xb, yb in loader:
            opt.zero_grad()
            loss = crit(model(Xb), yb)
            loss.backward()
            opt.step()
            total_loss += loss.item()
        print(f"[{label}] Epoch {ep+1}/{epochs} loss={total_loss:.4f}")
    return model


def main():
    node_a = sy.orchestra.launch(name="ClientA", dev_mode=True, reset=True)
    node_b = sy.orchestra.launch(name="ClientB", dev_mode=True, reset=True)

    ds_client_a = node_a.login(email="info@openmined.org", password="changethis")
    ds_client_b = node_b.login(email="info@openmined.org", password="changethis")

    transform = transforms.Compose([
        transforms.ToTensor(),
        transforms.Normalize((0.1307,), (0.3081,))
    ])

    full_train = datasets.MNIST("./data", train=True, download=True, transform=transform)
    test_dataset = datasets.MNIST("./data", train=False, download=True, transform=transform)

    n = len(full_train)
    half = n // 2

    subset_a = Subset(full_train, list(range(0, half)))
    subset_b = Subset(full_train, list(range(half, n)))

    X_a, y_a = extract_tensors(subset_a)
    X_b, y_b = extract_tensors(subset_b)

    dataset_a = sy.Dataset(
        name="mnist_client_a",
        asset_list=[
            sy.Asset(name="X", data=X_a, mock=X_a[:100]),
            sy.Asset(name="y", data=y_a, mock=y_a[:100]),
        ],
    )
    ds_client_a.upload_dataset(dataset_a)

    dataset_b = sy.Dataset(
        name="mnist_client_b",
        asset_list=[
            sy.Asset(name="X", data=X_b, mock=X_b[:100]),
            sy.Asset(name="y", data=y_b, mock=y_b[:100]),
        ],
    )
    ds_client_b.upload_dataset(dataset_b)

    X_a_ptr = ds_client_a.datasets["mnist_client_a"].assets["X"]
    y_a_ptr = ds_client_a.datasets["mnist_client_a"].assets["y"]

    X_b_ptr = ds_client_b.datasets["mnist_client_b"].assets["X"]
    y_b_ptr = ds_client_b.datasets["mnist_client_b"].assets["y"]

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

        model = SimpleCNN()
        optimizer = optim.SGD(model.parameters(), lr=0.01, momentum=0.9)
        criterion = nn.CrossEntropyLoss()

        EPOCHS = 3
        BATCH = 256
        n = X.shape[0]

        model.train()
        for epoch in range(EPOCHS):
            perm = torch.randperm(n)
            epoch_loss = 0.0
            for i in range(0, n, BATCH):
                idx = perm[i:i + BATCH]
                optimizer.zero_grad()
                loss = criterion(model(X[idx]), y[idx])
                loss.backward()
                optimizer.step()
                epoch_loss += loss.detach().item()
            print(f"[Client A] Epoch {epoch+1}/{EPOCHS} loss={epoch_loss:.4f}")

        return {k: v.detach().cpu() for k, v in model.state_dict().items()}

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

        model = SimpleCNN()
        optimizer = optim.SGD(model.parameters(), lr=0.01, momentum=0.9)
        criterion = nn.CrossEntropyLoss()

        EPOCHS = 3
        BATCH = 256
        n = X.shape[0]

        model.train()
        for epoch in range(EPOCHS):
            perm = torch.randperm(n)
            epoch_loss = 0.0
            for i in range(0, n, BATCH):
                idx = perm[i:i + BATCH]
                optimizer.zero_grad()
                loss = criterion(model(X[idx]), y[idx])
                loss.backward()
                optimizer.step()
                epoch_loss += loss.detach().item()
            print(f"[Client B] Epoch {epoch+1}/{EPOCHS} loss={epoch_loss:.4f}")

        return {k: v.detach().cpu() for k, v in model.state_dict().items()}

    request_a = ds_client_a.code.request_code_execution(train_on_client_a)
    request_b = ds_client_b.code.request_code_execution(train_on_client_b)
    print(f"Request A status: {request_a}")
    print(f"Request B status: {request_b}")

    print("Starting federated training...")
    t0 = time.time()

    result_a = ds_client_a.code.train_on_client_a(X=X_a_ptr, y=y_a_ptr).get()
    result_b = ds_client_b.code.train_on_client_b(X=X_b_ptr, y=y_b_ptr).get()

    elapsed = time.time() - t0
    print(f"Federated training time: {elapsed:.1f}s")

    global_state = federated_average([result_a, result_b], weights=[0.5, 0.5])
    global_model = SimpleCNN()
    global_model.load_state_dict(global_state)

    print("Training baseline local-only models...")

    local_model_a = SimpleCNN()
    local_model_a = train_local(local_model_a, subset_a, label="Client A")

    local_model_b = SimpleCNN()
    local_model_b = train_local(local_model_b, subset_b, label="Client B")

    fed_acc = evaluate(global_model, test_dataset, label="Federated Model (FedAvg)")
    local_a_acc = evaluate(local_model_a, test_dataset, label="Local-Only Model (Client A)")
    local_b_acc = evaluate(local_model_b, test_dataset, label="Local-Only Model (Client B)")

    print(f"Federated gain over Client A: +{fed_acc - local_a_acc:.2f}%")
    print(f"Federated gain over Client B: +{fed_acc - local_b_acc:.2f}%")

    node_a.land()
    node_b.land()
    print("Datasites shut down.")


if __name__ == "__main__":
    main()
