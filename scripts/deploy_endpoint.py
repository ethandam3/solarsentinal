"""
deploy_endpoint.py
Deploys the trained SageMaker model as a real-time endpoint.

Run AFTER upload_to_s3.py finishes and training job shows "Completed".

Usage:
  python scripts/deploy_endpoint.py

Reads config.json written by upload_to_s3.py.
Endpoint name will be: solarsentinel-predictor  (matches Lambda env var)
"""

import json
import boto3
import sagemaker
from pathlib import Path

CONFIG_PATH = Path(r"C:\Users\ethan\solarsentinel\config.json")
TRAIN_DIR   = Path(r"C:\Users\ethan\solarsentinel\training")
ENDPOINT_NAME = "solarsentinel-predictor"


def main():
    with open(CONFIG_PATH) as f:
        config = json.load(f)

    region   = config["region"]
    job_name = config["training_job_name"]

    session    = boto3.Session(region_name=region)
    sm_session = sagemaker.Session(boto_session=session)
    sm_client  = session.client("sagemaker")

    print(f"Training job: {job_name}")

    # Check job status
    job = sm_client.describe_training_job(TrainingJobName=job_name)
    status = job["TrainingJobStatus"]
    print(f"Status: {status}")

    if status != "Completed":
        print("Training not yet complete. Wait and re-run this script.")
        return

    model_uri = job["ModelArtifacts"]["S3ModelArtifacts"]
    print(f"Model artifact: {model_uri}")

    # Create model
    role = sagemaker.get_execution_role(sm_session)
    xgb_image = sagemaker.image_uris.retrieve(
        framework="xgboost",
        region=region,
        version="1.7-1",
    )

    model = sagemaker.Model(
        image_uri         = xgb_image,
        model_data        = model_uri,
        role              = role,
        entry_point       = "inference.py",
        source_dir        = str(TRAIN_DIR),
        sagemaker_session = sm_session,
        name              = "solarsentinel-model",
    )

    print(f"\nDeploying endpoint: {ENDPOINT_NAME}")
    print("(This takes ~5 minutes…)")

    predictor = model.deploy(
        initial_instance_count = 1,
        instance_type          = "ml.t2.medium",   # cheapest for demo
        endpoint_name          = ENDPOINT_NAME,
        wait                   = True,
    )

    print(f"\nOK Endpoint deployed: {ENDPOINT_NAME}")
    print("You can now deploy the CDK stack:  cd infra && cdk deploy")


if __name__ == "__main__":
    main()
