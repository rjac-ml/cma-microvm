"""Secrets: the webhook signing secret (launcher reads it) and the environment
key secret (read only by the MicroVM execution role, never by the launcher).

CDK creates these secrets if no existing ARN is supplied; otherwise it imports
the existing secret so the stack stays portable across environments.
"""

from __future__ import annotations

from aws_cdk import aws_secretsmanager as secretsmanager
from constructs import Construct


class LauncherSecrets(Construct):
    def __init__(
        self,
        scope: Construct,
        id_: str,
        *,
        signing_secret_arn: str | None = None,
        env_key_secret_arn: str | None = None,
    ) -> None:
        super().__init__(scope, id_)

        self.signing_secret = (
            secretsmanager.Secret.from_secret_complete_arn(
                self, "SigningSecret", signing_secret_arn
            )
            if signing_secret_arn
            else secretsmanager.Secret(
                self, "SigningSecret", description="Anthropic webhook signing secret"
            )
        )

        self.env_key_secret = (
            secretsmanager.Secret.from_secret_complete_arn(self, "EnvKeySecret", env_key_secret_arn)
            if env_key_secret_arn
            else secretsmanager.Secret(
                self,
                "EnvKeySecret",
                description="Anthropic environment key (read by the MicroVM execution role)",
            )
        )
