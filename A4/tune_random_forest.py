import os
import ray
import pandas as pd
from ray import tune
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import cross_val_score
import numpy as np
import time
import gc

DATA_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "covtype.csv")

def load_data():
    print("Loading dataset from local CSV...")
    df = pd.read_csv(DATA_PATH)
    print(f"Dataset shape: {df.shape}")
    y = df["target"].values
    X = df.drop(columns=["target"]).values
    print("Returning first 20,000 samples for X and y...")
    return X[:20000], y[:20000]

def train_evaluate(config, X=None, y=None):
    rf = RandomForestClassifier(
        max_depth=config["max_depth"],
        n_estimators=config["n_estimators"],
        ccp_alpha=config["ccp_alpha"],
        random_state=42,
        n_jobs=1
    )
    score = cross_val_score(rf, X, y, cv=3, scoring="accuracy")
    tune.report({"mean_accuracy": np.mean(score)})

def main():
    ray.init()
    print("Ray initialized with resources:", ray.cluster_resources())

    # Load data
    X, y = load_data()
    # Put data in object store once
    X_ref, y_ref = ray.put(X), ray.put(y)
    del X, y 
    gc.collect()

    config = {
        "max_depth": tune.grid_search([10, 20, 30]),
        "n_estimators": tune.grid_search([50, 100, 150]),
        "ccp_alpha": tune.grid_search([0.0, 0.001, 0.01])
    }

    start = time.time()
    analysis = tune.run(
        tune.with_parameters(train_evaluate, X=X_ref, y=y_ref),
        config=config,
        metric="mean_accuracy",
        mode="max",
        verbose=1,
        resources_per_trial={"cpu": 1},
        max_concurrent_trials=1,    
        raise_on_failed_trial=False,
    )
    elapsed_time = time.time() - start
    print(f"Hyperparameter tuning completed in {elapsed_time:.2f} seconds\n")
    print("Best hyperparameters found:", analysis.best_config)
    print("Best mean accuracy:", analysis.best_result["mean_accuracy"])


if __name__ == "__main__":
    main()