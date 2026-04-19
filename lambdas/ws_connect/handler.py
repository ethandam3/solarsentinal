"""
ws_connect/handler.py
Stores the WebSocket connectionId in DynamoDB when a client connects.
"""

import os
import json
import time
import boto3

dynamodb = boto3.resource("dynamodb")
table    = dynamodb.Table(os.environ["CONNECTIONS_TABLE"])

TTL_SECONDS = 3600 * 8  # 8-hour session TTL


def lambda_handler(event, context):
    connection_id = event["requestContext"]["connectionId"]
    domain        = event["requestContext"]["domainName"]
    stage         = event["requestContext"]["stage"]

    table.put_item(Item={
        "connection_id": connection_id,
        "endpoint":      f"https://{domain}/{stage}",
        "connected_at":  int(time.time()),
        "ttl":           int(time.time()) + TTL_SECONDS,
    })

    print(f"[WS CONNECT] connection_id={connection_id}")
    return {"statusCode": 200, "body": "Connected"}
