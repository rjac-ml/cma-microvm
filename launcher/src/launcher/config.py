"""Launcher configuration, loaded from the environment via Pydantic-settings.

Replaces the plain dataclass that lived in ``shared/types.py``. The environment
variable names match the SAM/CDK control-plane template so the same dispatch
contract works in AWS and locally (Factor III: config in the environment).
"""

from __future__ import annotations

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from launcher.shared.constants import (
    DEFAULT_LAUNCH_TPS_LIMIT,
    DEFAULT_MAX_LIFETIME_SECONDS,
)


class LauncherConfig(BaseSettings):
    """Configuration for the launcher, sourced from environment variables."""

    model_config = SettingsConfigDict(extra="ignore", populate_by_name=True)

    environment_id: str = Field(
        validation_alias=AliasChoices("ANTHROPIC_ENVIRONMENT_ID"),
    )
    image_identifier: str = Field(
        validation_alias=AliasChoices("MICROVM_IMAGE_IDENTIFIER"),
    )
    environment_key_secret_id: str = Field(
        validation_alias=AliasChoices("ENVIRONMENT_KEY_SECRET_ARN"),
    )
    execution_role_arn: str = Field(
        validation_alias=AliasChoices("MICROVM_EXECUTION_ROLE_ARN"),
    )
    aws_region: str = Field(
        default="us-west-2",
        validation_alias=AliasChoices("AWS_REGION"),
    )
    signing_secret_arn: str | None = Field(
        default=None,
        validation_alias=AliasChoices("SIGNING_SECRET_ARN"),
    )
    base_url: str | None = Field(
        default=None,
        validation_alias=AliasChoices("ANTHROPIC_BASE_URL"),
    )
    max_lifetime_seconds: int = Field(
        default=DEFAULT_MAX_LIFETIME_SECONDS,
        validation_alias=AliasChoices("MAX_LIFETIME_SECONDS"),
    )
    launch_tps_limit: int = Field(
        default=DEFAULT_LAUNCH_TPS_LIMIT,
        validation_alias=AliasChoices("LAUNCH_TPS_LIMIT"),
    )
