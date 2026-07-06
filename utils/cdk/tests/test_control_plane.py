"""Structural tests for the control-plane stack (FR-007: CDK reproduces SAM).

Run without Docker (build_image=False) — only the synthesized template is
inspected. A parity diff against template.yaml is a separate follow-up task.
"""

from __future__ import annotations

import pytest
from aws_cdk import App
from aws_cdk.assertions import Template
from control_plane.stack import ControlPlaneStack


@pytest.fixture
def template() -> Template:
    app = App()
    stack = ControlPlaneStack(
        app,
        "Test",
        environment_id="env_t",
        image_identifier="img_t",
        execution_role_arn="arn:aws:iam::1:role/microvm-exec",
        build_image=False,
    )
    return Template.from_stack(stack)


def test_synthesizes_one_lambda_function(template):
    template.resource_count_is("AWS::Lambda::Function", 1)
    template.has_resource_properties(
        "AWS::Lambda::Function",
        {"PackageType": "Image", "Architectures": ["arm64"]},
    )


def test_synthesizes_dynamodb_idempotency_table(template):
    template.resource_count_is("AWS::DynamoDB::Table", 1)
    template.has_resource_properties(
        "AWS::DynamoDB::Table",
        {
            "BillingMode": "PAY_PER_REQUEST",
            "KeySchema": [{"AttributeName": "id", "KeyType": "HASH"}],
            "AttributeDefinitions": [{"AttributeName": "id", "AttributeType": "S"}],
            "TimeToLiveSpecification": {"AttributeName": "expiration", "Enabled": True},
        },
    )


def test_synthesizes_http_api_with_webhook_route(template):
    template.resource_count_is("AWS::ApiGatewayV2::Api", 1)
    template.resource_count_is("AWS::ApiGatewayV2::Integration", 2)
    template.resource_count_is("AWS::ApiGatewayV2::Route", 2)


def test_synthesizes_signing_and_envkey_secrets(template):
    template.resource_count_is("AWS::SecretsManager::Secret", 2)


def test_function_env_carries_idempotency_and_credential_ref(template):
    resources = template.to_json()["Resources"]
    function = next(r for r in resources.values() if r["Type"] == "AWS::Lambda::Function")
    env = function["Properties"]["Environment"]["Variables"]

    assert env["ANTHROPIC_ENVIRONMENT_ID"] == "env_t"
    assert env["MICROVM_IMAGE_IDENTIFIER"] == "img_t"
    assert env["MICROVM_EXECUTION_ROLE_ARN"] == "arn:aws:iam::1:role/microvm-exec"
    assert env["IDEMPOTENCY_TABLE"]
    # The environment-key *ARN* (a reference), not the key value.
    assert env["ENVIRONMENT_KEY_SECRET_ARN"]
    assert env["SIGNING_SECRET_ARN"]


def test_credential_boundary_no_secret_values_in_function_env(template):
    """FR-004: API key and environment key values never reach the launcher."""
    resources = template.to_json()["Resources"]
    function = next(r for r in resources.values() if r["Type"] == "AWS::Lambda::Function")
    env = function["Properties"]["Environment"]["Variables"]

    assert "ANTHROPIC_API_KEY" not in env
    assert "ANTHROPIC_ENVIRONMENT_KEY" not in env
