#!/usr/bin/env python3
"""CDK app entrypoint for the launcher control plane.

Synthesizes the control-plane stack. Configuration comes from the environment
(so the same app works locally and in CI); sensible defaults are provided for
local `cdk synth`.
"""

from __future__ import annotations

import os

import aws_cdk as cdk
from control_plane.stack import ControlPlaneStack

# Pin the output directory so `just cdk-synth` (which runs this directly, without
# the `cdk` CLI) writes the template into the repo instead of a temp staging dir.
app = cdk.App(outdir="cdk.out")

ControlPlaneStack(
    app,
    "CmaMicrovmLauncherStack",
    environment_id=os.environ.get("ANTHROPIC_ENVIRONMENT_ID", "env_cdk"),
    image_identifier=os.environ.get("MICROVM_IMAGE_IDENTIFIER", "img_cdk"),
    execution_role_arn=os.environ.get(
        "MICROVM_EXECUTION_ROLE_ARN", "arn:aws:iam::1:role/microvm-exec"
    ),
    env_key_secret_arn=os.environ.get("ENVIRONMENT_KEY_SECRET_ARN"),
    signing_secret_arn=os.environ.get("SIGNING_SECRET_ARN"),
    # Default: build the real OCI image at synth/deploy (needs Docker). Set
    # CDK_BUILD_IMAGE=0 to synthesize a structural template without Docker.
    build_image=os.environ.get("CDK_BUILD_IMAGE", "1") == "1",
    env=cdk.Environment(
        account=os.environ.get("CDK_DEFAULT_ACCOUNT"),
        region=os.environ.get("CDK_DEFAULT_REGION", "us-west-2"),
    ),
)

app.synth()
