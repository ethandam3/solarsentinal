"""
scorer/handler.py
Triggered by: S3 ObjectCreated on the raw-irradiance bucket (*.json events)

For each reading in the uploaded JSON file:
  1. Build feature vector
  2. Invoke SageMaker endpoint → expected_kwh
  3. Compute delta = (expected - actual) / expected
  4. Write score row to DynamoDB (streams to anomaly_broadcaster)
"""

import os
import json
import time
import math
import boto3
from decimal import Decimal

s3_client  = boto3.client("s3")
sm_runtime = boto3.client("sagemaker-runtime")
dynamodb   = boto3.resource("dynamodb")
scores_tbl = dynamodb.Table(os.environ["SCORES_TABLE"])

ENDPOINT        = os.environ["SAGEMAKER_ENDPOINT"]
ANOMALY_THRESH  = float(os.environ.get("ANOMALY_THRESHOLD", "0.15"))
TTL_SECONDS     = 3600 * 48   # keep scores for 48h

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


def invoke_endpoint(features: dict) -> float:
    """Call SageMaker endpoint and return predicted expected_kwh.
    Uses CSV format — the built-in XGBoost container's native input format.
    Feature order must match training: solar_wm2, temp_f, humidity, uv,
    size_kw, tilt, azimuth, hour, month.
    """
    csv_row = ",".join(str(features[f]) for f in FEATURES)
    response = sm_runtime.invoke_endpoint(
        EndpointName=ENDPOINT,
        ContentType="text/csv",
        Body=csv_row,
    )
    return float(response["Body"].read().decode().strip())


def score_reading(reading: dict) -> dict:
    """Score one reading, return enriched result with delta + anomaly flag."""
    feat_vec = {f: reading[f] for f in FEATURES}
    expected = invoke_endpoint(feat_vec)

    actual   = float(reading.get("actual_kwh", expected))  # fallback = expected
    delta    = (expected - actual) / max(expected, 1e-9)
    is_anomaly = delta > ANOMALY_THRESH

    return {
        **reading,
        "expected_kwh":  round(expected, 5),
        "actual_kwh":    round(actual,   5),
        "delta_pct":     round(delta * 100, 2),
        "is_anomaly":    is_anomaly,
    }


def write_score(scored: dict):
    """Persist scored reading to DynamoDB."""
    scores_tbl.put_item(Item={
        "permit_id":      scored["permit_id"],
        "timestamp":      scored["timestamp"],
        "solar_wm2":      Decimal(str(round(scored["solar_radiation_wm2"], 2))),
        "expected_kwh":   Decimal(str(scored["expected_kwh"])),
        "actual_kwh":     Decimal(str(scored["actual_kwh"])),
        "delta_pct":      Decimal(str(scored["delta_pct"])),
        "is_anomaly":     scored["is_anomaly"],
        "system_size_kw": Decimal(str(scored.get("system_size_dc_kw", 0))),
        "address":        scored.get("address", ""),
        "zip_code":       scored.get("zip_code", ""),
        "fault_injected": scored.get("fault_injected", False),
        "ttl":            int(time.time()) + TTL_SECONDS,
    })


def lambda_handler(event, context):
    results = []

    for record in event.get("Records", []):
        bucket = record["s3"]["bucket"]["name"]
        key    = record["s3"]["object"]["key"]

        print(f"[SCORER] Processing s3://{bucket}/{key}")

        obj  = s3_client.get_object(Bucket=bucket, Key=key)
        body = obj["Body"].read().decode("utf-8")
        readings = json.loads(body)

        # Support both single dict and list
        if isinstance(readings, dict):
            readings = [readings]

        for reading in readings:
            # Skip nighttime / zero-solar readings (no meaningful score)
            if reading.get("solar_radiation_wm2", 0) < 50:
                continue

            try:
                scored = score_reading(reading)
                write_score(scored)
                results.append({
                    "permit_id": scored["permit_id"],
                    "delta_pct": scored["delta_pct"],
                    "anomaly":   scored["is_anomaly"],
                })
                print(
                    f"  {scored['permit_id']}  "
                    f"expected={scored['expected_kwh']} kWh  "
                    f"actual={scored['actual_kwh']} kWh  "
                    f"delta={scored['delta_pct']}%  "
                    f"{'🚨 ANOMALY' if scored['is_anomaly'] else 'OK'}"
                )
            except Exception as e:
                print(f"  ERROR scoring {reading.get('permit_id', '?')}: {e}")

    print(f"[SCORER] Done. Scored {len(results)} readings.")
    return {"statusCode": 200, "scored": len(results)}
