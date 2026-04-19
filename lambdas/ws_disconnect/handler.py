"""
ws_disconnect/handler.py
Removes the WebSocket connectionId from DynamoDB when a client disconnects.
"""

import os
import boto3

dynamodb = boto3.resource("dynamodb")
table    = dynamodb.Table(os.environ["CONNECTIONS_TABLE"])


def lambda_handler(event, context):
    connection_id = event["requestContext"]["connectionId"]

    table.delete_item(Key={"connection_id": connection_id})

    print(f"[WS DISCONNECT] connection_id={connection_id}")
    return {"statusCode": 200, "body": "Disconnected"}
