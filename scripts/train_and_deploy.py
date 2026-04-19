"""
train_and_deploy.py
Replaces upload_to_s3.py + deploy_endpoint.py.
Does everything with boto3 only — no sagemaker SDK required.

Steps:
  1. Train XGBoost locally on data/training.csv  (~5 seconds)
  2. Package model as model.tar.gz
  3. Upload model artifact + demo data to S3
  4. Create SageMaker Model + EndpointConfig + Endpoint via boto3
     (endpoint name: solarsentinel-predictor — matches Lambda env var)
"""

import os, json, tarfile, time
import boto3, numpy as np, pandas as pd
from pathlib import Path
from xgboost import XGBRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error, r2_score

ACCOUNT   = "437982993480"
REGION    = "us-east-1"
DATA_DIR  = Path(r"C:\Users\ethan\solarsentinel\data")
TRAIN_DIR = Path(r"C:\Users\ethan\solarsentinel\training")

RAW_BUCKET      = f"solarsentinel-raw-irradiance-{ACCOUNT}"
TRAINING_BUCKET = f"solarsentinel-training-{ACCOUNT}"
SAGEMAKER_ROLE  = f"arn:aws:iam::{ACCOUNT}:role/solarsentinel-sagemaker-role"
ENDPOINT_NAME   = "solarsentinel-predictor"

# XGBoost 1.7-1 container in us-east-1 (no sagemaker SDK needed)
XGB_IMAGE = "683313688378.dkr.ecr.us-east-1.amazonaws.com/sagemaker-xgboost:1.7-1-cpu-py3"

FEATURES = [
    "solar_radiation_wm2", "outdoor_temp_f", "humidity_pct",
    "uv_index", "system_size_dc_kw", "tilt_deg", "azimuth_deg",
    "hour_local", "month",
]
TARGET = "expected_kwh"


# ── Step 1: Train locally ─────────────────────────────────────────────────────
def train():
    print("Loading training.csv ...")
    df = pd.read_csv(DATA_DIR / "training.csv")
    print(f"  {len(df)} rows, {len(df.columns)} columns")

    X = df[FEATURES].values
    y = df[TARGET].values
    X_train, X_val, y_train, y_val = train_test_split(X, y, test_size=0.15, random_state=42)

    print("Training XGBoost ...")
    model = XGBRegressor(
        n_estimators=300, max_depth=6, learning_rate=0.08,
        subsample=0.85, colsample_bytree=0.85, min_child_weight=3,
        objective="reg:squarederror", tree_method="hist",
        random_state=42, verbosity=0,
    )
    model.fit(X_train, y_train)

    preds = model.predict(X_val)
    mae   = mean_absolute_error(y_val, preds)
    r2    = r2_score(y_val, preds)
    mape  = float(np.mean(np.abs((y_val - preds) / np.maximum(y_val, 1e-6))) * 100)
    print(f"  MAE={mae:.5f} kWh   R2={r2:.4f}   MAPE={mape:.2f}%")

    return model


# ── Step 2: Package as model.tar.gz ──────────────────────────────────────────
def package_model(model) -> Path:
    model_dir = DATA_DIR / "model_artifact"
    model_dir.mkdir(exist_ok=True)
    code_dir  = model_dir / "code"
    code_dir.mkdir(exist_ok=True)

    # Save in native XGBoost binary format
    # No custom inference script — use the container's built-in CSV handler
    model.get_booster().save_model(str(model_dir / "xgboost-model"))

    tar_path = DATA_DIR / "model.tar.gz"
    with tarfile.open(tar_path, "w:gz") as tar:
        tar.add(model_dir / "xgboost-model", arcname="xgboost-model")

    print(f"  Packaged -> {tar_path}  ({tar_path.stat().st_size // 1024} KB)")
    return tar_path


# ── Step 3: Upload to S3 ──────────────────────────────────────────────────────
def upload_to_s3(s3, tar_path: Path) -> str:
    model_key = "model-output/model.tar.gz"
    print(f"Uploading model artifact -> s3://{TRAINING_BUCKET}/{model_key}")
    s3.upload_file(str(tar_path), TRAINING_BUCKET, model_key)

    demo_key = "demo/demo_events_with_fault.json"
    print(f"Uploading demo events    -> s3://{RAW_BUCKET}/{demo_key}")
    s3.upload_file(str(DATA_DIR / "demo_events_with_fault.json"), RAW_BUCKET, demo_key)

    permits_key = "permits/zenpower_permits.csv"
    print(f"Uploading permits CSV    -> s3://{TRAINING_BUCKET}/{permits_key}")
    s3.upload_file(str(DATA_DIR / "zenpower_permits.csv"), TRAINING_BUCKET, permits_key)

    return f"s3://{TRAINING_BUCKET}/{model_key}"


# ── Step 4: Deploy SageMaker endpoint via boto3 ───────────────────────────────
def deploy_endpoint(sm, model_s3_uri: str):
    ts = int(time.time())
    model_name  = f"solarsentinel-model-{ts}"
    config_name = f"solarsentinel-config-{ts}"

    # Delete existing endpoint if it exists
    try:
        sm.delete_endpoint(EndpointName=ENDPOINT_NAME)
        print(f"Deleted existing endpoint {ENDPOINT_NAME}, waiting 30s ...")
        time.sleep(30)
    except sm.exceptions.ClientError:
        pass  # doesn't exist yet

    # Create Model
    print(f"Creating SageMaker model: {model_name}")
    sm.create_model(
        ModelName        = model_name,
        ExecutionRoleArn = SAGEMAKER_ROLE,
        PrimaryContainer = {
            "Image":        XGB_IMAGE,
            "ModelDataUrl": model_s3_uri,
        },
    )

    # Create EndpointConfig
    print(f"Creating endpoint config: {config_name}")
    sm.create_endpoint_config(
        EndpointConfigName = config_name,
        ProductionVariants  = [{
            "VariantName":         "AllTraffic",
            "ModelName":           model_name,
            "InstanceType":        "ml.t2.medium",
            "InitialInstanceCount": 1,
        }],
    )

    # Create Endpoint
    print(f"Creating endpoint: {ENDPOINT_NAME}  (takes ~5 min, polling ...)")
    sm.create_endpoint(
        EndpointName       = ENDPOINT_NAME,
        EndpointConfigName = config_name,
    )

    # Poll until InService
    for i in range(120):  # wait up to 30 min
        resp   = sm.describe_endpoint(EndpointName=ENDPOINT_NAME)
        status = resp["EndpointStatus"]
        print(f"  [{i*15:>4}s] {status}")
        if status == "InService":
            print(f"\nEndpoint {ENDPOINT_NAME} is LIVE.")
            return
        if status == "Failed":
            reason = resp.get("FailureReason", "unknown")
            raise RuntimeError(f"Endpoint failed: {reason}")
        time.sleep(15)

    raise TimeoutError("Endpoint did not become InService within 10 minutes.")


def main():
    session = boto3.Session(region_name=REGION)
    s3  = session.client("s3")
    sm  = session.client("sagemaker")

    print("=== Step 1: Train locally ===")
    model = train()

    print("\n=== Step 2: Package model ===")
    tar_path = package_model(model)

    print("\n=== Step 3: Upload to S3 ===")
    model_s3_uri = upload_to_s3(s3, tar_path)

    print("\n=== Step 4: Deploy SageMaker endpoint ===")
    deploy_endpoint(sm, model_s3_uri)

    print("\nAll done. Your live endpoint: solarsentinel-predictor")
    print("Next: cd frontend && npm install && npm run dev")


if __name__ == "__main__":
    main()
