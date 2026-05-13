import ray
import pandas as pd
from ray import tune
from sklearn.ensemble import RandomForestClassifier
from sklearn.datasets import fetch_covtype
from sklearn.model_selection import cross_val_score
import numpy as np
import time

def main():
    # Load dataset
    print("Loading dataset...")
    data = fetch_covtype()
    X, y = data.data, data.target  # subset to keep runtime reasonable
    df = pd.DataFrame(X, columns=data.feature_names)
    print(df.info())

    # Baseline with default parameters
    rf_default = RandomForestClassifier(random_state=42)
    print("Default parameters:", rf_default.get_params())
    start = time.time()
    default_score = cross_val_score(rf_default, X, y, cv=3, scoring="accuracy")
    print(f"Default cross-validation accuracy: {np.mean(default_score):.4f} and runtime: {time.time() - start:.2f} seconds")


if __name__ == "__main__":
    main()