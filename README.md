# CY-06 Module 1

## Local JSON import

Run the importer without AWS credentials using the AWS-shaped sample fixture:

```powershell
.venv\Scripts\python.exe -m cy06 --input data\sample-iam-inventory.json
```

The output is a safe import summary. The fixture is synthetic and contains no credentials.

## Local AWS SSO setup and run

Configure a named AWS CLI SSO profile locally. Do not add access keys to the repository.

```text
python -m pip install -e .
aws sso login --profile <profile>
python -m cy06 --profile <profile>
```

The CLI uses region `ap-south-1` by default. Override it with `--region <region>` when needed. The assumed role defaults to:

```text
arn:aws:iam::820919093456:role/PrivilegePathFinderReadOnlyRole
```

## Verification

Successful output is JSON with `status: "ok"`, account ID `820919093456`, source ARN, assumed-role ARN, and expiration. It contains no access keys, secret keys, session tokens, or boto3 session data.

Failures are concise messages on stderr with a non-zero exit code. Module 1 performs identity verification and read-only role assumption only; inventory collection is deferred to Module 2.
