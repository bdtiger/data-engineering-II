import ray
import pandas as pd
from ray import tune
from sklearn.ensemble import RandomForestClassifier
from sklearn.datasets import fetch_covtype
from sklearn.model_selection import cross_val_score
import numpy as np
import time

def load_data():
    print("Loading dataset...")
    data = fetch_covtype()
    X, y = data.data[:20000], data.target[:20000]
    return X, y

def train_evaluate(config):
    X, y = load_data()
    rf = RandomForestClassifier(
        max_depth=config["max_depth"],
        n_estimators=config["n_estimators"],
        ccp_alpha=config["ccp_alpha"],
        random_state=42,
        n_jobs=1
    )
    score = cross_val_score(rf, X, y, cv=3, scoring="accuracy")
    tune.report(mean_accuracy=np.mean(score))

def main():
    ray.init()
    print("Ray initialized with resources:", ray.cluster_resources())
    
    # Load dataset
    X, y = load_data()
    
    # Baseline with default parameters
    rf_default = RandomForestClassifier(random_state=42)
    print("Default parameters:", rf_default.get_params())
    start = time.time()
    default_score = cross_val_score(rf_default, X, y, cv=3, scoring="accuracy")
    print(f"Default cross-validation accuracy: {np.mean(default_score):.4f} and runtime: {time.time() - start:.2f} seconds\n")
    
    # Hyperparameter tuning with Ray Tune
    config = {
        "max_depth": tune.grid_search([10, 20, 30]),
        "n_estimators": tune.grid_search([50, 100, 200]),
        "ccp_alpha": tune.grid_search([0.0, 0.001, 0.01])
    }

    start = time.time()
    analysis = tune.run(
        train_evaluate, 
        config=config,
        metric="mean_accuracy",
        mode="max",
        verbose=1,
        resources_per_trial={"cpu": 1}
    )
    elapsed_time = time.time() - start
    print(f"Hyperparameter tuning completed in {elapsed_time:.2f} seconds\n")
    print("Best hyperparameters found were: ", analysis.best_config)
    print("Best mean accuracy: ", analysis.best_result["mean_accuracy"])


if __name__ == "__main__":
    main()