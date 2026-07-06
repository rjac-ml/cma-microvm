"""HTTP API: POST /webhook (and GET /healthz) -> the launcher Lambda."""

from __future__ import annotations

from aws_cdk import aws_apigatewayv2 as apigw
from aws_cdk import aws_apigatewayv2_integrations as integrations
from aws_cdk import aws_lambda as lambda_
from constructs import Construct


class LauncherApi(Construct):
    def __init__(self, scope: Construct, id_: str, *, handler: lambda_.Function) -> None:
        super().__init__(scope, id_)

        webhook = integrations.HttpLambdaIntegration("WebhookIntegration", handler)
        health = integrations.HttpLambdaIntegration("HealthIntegration", handler)

        self.api = apigw.HttpApi(self, "Api")
        self.api.add_routes(path="/webhook", methods=[apigw.HttpMethod.POST], integration=webhook)
        self.api.add_routes(path="/healthz", methods=[apigw.HttpMethod.GET], integration=health)

        self.url = self.api.url
