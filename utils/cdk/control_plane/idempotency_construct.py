"""DynamoDB table backing webhook idempotency."""

from __future__ import annotations

from aws_cdk import RemovalPolicy
from aws_cdk import aws_dynamodb as dynamodb
from constructs import Construct


class IdempotencyTable(dynamodb.Table):
    """Partition key ``id`` with a TTL on ``expiration`` (matches the launcher)."""

    def __init__(self, scope: Construct, id_: str) -> None:
        super().__init__(
            scope,
            id_,
            partition_key=dynamodb.Attribute(name="id", type=dynamodb.AttributeType.STRING),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            time_to_live_attribute="expiration",
            removal_policy=RemovalPolicy.DESTROY,
        )
