"""Run a non-secret AWS connection smoke check."""

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from .connector import EXPECTED_ROLE_ARN, connect
from .inventory import InventoryError, load_inventory, summarize_inventory


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Import IAM JSON locally or verify AWS access.",
        epilog=(
            "Login first: aws sso login --profile <profile>; "
            "then run: python -m cy06 --profile <profile>"
        ),
    )
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--profile", help="local AWS profile name")
    source.add_argument("--input", type=Path, help="AWS IAM authorization-details JSON")
    parser.add_argument("--role-arn", default=EXPECTED_ROLE_ARN, help="assumed role ARN")
    parser.add_argument("--region", default="ap-south-1", help="AWS region")
    args = parser.parse_args(argv)

    if args.input:
        try:
            print(json.dumps(summarize_inventory(load_inventory(args.input))))
        except InventoryError as error:
            print(f"error: {error}", file=sys.stderr)
            return 1
        return 0

    if not args.profile:
        parser.error("one of --profile or --input is required")

    try:
        connection = connect(args.profile, args.role_arn, args.region)
    except ConnectionError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    except Exception:  # noqa: BLE001 - CLI must suppress unexpected tracebacks.
        print("error: unexpected connector failure", file=sys.stderr)
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
