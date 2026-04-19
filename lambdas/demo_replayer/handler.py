"""
demo_replayer/handler.py
Triggered by: POST /replay (REST API)

Reads pre-processed demo events from S3 (demo_events_with_fault.json),
then dispatches them to the scorer Lambda one-by-one with a configurable
delay between each event — creating a real-time replay for judges.

POST /replay body (optional JSON):
  {
    "delay_seconds": 8,        // default 8  (how fast to replay)
    "permit_filter": "ZP-0014" // optional: only replay this install
  }

The fault is pre-baked into demo_events_with_fault.json by prepare_training_data.py.
Install ZP-0014 drops 24% below expected during hours 12-16 — the WebSocket alert
will fire naturally when the scorer Lambda writes that anomaly to DynamoDB.
"""

import os
import json
import time
import boto3

s3_client     = boto3.client("s3")
lambda_client = boto3.client("lambda")

RAW_BUCKET    = os.environ["RAW_BUCKET"]
SCORER_FN     = os.environ["SCORER_FN_NAME"]
DEMO_KEY      = "demo/demo_events_with_fault.json"

DEFAULT_DELAY = 8    # seconds between events (10min compressed to ~8s each)
MAX_EVENTS    = 200  # cap replay length (200 events × 8s ≈ 26 minutes max)


def lambda_handler(event, context):
    # Parse request body
    body = {}
    if isinstance(event.get("body"), str):
        try:
            body = json.loads(event["body"])
        except Exception:
            pass
    elif isinstance(event.get("body"), dict):
        body = event["body"]

    delay_seconds = float(body.get("delay_seconds", DEFAULT_DELAY))
    permit_filter = body.get("permit_filter")   # None = replay all installs

    # Load demo events from S3
    try:
        obj    = s3_client.get_object(Bucket=RAW_BUCKET, Key=DEMO_KEY)
        events = json.loads(obj["Body"].read().decode("utf-8"))
    except Exception as e:
        print(f"[REPLAYER] ERROR loading demo events: {e}")
        return {
            "statusCode": 500,
            "body": json.dumps({"error": str(e)}),
        }

    if permit_filter:
        events = [e for e in events if e.get("permit_id") == permit_filter]

    # Deduplicate by timestamp — only send each timestamp once (one reading per tick)
    # Group events by timestamp so all installs at that timestamp go in one batch
    from collections import defaultdict
    by_ts = defaultdict(list)
    for ev in events:
        by_ts[ev["timestamp"]].append(ev)

    timestamps = sorted(by_ts.keys())[:MAX_EVENTS]
    total_sent = 0

    print(
        f"[REPLAYER] Starting replay: {len(timestamps)} timestamps, "
        f"{delay_seconds}s delay, filter={permit_filter or 'all'}"
    )

    for i, ts in enumerate(timestamps):
        batch = by_ts[ts]

        # Upload batch as a JSON file to raw bucket (scorer picks it up via S3 trigger)
        key = f"raw/replay/{ts.replace(':', '-')}.json"
        s3_client.put_object(
            Bucket=RAW_BUCKET,
            Key=key,
            Body=json.dumps(batch),
            ContentType="application/json",
        )

        total_sent += len(batch)
        print(
            f"  [{i+1}/{len(timestamps)}] ts={ts}  "
            f"batch_size={len(batch)}  "
            f"has_fault={any(e.get('fault_injected') for e in batch)}"
        )

        # Check Lambda timeout: if <30s remaining, stop gracefully
        remaining_ms = context.get_remaining_time_in_millis() if hasattr(context, 'get_remaining_time_in_millis') else 999999
        if remaining_ms < 35000:
            print(f"[REPLAYER] Stopping early — only {remaining_ms}ms remaining")
            break

        if i < len(timestamps) - 1:
            time.sleep(delay_seconds)

    print(f"[REPLAYER] Done. Dispatched {total_sent} total readings.")
    return {
        "statusCode": 200,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
        },
        "body": json.dumps({
            "replayed_timestamps": len(timestamps),
            "total_readings": total_sent,
        }),
    }
