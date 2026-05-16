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