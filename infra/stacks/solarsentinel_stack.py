"""
SolarSentinel CDK Stack
Deploys the full AWS infrastructure for SolarSentinel:

  S3 buckets (raw data, training dataset, inference payloads)
  DynamoDB tables (install scores, anomaly log, WS connection registry)
  SageMaker endpoint (XGBoost regressor)
  Lambda functions (scorer, anomaly_broadcaster, ws_connect, ws_disconnect, demo_replayer)
  API Gateway REST + WebSocket APIs
  SNS alert topic
  CloudWatch dashboard + alarm
  EventBridge rule (30-min polling schedule)
"""

from aws_cdk import (
    Stack, Duration, RemovalPolicy, CfnOutput,
    aws_s3 as s3,
    aws_dynamodb as dynamodb,
    aws_lambda as lambda_,
    aws_lambda_event_sources as lambda_es,
    aws_apigateway as apigw,
    aws_apigatewayv2 as apigwv2,
    aws_apigatewayv2_integrations as apigwv2_integrations,
    aws_sns as sns,
    aws_sns_subscriptions as subscriptions,
    aws_cloudwatch as cw,
    aws_cloudwatch_actions as cw_actions,
    aws_events as events,
    aws_events_targets as targets,
    aws_iam as iam,
    aws_logs as logs,
)
from constructs import Construct
import os


class SolarSentinelStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs):
        super().__init__(scope, construct_id, **kwargs)

        # ── S3 Buckets ────────────────────────────────────────────────────────
        raw_bucket = s3.Bucket(
            self, "RawIrradianceBucket",
            bucket_name=f"solarsentinel-raw-irradiance-{self.account}",
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
            versioned=False,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
        )

        training_bucket = s3.Bucket(
            self, "TrainingDatasetBucket",
            bucket_name=f"solarsentinel-training-{self.account}",
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
        )

        inference_bucket = s3.Bucket(
            self, "InferencePayloadsBucket",
            bucket_name=f"solarsentinel-inference-{self.account}",
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
        )

        # ── DynamoDB Tables ───────────────────────────────────────────────────
        # Stores per-reading scores for every install
        scores_table = dynamodb.Table(
            self, "InstallScoresTable",
            table_name="solarsentinel-scores",
            partition_key=dynamodb.Attribute(
                name="permit_id", type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(
                name="timestamp", type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY,
            stream=dynamodb.StreamViewType.NEW_AND_OLD_IMAGES,  # triggers broadcaster
            time_to_live_attribute="ttl",
        )

        # Persists fired anomaly alerts
        anomaly_table = dynamodb.Table(
            self, "AnomalyLogTable",
            table_name="solarsentinel-anomalies",
            partition_key=dynamodb.Attribute(
                name="alert_id", type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY,
        )

        # WebSocket connection registry
        connections_table = dynamodb.Table(
            self, "WsConnectionsTable",
            table_name="solarsentinel-ws-connections",
            partition_key=dynamodb.Attribute(
                name="connection_id", type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY,
        )

        # ── SNS Alert Topic ───────────────────────────────────────────────────
        alert_topic = sns.Topic(
            self, "AlertTopic",
            topic_name="solarsentinel-alerts",
            display_name="SolarSentinel Anomaly Alerts",
        )
        # Add ZenPower ops team email (swap in at runtime via context)
        ops_email = self.node.try_get_context("ops_email")
        if ops_email:
            alert_topic.add_subscription(
                subscriptions.EmailSubscription(ops_email)
            )

        # ── SageMaker IAM Role ────────────────────────────────────────────────
        # Fixed role name so upload_to_s3.py can construct the ARN locally
        sagemaker_role = iam.Role(
            self, "SageMakerRole",
            role_name="solarsentinel-sagemaker-role",
            assumed_by=iam.ServicePrincipal("sagemaker.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "AmazonSageMakerFullAccess"
                ),
            ],
        )
        training_bucket.grant_read_write(sagemaker_role)

        # ── Lambda shared environment + role ─────────────────────────────────
        lambda_role = iam.Role(
            self, "LambdaRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "service-role/AWSLambdaBasicExecutionRole"
                ),
            ],
        )
        scores_table.grant_read_write_data(lambda_role)
        anomaly_table.grant_read_write_data(lambda_role)
        connections_table.grant_read_write_data(lambda_role)
        raw_bucket.grant_read(lambda_role)
        inference_bucket.grant_read_write(lambda_role)
        alert_topic.grant_publish(lambda_role)
        lambda_role.add_to_policy(iam.PolicyStatement(
            actions=["sagemaker:InvokeEndpoint"],
            resources=["*"],
        ))
        lambda_role.add_to_policy(iam.PolicyStatement(
            actions=["execute-api:ManageConnections"],
            resources=["*"],
        ))
        lambda_role.add_to_policy(iam.PolicyStatement(
            actions=["lambda:InvokeFunction"],
            resources=["*"],
        ))

        common_env = {
            "SCORES_TABLE":       scores_table.table_name,
            "ANOMALY_TABLE":      anomaly_table.table_name,
            "CONNECTIONS_TABLE":  connections_table.table_name,
            "ALERT_TOPIC_ARN":    alert_topic.topic_arn,
            "SAGEMAKER_ENDPOINT": "solarsentinel-predictor",
            "ANOMALY_THRESHOLD":  "0.15",   # 15% delta triggers alert
        }

        python_runtime = lambda_.Runtime.PYTHON_3_12
        lambda_dir = os.path.join(os.path.dirname(__file__), "../../lambdas")

        def make_log_group(self, name: str) -> logs.LogGroup:
            return logs.LogGroup(
                self, f"{name}LogGroup",
                log_group_name=f"/aws/lambda/solarsentinel-{name}",
                retention=logs.RetentionDays.THREE_DAYS,
                removal_policy=RemovalPolicy.DESTROY,
            )

        # ── WebSocket connect Lambda ──────────────────────────────────────────
        ws_connect_fn = lambda_.Function(
            self, "WsConnectFn",
            function_name="solarsentinel-ws-connect",
            runtime=python_runtime,
            handler="handler.lambda_handler",
            code=lambda_.Code.from_asset(os.path.join(lambda_dir, "ws_connect")),
            role=lambda_role,
            environment=common_env,
            timeout=Duration.seconds(10),
            log_group=make_log_group(self, "ws-connect"),
        )

        # ── WebSocket disconnect Lambda ───────────────────────────────────────
        ws_disconnect_fn = lambda_.Function(
            self, "WsDisconnectFn",
            function_name="solarsentinel-ws-disconnect",
            runtime=python_runtime,
            handler="handler.lambda_handler",
            code=lambda_.Code.from_asset(os.path.join(lambda_dir, "ws_disconnect")),
            role=lambda_role,
            environment=common_env,
            timeout=Duration.seconds(10),
            log_group=make_log_group(self, "ws-disconnect"),
        )

        # ── WebSocket API ─────────────────────────────────────────────────────
        ws_api = apigwv2.WebSocketApi(
            self, "SolarSentinelWsApi",
            api_name="solarsentinel-ws",
            connect_route_options=apigwv2.WebSocketRouteOptions(
                integration=apigwv2_integrations.WebSocketLambdaIntegration(
                    "WsConnectInteg", ws_connect_fn
                )
            ),
            disconnect_route_options=apigwv2.WebSocketRouteOptions(
                integration=apigwv2_integrations.WebSocketLambdaIntegration(
                    "WsDisconnectInteg", ws_disconnect_fn
                )
            ),
        )

        ws_stage = apigwv2.WebSocketStage(
            self, "WsStage",
            web_socket_api=ws_api,
            stage_name="prod",
            auto_deploy=True,
        )

        ws_callback_url = ws_stage.callback_url

        # ── Scorer Lambda ─────────────────────────────────────────────────────
        scorer_fn = lambda_.Function(
            self, "ScorerFn",
            function_name="solarsentinel-scorer",
            runtime=python_runtime,
            handler="handler.lambda_handler",
            code=lambda_.Code.from_asset(os.path.join(lambda_dir, "scorer")),
            role=lambda_role,
            environment={**common_env},
            timeout=Duration.seconds(30),
            memory_size=256,
            log_group=make_log_group(self, "scorer"),
        )

        # Trigger scorer when new JSON lands in raw bucket
        scorer_fn.add_event_source(
            lambda_es.S3EventSource(
                raw_bucket,
                events=[s3.EventType.OBJECT_CREATED],
                filters=[s3.NotificationKeyFilter(suffix=".json")],
            )
        )

        # ── Anomaly Broadcaster Lambda ────────────────────────────────────────
        broadcaster_fn = lambda_.Function(
            self, "AnomalyBroadcasterFn",
            function_name="solarsentinel-anomaly-broadcaster",
            runtime=python_runtime,
            handler="handler.lambda_handler",
            code=lambda_.Code.from_asset(
                os.path.join(lambda_dir, "anomaly_broadcaster")
            ),
            role=lambda_role,
            environment={
                **common_env,
                "WS_CALLBACK_URL": ws_callback_url,
            },
            timeout=Duration.seconds(30),
            memory_size=256,
            log_group=make_log_group(self, "anomaly-broadcaster"),
        )

        # Triggered by DynamoDB stream on scores table
        broadcaster_fn.add_event_source(
            lambda_es.DynamoEventSource(
                scores_table,
                starting_position=lambda_.StartingPosition.LATEST,
                batch_size=10,
                bisect_batch_on_error=True,
                retry_attempts=2,
            )
        )

        # ── Demo Replayer Lambda ──────────────────────────────────────────────
        demo_replayer_fn = lambda_.Function(
            self, "DemoReplayerFn",
            function_name="solarsentinel-demo-replayer",
            runtime=python_runtime,
            handler="handler.lambda_handler",
            code=lambda_.Code.from_asset(
                os.path.join(lambda_dir, "demo_replayer")
            ),
            role=lambda_role,
            environment={
                **common_env,
                "RAW_BUCKET":     raw_bucket.bucket_name,
                "SCORER_FN_NAME": scorer_fn.function_name,
            },
            timeout=Duration.minutes(15),   # long-running replay
            memory_size=256,
            log_group=make_log_group(self, "demo-replayer"),
        )
        raw_bucket.grant_read_write(demo_replayer_fn)

        # ── REST API ──────────────────────────────────────────────────────────
        rest_api = apigw.RestApi(
            self, "SolarSentinelRestApi",
            rest_api_name="solarsentinel-api",
            description="SolarSentinel REST endpoints",
            default_cors_preflight_options=apigw.CorsOptions(
                allow_origins=apigw.Cors.ALL_ORIGINS,
                allow_methods=apigw.Cors.ALL_METHODS,
            ),
        )

        # POST /replay  →  demo_replayer_fn
        replay_resource = rest_api.root.add_resource("replay")
        replay_resource.add_method(
            "POST",
            apigw.LambdaIntegration(demo_replayer_fn),
        )

        # GET /alerts  →  simple Lambda (or direct DynamoDB integration)
        alerts_resource = rest_api.root.add_resource("alerts")
        alerts_resource.add_method(
            "GET",
            apigw.LambdaIntegration(broadcaster_fn),
        )

        # ── CloudWatch Dashboard ──────────────────────────────────────────────
        dashboard = cw.Dashboard(
            self, "SolarSentinelDashboard",
            dashboard_name="SolarSentinel",
        )

        endpoint_latency_metric = cw.Metric(
            namespace="AWS/SageMaker",
            metric_name="ModelLatency",
            dimensions_map={"EndpointName": "solarsentinel-predictor"},
            statistic="p99",
            period=Duration.minutes(1),
        )

        scorer_errors = scorer_fn.metric_errors(period=Duration.minutes(5))
        broadcaster_invocations = broadcaster_fn.metric_invocations(
            period=Duration.minutes(5)
        )

        dashboard.add_widgets(
            cw.GraphWidget(
                title="SageMaker Endpoint p99 Latency (ms)",
                left=[endpoint_latency_metric],
                width=12,
            ),
            cw.GraphWidget(
                title="Scorer Errors / Broadcaster Invocations",
                left=[scorer_errors],
                right=[broadcaster_invocations],
                width=12,
            ),
        )

        # Alarm if endpoint latency > 2s
        latency_alarm = cw.Alarm(
            self, "EndpointLatencyAlarm",
            alarm_name="SolarSentinel-HighLatency",
            metric=endpoint_latency_metric,
            threshold=2000,
            evaluation_periods=3,
            comparison_operator=cw.ComparisonOperator.GREATER_THAN_THRESHOLD,
            alarm_description="SageMaker endpoint p99 latency exceeded 2s",
        )
        latency_alarm.add_alarm_action(
            cw_actions.SnsAction(alert_topic)
        )

        # ── Outputs ───────────────────────────────────────────────────────────
        CfnOutput(self, "RestApiUrl",
                  value=rest_api.url,
                  description="REST API base URL")
        CfnOutput(self, "WebSocketUrl",
                  value=ws_stage.url,
                  description="WebSocket URL (wss://...)")
        CfnOutput(self, "RawBucketName",
                  value=raw_bucket.bucket_name)
        CfnOutput(self, "TrainingBucketName",
                  value=training_bucket.bucket_name)
        CfnOutput(self, "ScoresTableName",
                  value=scores_table.table_name)
        CfnOutput(self, "SageMakerRoleArn",
                  value=sagemaker_role.role_arn,
                  description="Paste into upload_to_s3.py --role flag")
        CfnOutput(self, "DashboardUrl",
                  value=f"https://console.aws.amazon.com/cloudwatch/home#dashboards:name=SolarSentinel",
                  description="CloudWatch dashboard")
