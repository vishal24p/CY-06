"""AWS profile verification and assumed-role connection."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import boto3
from botocore.exceptions import (
    ClientError,
    NoCredentialsError,
    ProfileNotFound,
    SSOTokenLoadError,
    TokenRetrievalError,
)

EXPECTED_SOURCE_ACCOUNT = "820919093456"
EXPECTED_ROLE_ARN = (
    "arn:aws:iam::820919093456:role/PrivilegePathFinderReadOnlyRole"
)


@dataclass(frozen=True, repr=False)
class Connection:
    """Temporary assumed-role session and non-sensitive identity metadata."""

    session: Any = field(repr=False)
    account_id: str
    source_arn: str
    assumed_role_arn: str
    expiration: datetime

    def __repr__(self) -> str:
        return (
            "Connection("
            f"account_id={self.account_id!r}, "
            f"source_arn={self.source_arn!r}, "
            f"assumed_role_arn={self.assumed_role_arn!r}, "
            f"expiration={self.expiration!r})"
        )


def collect_inventory(connection: Connection) -> dict[str, list[dict[str, Any]]]:
    """Read the complete account IAM authorization inventory."""
    inventory: dict[str, list[dict[str, Any]]] = {
        "UserDetailList": [],
        "GroupDetailList": [],
        "RoleDetailList": [],
        "Policies": [],
    }
    try:
        pages = connection.session.client("iam").get_paginator(
            "get_account_authorization_details"
        ).paginate()
        for page in pages:
            for key in inventory:
                inventory[key].extend(page.get(key, []))
    except ClientError as error:
        raise ConnectionError("AWS IAM inventory read failed") from error
    return inventory


def connect(
    profile_name: str,
    role_arn: str,
    region_name: str | None = None,
) -> Connection:
    """Verify an AWS profile and return a temporary assumed-role connection."""
    if role_arn != EXPECTED_ROLE_ARN:
        raise ConnectionError("role ARN is not authorized")

    try:
        source_session = boto3.Session(profile_name=profile_name)
        if region_name:
            sts = source_session.client("sts", region_name=region_name)
        else:
            sts = source_session.client("sts")
        identity = sts.get_caller_identity()
        account_id = identity["Account"]
        if account_id != EXPECTED_SOURCE_ACCOUNT:
            raise ConnectionError("source account is not authorized")
        assumed = sts.assume_role(RoleArn=role_arn, RoleSessionName="cy06-local")
    except ProfileNotFound as error:
        raise ConnectionError("AWS profile not found") from error
    except (SSOTokenLoadError, TokenRetrievalError, NoCredentialsError) as error:
        raise ConnectionError("AWS SSO credentials unavailable") from error
    except ClientError as error:
        code = error.response.get("Error", {}).get("Code", "")
        if code in {"UnauthorizedException", "AccessDenied", "AccessDeniedException"}:
            raise ConnectionError("AWS profile login incomplete or role assumption denied") from error
        raise ConnectionError("AWS connection failed") from error

    credentials = assumed["Credentials"]
    session = boto3.Session(
        aws_access_key_id=credentials["AccessKeyId"],
        aws_secret_access_key=credentials["SecretAccessKey"],
        aws_session_token=credentials["SessionToken"],
        region_name=region_name,
    )
    return Connection(
        session=session,
        account_id=account_id,
        source_arn=identity["Arn"],
        assumed_role_arn=assumed["AssumedRoleUser"]["Arn"],
        expiration=credentials["Expiration"],
    )
