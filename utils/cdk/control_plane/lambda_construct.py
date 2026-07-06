"""The launcher Lambda (container image) and its IAM permissions.

Builds the OCI image from ``container/Dockerfile`` at synth time (the same image
used by `just docker-build`). In tests, ``build_image=False`` swaps in a dummy
ECR reference so synthesis doesn't require Docker.

Security model preserved here:
- The launcher role may read only the *signing* secret and write the idempotency
  table. It never receives the environment key (that's the MicroVM role's job).
- The run-hook config passed to the VM carries the environment-key *ARN*, not the
  value.
"""

from __future__ import annotations

from collections.abc import Mapping

from aws_cdk import Duration
from aws_cdk import aws_dynamodb as dynamodb
from aws_cdk import aws_ecr as ecr
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_secretsmanager as secretsmanager
from constructs import Construct


class LauncherFunction(Construct):
    def __init__(
        self,
        scope: Construct,
        id_: str,
        *,
        environment: Mapping[str, str],
        table: dynamodb.Table,
        signing_secret: secretsmanager.Secret,
        build_image: bool = True,
    ) -> None:
        super().__init__(scope, id_)

        code = self._code(build_image)

        env = dict(environment)
        env["IDEMPOTENCY_TABLE"] = table.table_name
        env["SIGNING_SECRET_ARN"] = signing_secret.secret_arn

        self.function = lambda_.DockerImageFunction(
            self,
            "Function",
            code=code,
            architecture=lambda_.Architecture.ARM_64,
            timeout=Duration.seconds(60),
            memory_size=512,
            environment=env,
        )

        # Idempotency: read + write the table; read the signing secret only.
        table.grant_read_write_data(self.function)
        signing_secret.grant_read(self.function)

    def _code(self, build_image: bool) -> lambda_.DockerImageCode:
        if build_image:
            return lambda_.DockerImageCode.from_image_asset(
                directory="../..",
                file="container/Dockerfile",
                cmd=["launcher.app.handler"],
            )
        # Dummy ECR ref so synthesis (and unit tests) don't require Docker.
        repo = ecr.Repository.from_repository_arn(
            self,
            "DummyRepo",
            "arn:aws:ecr:us-west-2:1:repository/claude-microvm-launcher",
        )
        return lambda_.DockerImageCode.from_ecr(
            repo, tag_or_digest="dummy", cmd=["launcher.app.handler"]
        )
