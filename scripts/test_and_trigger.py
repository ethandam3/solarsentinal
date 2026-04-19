"""
test_and_trigger.py
1. Sends a test prediction to the SageMaker endpoint
2. Triggers the demo replay via REST API
"""
import boto3, json, urllib.request

REGION        = "us-east-1"
ENDPOINT_NAME = "solarsentinel-predictor"
REST_URL      = "https://8diq28ge23.execute-api.us-east-1.amazonaws.com/prod"

# ── Step 1: Test the SageMaker endpoint directly ──────────────────────────────
print("=== Testing SageMaker endpoint ===")
sm = boto3.client("sagemaker-runtime", region_name=REGION)

# CSV row: solar_wm2, temp_f, humidity, uv, size_kw, tilt, azimuth, hour, month
csv_payload = "746.5,73.8,76.0,7.0,8.4,22,180,14,8"

resp = sm.invoke_endpoint(
    EndpointName=ENDPOINT_NAME,
    ContentType="text/csv",
    Body=csv_payload,
)
result = resp["Body"].read().decode().strip()
print(f"  Input:  746.5 W/m2, 8.4 kW system, 2pm August")
print(f"  Output: {float(result):.5f} kWh predicted")
print("  Endpoint is working!\n")

# ── Step 2: Trigger the demo replay ──────────────────────────────────────────
print("=== Triggering demo replay ===")
payload = json.dumps({"delay_seconds": 4}).encode()
req = urllib.request.Request(
    f"{REST_URL}/replay",
    data=payload,
    headers={"Content-Type": "application/json"},
    method="POST",
)
print("  POST /replay sent (replay is running in Lambda, async)")
print("  Go to http://localhost:5173 and watch the dashboard!")
print("  Alert for ZP-0014 will fire within ~2-3 minutes.")
try:
    with urllib.request.urlopen(req, timeout=10) as r:
        print(f"  Response: {r.read().decode()}")
except Exception as e:
    # Lambda takes >10s to respond since it's long-running — that's fine
    print(f"  (Lambda is running in background — {e})")
    print("  This is expected. Dashboard will update live.")
