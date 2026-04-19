#!/usr/bin/env python3
"""
SolarSentinel CDK App entry point.

Deploy:
  cd infra
  pip install -r requirements.txt
  cdk bootstrap
  cdk deploy SolarSentinelStack
"""

import aws_cdk as cdk
from stacks.solarsentinel_stack import SolarSentinelStack

app = cdk.App()

SolarSentinelStack(
    app,
    "SolarSentinelStack",
    env=cdk.Environment(
        # CDK will use your active AWS_PROFILE / credentials
        account=app.node.try_get_context("account"),
        region=app.node.try_get_context("region") or "us-east-1",
    ),
    description="SolarSentinel — real-time solar anomaly detection (DataHacks 2026)",
)

app.synth()
