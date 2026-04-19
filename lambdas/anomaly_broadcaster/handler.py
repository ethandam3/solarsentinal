"""
anomaly_broadcaster/handler.py
Triggered by: DynamoDB stream on the solarsentinel-scores table.

For each INSERT/MODIFY on an anomaly row (is_anomaly=True):
  1. Look up all active WebSocket connection IDs from DynamoDB
  2. Push alert payload to every connected browser via API Gateway Management API
  3. Log the alert to the solarsentinel-anomalies table
  4. Publish to SNS (ZenPower ops team email/SMS)

Also handles GET /alerts REST calls for returning anomaly history.
"""

import os
import json
import time
import uuid
import boto3
from boto3.dynamodb.conditions import Attr
from botocore.exceptions import ClientError

dynamodb        = boto3.resource("dynamodb")
connections_tbl = dynamodb.Table(os.environ["CONNECTIONS_TABLE"])
anomaly_tbl     = dynamodb.Table(os.environ["ANOMALY_TABLE"])
sns_client      = boto3.client("sns")

WS_CALLBACK_URL = os.environ.get("WS_CALLBACK_URL", "")
ALERT_TOPIC_ARN = os.environ.get("ALERT_TOPIC_ARN", "")


def get_apigw_client():
    """Build API Gateway Management API client from the WebSocket callback URL."""
    if not WS_CALLBACK_URL:
        return None
    return boto3.client(
        "apigatewaymanagementapi",
        endpoint_url=WS_CALLBACK_URL,
    )


def broadcast_to_connections(payload: dict):
    """Send JSON payload to all active WebSocket connections."""
    apigw = get_apigw_client()
    if not apigw:
        print("[BROADCASTER] No WS callback URL — skipping WebSocket push")
        return

    resp  = connections_tbl.scan()
    conns = resp.get("Items", [])
    print(f"[BROADCASTER] Broadcasting to {len(conns)} connections")

    dead_connections = []
    for conn in conns:
        cid = conn["connection_id"]
        try:
            apigw.post_to_connection(
                ConnectionId=cid,
                Data=json.dumps(payload),
            )
        except ClientError as e:
            code = e.response["Error"]["Code"]
            if code in ("GoneException", "410"):
                dead_connections.append(cid)
            else:
                print(f"  ERROR pushing to {cid}: {e}")

    # Prune stale connections
    for cid in dead_connections:
        print(f"  Pruning stale connection {cid}")
        connections_tbl.delete_item(Key={"connection_id": cid})


def log_anomaly(alert_payload: dict):
    """Persist the alert to the anomaly log table."""
    anomaly_tbl.put_item(Item={
        "alert_id":    str(uuid.uuid4()),
        "timestamp":   alert_payload["timestamp"],
        "permit_id":   alert_payload["permit_id"],
        "address":     alert_payload.get("address", ""),
        "delta_pct":   str(alert_payload["delta_pct"]),
        "expected_kwh":str(alert_payload["expected_kwh"]),
        "actual_kwh":  str(alert_payload["actual_kwh"]),
        "solar_wm2":   str(alert_payload.get("solar_wm2", 0)),
        "created_at":  int(time.time()),
    })


def notify_sns(alert_payload: dict):
    """Send an SNS notification to ZenPower ops."""
    if not ALERT_TOPIC_ARN:
        return
    message = (
        f"⚠️ SolarSentinel Alert\n"
        f"Install:   {alert_payload['permit_id']} ({alert_payload.get('address', '')})\n"
        f"Time:      {alert_payload['timestamp']}\n"
        f"Expected:  {alert_payload['expected_kwh']} kWh\n"
        f"Actual:    {alert_payload['actual_kwh']} kWh\n"
        f"Drop:      {alert_payload['delta_pct']}% below expected\n"
        f"Solar:     {alert_payload.get('solar_wm2', '?')} W/m²"
    )
    sns_client.publish(
        TopicArn=ALERT_TOPIC_ARN,
        Subject=f"Solar Anomaly: {alert_payload['permit_id']}",
        Message=message,
    )


def handle_dynamodb_stream(event):
    """Process DynamoDB stream records.

    Every scored reading is broadcast to the frontend so the dashboard can
    show green (healthy) tiles as well as red (anomaly) tiles.  Only anomaly
    rows also get logged to the anomaly table and published to SNS.
    """
    alerts_fired = 0
    scores_broadcast = 0

    for record in event.get("Records", []):
        if record["eventName"] not in ("INSERT", "MODIFY"):
            continue

        new_image = record["dynamodb"].get("NewImage", {})

        # Deserialise DynamoDB attribute values
        def dv(attr, typ="S"):
            v = new_image.get(attr, {})
            return v.get(typ) or v.get("N") or v.get("BOOL")

        is_anomaly = new_image.get("is_anomaly", {}).get("BOOL", False)

        payload = {
            "type":         "anomaly" if is_anomaly else "score",
            "permit_id":    dv("permit_id"),
            "timestamp":    dv("timestamp"),
            "address":      dv("address"),
            "expected_kwh": float(dv("expected_kwh", "N") or 0),
            "actual_kwh":   float(dv("actual_kwh",   "N") or 0),
            "delta_pct":    float(dv("delta_pct",    "N") or 0),
            "solar_wm2":    float(dv("solar_wm2",    "N") or 0),
            "system_kw":    float(dv("system_size_kw", "N") or 0),
            "is_anomaly":   is_anomaly,
        }

        broadcast_to_connections(payload)
        scores_broadcast += 1

        if is_anomaly:
            print(
                f"[BROADCASTER] Anomaly: {payload['permit_id']} "
                f"delta={payload['delta_pct']}%"
            )
            log_anomaly(payload)
            notify_sns(payload)
            alerts_fired += 1

    print(f"[BROADCASTER] Done. Broadcast {scores_broadcast} scores, fired {alerts_fired} alerts.")
    return alerts_fired


def handle_rest_get(event):
    """Return recent anomalies for the /alerts REST endpoint."""
    resp = anomaly_tbl.scan(Limit=50)
    items = sorted(
        resp.get("Items", []),
        key=lambda x: x.get("created_at", 0),
        reverse=True,
    )
    return {
        "statusCode": 200,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
        },
        "body": json.dumps({"alerts": items}, default=str),
    }


def lambda_handler(event, context):
    # REST API invocation (GET /alerts)
    if "httpMethod" in event:
        return handle_rest_get(event)

    # DynamoDB stream invocation
    return handle_dynamodb_stream(event)
