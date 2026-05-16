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