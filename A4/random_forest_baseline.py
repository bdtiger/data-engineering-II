import os
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import cross_val_score
import numpy as np
import time

DATA_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "covtype.csv")

def load_data():
    print("Loading dataset from local CSV...")
    df = pd.read_csv(DATA_PATH)
    print(f"Dataset shape: {df.shape}")
    y = df["target"].values
    X = df.drop(columns=["target"]).values
    print("Returning first 20,000 samples for X and y...")
    return X[:20000], y[:20000]

def main():
    # Load data
    X, y = load_data()
    
    # Check if data was loaded correctly
    if X is None or y is None:
        raise ValueError("Failed to load data.")

    # Baseline with default parameters
    rf_default = RandomForestClassifier(random_state=42)
    print("\nDefault parameters:", rf_default.get_params())
    start = time.time()
    default_score = cross_val_score(rf_default, X, y, cv=3, scoring="accuracy")
    elapsed_time = time.time() - start
    print(f"Default cross-validation accuracy: {np.mean(default_score):.4f} and runtime: {elapsed_time:.2f} seconds")


if __name__ == "__main__":
    main()