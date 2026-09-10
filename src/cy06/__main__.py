"""Run a non-secret AWS connection smoke check."""

import argparse
import json
import sys
from collections.abc import Sequence

from .connector import EXPECTED_ROLE_ARN, connect


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Verify CY-06 AWS SSO access and assumed-role identity.",
        epilog=(
            "Login first: aws sso login --profile <profile>; "
            "then run: python -m cy06 --profile <profile>"
        ),
    )
    parser.add_argument("--profile", required=True, help="local AWS profile name")
    parser.add_argument("--role-arn", default=EXPECTED_ROLE_ARN)
    parser.add_argument("--region", default="ap-south-1")
    args = parser.parse_args(argv)

    try:
        connection = connect(args.profile, args.role_arn, args.region)
    except ConnectionError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    print(
        json.dumps(
            {
                "account_id": connection.account_id,
                "source_arn": connection.source_arn,
                "assumed_role_arn": connection.assumed_role_arn,
                "expiration": connection.expiration.isoformat(),
                "status": "ok",
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
