"""
upload_to_s3.py
Uploads all prepared data files to S3 and kicks off the SageMaker training job.

Run this AFTER:
  1. parse_scripps.py       -> data/awn_events.json
  2. generate_permits.py    -> data/zenpower_permits.csv
  3. prepare_training_data.py -> data/training.csv + data/demo_events_with_fault.json

Usage:
  python scripts/upload_to_s3.py --account 123456789012 --region us-east-1

After this finishes:
  - training.csv is in s3://solarsentinel-training-{account}/data/training.csv
  - SageMaker training job has been submitted (takes ~5-10 min)
  - demo_events_with_fault.json is in s3://solarsentinel-raw-{account}/demo/
  - Script prints the training job name to paste into deploy_endpoint.py
"""

import argparse
import boto3
import sagemaker
import json
from pathlib import Path
from datetime import datetime

DATA_DIR = Path(r"C:\Users\ethan\solarsentinel\data")
TRAIN_DIR = Path(r"C:\Users\ethan\solarsentinel\training")


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--account", required=True,   help="AWS account ID (12 digits)")
    p.add_argument("--region",  default="us-east-1")
    p.add_argument("--role",    default=None,     help="SageMaker execution role ARN (auto-detected if omitted)")
    return p.parse_args()


def main():
    args   = parse_args()
    region = args.region
    acct   = args.account

    session    = boto3.Session(region_name=region)
    s3_client  = session.client("s3")
    sm_session = sagemaker.Session(boto_session=session)

    raw_bucket      = f"solarsentinel-raw-irradiance-{acct}"
    training_bucket = f"solarsentinel-training-{acct}"

    # ── 1. Upload training CSV to training bucket ─────────────────────────
    training_csv = DATA_DIR / "training.csv"
    print(f"Uploading {training_csv.name} -> s3://{training_bucket}/data/")
    s3_client.upload_file(
        str(training_csv),
        training_bucket,
        "data/training.csv",
    )
    print("  OK Done")

    # ── 2. Upload demo replay events to raw bucket ────────────────────────
    demo_json = DATA_DIR / "demo_events_with_fault.json"
    print(f"Uploading {demo_json.name} -> s3://{raw_bucket}/demo/")
    s3_client.upload_file(
        str(demo_json),
        raw_bucket,
        "demo/demo_events_with_fault.json",
    )
    print("  OK Done")

    # ── 3. Upload ZenPower permits CSV ────────────────────────────────────
    permits_csv = DATA_DIR / "zenpower_permits.csv"
    print(f"Uploading {permits_csv.name} -> s3://{training_bucket}/permits/")
    s3_client.upload_file(
        str(permits_csv),
        training_bucket,
        "permits/zenpower_permits.csv",
    )
    print("  OK Done")

    # ── 4. Submit SageMaker XGBoost training job ──────────────────────────
    # Role has a fixed name set in the CDK stack — construct ARN locally
    role = args.role or f"arn:aws:iam::{acct}:role/solarsentinel-sagemaker-role"
    print(f"\nUsing SageMaker role: {role}")

    xgb_image = sagemaker.image_uris.retrieve(
        framework="xgboost",
        region=region,
        version="1.7-1",
    )
    print(f"XGBoost image: {xgb_image}")

    job_name = f"solarsentinel-train-{datetime.now().strftime('%Y%m%d-%H%M%S')}"

    estimator = sagemaker.estimator.Estimator(
        image_uri        = xgb_image,
        role             = role,
        instance_count   = 1,
        instance_type    = "ml.m5.large",
        volume_size      = 10,
        output_path      = f"s3://{training_bucket}/model-output/",
        sagemaker_session= sm_session,
        base_job_name    = job_name,
        hyperparameters  = {
            "num_round":       "300",
            "max_depth":       "6",
            "eta":             "0.08",
            "subsample":       "0.85",
            "colsample_bytree":"0.85",
            "min_child_weight":"3",
            "objective":       "reg:squarederror",
            "eval_metric":     "mae",
            # XGBoost container expects CSV with label in first column
            # (prepare_training_data.py puts expected_kwh last — we reorder below)
        },
        entry_point      = "train.py",
        source_dir       = str(TRAIN_DIR),
        framework_version= "1.7-1",
        py_version       = "py3",
    )

    training_input = sagemaker.inputs.TrainingInput(
        s3_data      = f"s3://{training_bucket}/data/",
        content_type = "text/csv",
    )

    print(f"\nSubmitting training job: {job_name}")
    estimator.fit({"train": training_input}, wait=False)
    print(f"  OK Job submitted (async). Monitor in SageMaker console.")
    print(f"  Training job name: {estimator.latest_training_job.name}")

    # Save job name for deploy_endpoint.py
    config = {
        "training_job_name": estimator.latest_training_job.name,
        "region":            region,
        "account":           acct,
        "training_bucket":   training_bucket,
        "raw_bucket":        raw_bucket,
    }
    config_path = DATA_DIR.parent / "config.json"
    with open(config_path, "w") as f:
        json.dump(config, f, indent=2)
    print(f"\nConfig saved -> {config_path}")
    print("\nNext step: run  python scripts/deploy_endpoint.py  after training completes (~5-10 min)")


if __name__ == "__main__":
    main()
