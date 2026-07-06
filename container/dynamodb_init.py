"""Create the idempotency table in DynamoDB Local (compose dev parity).

Run inside the launcher image (boto3 is present). Retries until DynamoDB Local
is reachable, then creates ``IDEMPOTENCY_TABLE`` if absent. Idempotent.
"""

from __future__ import annotations

import os
import time

import boto3
from botocore.exceptions import BotoCoreError, ClientError, ConnectionError


def main() -> None:
    endpoint = os.environ["AWS_ENDPOINT_URL_DYNAMODB"]
    table = os.environ["IDEMPOTENCY_TABLE"]
    region = os.environ.get("AWS_REGION", "us-west-2")

    client = boto3.client("dynamodb", endpoint_url=endpoint, region_name=region)

    # Wait for DynamoDB Local to accept connections.
    for _ in range(30):
        try:
            client.list_tables()
            break
        except (ConnectionError, BotoCoreError):
            time.sleep(1)
    else:
        raise SystemExit("DynamoDB Local not reachable at " + endpoint)

    try:
        client.create_table(
            TableName=table,
            AttributeDefinitions=[{"AttributeName": "id", "AttributeType": "S"}],
            KeySchema=[{"AttributeName": "id", "KeyType": "HASH"}],
            BillingMode="PAY_PER_REQUEST",
        )
        client.get_waiter("table_exists").wait(TableName=table)
        print(f"created idempotency table: {table}")
    except ClientError as exc:
        if exc.response["Error"]["Code"] == "ResourceInUseException":
            print(f"idempotency table already exists: {table}")
        else:
            raise


if __name__ == "__main__":
    main()
