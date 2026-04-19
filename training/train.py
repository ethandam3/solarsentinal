"""
train.py  —  SageMaker XGBoost training script
Runs inside the SageMaker managed XGBoost container.

Environment variables provided by SageMaker:
  SM_CHANNEL_TRAIN  →  directory containing training.csv
  SM_MODEL_DIR      →  where to save the model artifact

Usage (local test):
  SM_CHANNEL_TRAIN=../data SM_MODEL_DIR=../model python train.py

SageMaker launch (from upload_to_s3.py / CDK):
  estimator = sagemaker.estimator.Estimator(
      image_uri = sagemaker.image_uris.retrieve("xgboost", region, "1.7-1"),
      entry_point = "train.py",
      ...
  )
"""

import os
import json
import argparse
import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error, r2_score
import joblib

# ── SageMaker channel paths ──────────────────────────────────────────────────
TRAIN_DIR = os.environ.get("SM_CHANNEL_TRAIN", "../data")
MODEL_DIR = os.environ.get("SM_MODEL_DIR",     "../model")

# ── Hyperparameters (passed via SageMaker estimator or argparse) ─────────────
def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--n_estimators",  type=int,   default=300)
    p.add_argument("--max_depth",     type=int,   default=6)
    p.add_argument("--learning_rate", type=float, default=0.08)
    p.add_argument("--subsample",     type=float, default=0.85)
    p.add_argument("--colsample",     type=float, default=0.85)
    p.add_argument("--min_child_wt",  type=float, default=3.0)
    return p.parse_args()


FEATURES = [
    "solar_radiation_wm2",
    "outdoor_temp_f",
    "humidity_pct",
    "uv_index",
    "system_size_dc_kw",
    "tilt_deg",
    "azimuth_deg",
    "hour_local",
    "month",
]
TARGET = "expected_kwh"


def main():
    args = parse_args()
    os.makedirs(MODEL_DIR, exist_ok=True)

    # ── Load data ─────────────────────────────────────────────────────────────
    csv_path = os.path.join(TRAIN_DIR, "training.csv")
    print(f"Loading training data from {csv_path}")
    df = pd.read_csv(csv_path)
    print(f"  Shape: {df.shape}")
    print(f"  Columns: {df.columns.tolist()}")
    print(f"  Target stats:\n{df[TARGET].describe()}")

    X = df[FEATURES].values
    y = df[TARGET].values

    X_train, X_val, y_train, y_val = train_test_split(
        X, y, test_size=0.15, random_state=42
    )

    # ── Train ─────────────────────────────────────────────────────────────────
    model = xgb.XGBRegressor(
        n_estimators      = args.n_estimators,
        max_depth         = args.max_depth,
        learning_rate     = args.learning_rate,
        subsample         = args.subsample,
        colsample_bytree  = args.colsample,
        min_child_weight  = args.min_child_wt,
        objective         = "reg:squarederror",
        tree_method       = "hist",
        early_stopping_rounds = 20,
        eval_metric       = "mae",
        random_state      = 42,
    )

    print("\nFitting XGBoost…")
    model.fit(
        X_train, y_train,
        eval_set       = [(X_val, y_val)],
        verbose        = 50,
    )

    # ── Evaluate ──────────────────────────────────────────────────────────────
    preds = model.predict(X_val)
    mae   = mean_absolute_error(y_val, preds)
    r2    = r2_score(y_val, preds)
    mape  = np.mean(np.abs((y_val - preds) / np.maximum(y_val, 1e-6))) * 100

    print(f"\nValidation results:")
    print(f"  MAE  : {mae:.5f} kWh")
    print(f"  R²   : {r2:.4f}")
    print(f"  MAPE : {mape:.2f}%")

    # Feature importances
    importances = dict(zip(FEATURES, model.feature_importances_))
    print("\nFeature importances:")
    for feat, imp in sorted(importances.items(), key=lambda x: -x[1]):
        print(f"  {feat:25s}: {imp:.4f}")

    # ── Save model + metadata ─────────────────────────────────────────────────
    model_path = os.path.join(MODEL_DIR, "model.joblib")
    joblib.dump(model, model_path)
    print(f"\nModel saved → {model_path}")

    meta = {
        "features":    FEATURES,
        "target":      TARGET,
        "val_mae":     float(mae),
        "val_r2":      float(r2),
        "val_mape_pct":float(mape),
        "n_estimators":model.n_estimators,
        "best_iteration": int(model.best_iteration) if hasattr(model, "best_iteration") else None,
    }
    meta_path = os.path.join(MODEL_DIR, "metadata.json")
    with open(meta_path, "w") as f:
        json.dump(meta, f, indent=2)
    print(f"Metadata saved → {meta_path}")


if __name__ == "__main__":
    main()
