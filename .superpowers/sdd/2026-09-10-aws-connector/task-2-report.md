# Task 2 Report: Non-Secret CLI Smoke Check

## Implementation

Created `src/cy06/__main__.py`.

- Added `python -m cy06` entry point.
- Required `--profile`.
- Defaulted `--role-arn` to `EXPECTED_ROLE_ARN`.
- Defaulted `--region` to `ap-south-1`.
- Called existing `connect(profile, role_arn, region)` interface.
- Printed only `account_id`, `source_arn`, `assumed_role_arn`, ISO-formatted `expiration`, and `status: "ok"`.
- Sent connector failures to stderr and returned exit code 1.
- Added local SSO login and CLI usage instructions to argparse help.
- Never serialized or printed the boto3 session or credentials.

## Checks

- `py_compile src/cy06/__main__.py`: passed.
- `git diff --check`: passed.
- `python -m cy06 --help`: not runnable; bundled Python has no `boto3`.
- `pytest -q tests/test_connector.py`: not runnable; bundled Python has no `pytest`.
- No AWS commands, credentials, or network calls were used.

## Scope

Only Task 2 CLI code and this report were added. Existing generated `__pycache__` files and unrelated documentation changes were not staged.

## Fix Round 1

- Added `tests/test_cli.py` with four offline tests for required profile, default role/region and safe JSON, preserved `ConnectionError` stderr behavior, and unexpected runtime failure handling.
- Added concise help text for `--role-arn` and `--region`.
- Caught unexpected exceptions with fixed text (`error: unexpected connector failure`) to prevent traceback or exception-detail leakage.

## Fix Round 1 Checks

- `python -m py_compile src/cy06/__main__.py tests/test_cli.py`: passed.
- `git diff --check`: passed.
- `python -m pytest -q tests/test_cli.py`: blocked; bundled Python lacks `pytest` and `boto3`.
- No AWS commands, credentials, or network calls were used.
