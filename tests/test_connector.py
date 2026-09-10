from datetime import UTC, datetime
from unittest.mock import Mock, patch

import pytest
from botocore.exceptions import (
    NoCredentialsError,
    SSOTokenLoadError,
    TokenRetrievalError,
)

from cy06.connector import EXPECTED_ROLE_ARN, connect


def test_connector_behavior_is_offline_and_boundary_safe():
    sts = Mock()
    sts.get_caller_identity.return_value = {
        "Account": "123456789012",
        "Arn": "arn:aws:iam::123456789012:user/test",
    }
    with patch(
        "cy06.connector.boto3.Session", return_value=Mock(client=Mock(return_value=sts))
    ) as session:
        with pytest.raises(ConnectionError, match="source account"):
            connect("profile", EXPECTED_ROLE_ARN)
        session.assert_called_once_with(profile_name="profile")
        sts.assume_role.assert_not_called()

    with pytest.raises(ConnectionError, match="role ARN"):
        connect("profile", "arn:aws:iam::820919093456:role/other")

    sts.get_caller_identity.return_value = {
        "Account": "820919093456",
        "Arn": "arn:aws:iam::820919093456:user/test",
    }
    sts.assume_role.return_value = {
        "Credentials": {
            "AccessKeyId": "key",
            "SecretAccessKey": "secret",
            "SessionToken": "token",
            "Expiration": datetime.now(UTC),
        },
        "AssumedRoleUser": {"Arn": "arn:aws:sts::820919093456:assumed-role/r/s"},
    }
    temporary = Mock()
    with patch("cy06.connector.boto3.Session", side_effect=[Mock(client=Mock(return_value=sts)), temporary]):
        connection = connect("profile", EXPECTED_ROLE_ARN, "us-east-1")
    assert "secret" not in repr(connection) and "token" not in repr(connection)
    assert temporary is connection.session


@pytest.mark.parametrize(
    "exception",
    [
        SSOTokenLoadError(error_msg="sso"),
        TokenRetrievalError(provider="sso", error_msg="token"),
        NoCredentialsError(),
    ],
)
def test_credential_boundary_errors_are_chained(exception):
    with (
        patch("cy06.connector.boto3.Session", side_effect=exception),
        pytest.raises(ConnectionError, match="credentials unavailable") as raised,
    ):
        connect("profile", EXPECTED_ROLE_ARN)
    assert raised.value.__cause__ is exception
