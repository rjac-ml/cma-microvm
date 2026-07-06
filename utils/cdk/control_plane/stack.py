"""Control-plane stack: composes the idempotency table, secrets, launcher
function, and HTTP API into one deployable unit.

Reproduces the original SAM template as CDK (FR-007). The launcher's environment
carries only non-secret dispatch config plus the *ARN* of the environment-key
secret — never the key itself (credential boundary, test-asserted).
"""

from __future__ import annotations

from aws_cdk import CfnOutput, Stack
from aws_cdk import aws_lambda as lambda_
from constructs import Construct

from control_plane.api_construct import LauncherApi
from control_plane.idempotency_construct import IdempotencyTable
from control_plane.lambda_construct import LauncherFunction
from control_plane.secrets_construct import LauncherSecrets


class ControlPlaneStack(Stack):
    def __init__(
        self,
        scope: Construct,
        id_: str,
        *,
        environment_id: str,
        image_identifier: str,
        execution_role_arn: str,
        env_key_secret_arn: str | None = None,
        signing_secret_arn: str | None = None,
        build_image: bool = True,
        **kwargs: object,
    ) -> None:
        super().__init__(scope, id_, **kwargs)  # type: ignore[arg-type]

        self.table = IdempotencyTable(self, "IdempotencyTable")
        self.secrets = LauncherSecrets(
            self,
            "Secrets",
            signing_secret_arn=signing_secret_arn,
            env_key_secret_arn=env_key_secret_arn,
        )

        # Non-secret dispatch config. Only the environment-key ARN is passed.
        function_env = {
            "ANTHROPIC_ENVIRONMENT_ID": environment_id,
            "MICROVM_IMAGE_IDENTIFIER": image_identifier,
            "MICROVM_EXECUTION_ROLE_ARN": execution_role_arn,
            "ENVIRONMENT_KEY_SECRET_ARN": self.secrets.env_key_secret.secret_arn,
        }

        self.launcher_construct = LauncherFunction(
            self,
            "Launcher",
            environment=function_env,
            table=self.table,
            signing_secret=self.secrets.signing_secret,
            build_image=build_image,
        )
        self.function: lambda_.Function = self.launcher_construct.function

        self.api = LauncherApi(self, "Api", handler=self.function)

        CfnOutput(self, "ApiUrl", value=self.api.url or "")
        CfnOutput(self, "LauncherFunctionArn", value=self.function.function_arn)
        CfnOutput(self, "IdempotencyTableName", value=self.table.table_name)
