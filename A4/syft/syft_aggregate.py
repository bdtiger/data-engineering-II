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