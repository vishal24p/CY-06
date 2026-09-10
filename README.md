# CY-06

Read-only IAM privilege-path analysis. The Python rules engine is authoritative; the Next.js UI only presents its findings.

## Local JSON import

Run the importer without AWS credentials using the AWS-shaped sample fixture:

```powershell
.venv\Scripts\python.exe -m cy06 --input data\sample-iam-inventory.json
```

The output is a safe import summary. The fixture is synthetic and contains no credentials.

## Local analyzer and UI

Start the Python API in one terminal:

```powershell
.venv\Scripts\python.exe -m uvicorn cy06.api:app --reload --port 8000
```

Start the Next.js UI in another:

```powershell
cd frontend
npm run dev
```

Open `http://localhost:3000`, upload `data\sample-iam-inventory.json`, and review the privilege graph, source tables, and findings. The UI sends the file to the local API; it does not contact AWS.

The sample contains 8 users, 4 groups, 6 roles, and 8 policies. It intentionally mixes safe access with group inheritance, unrestricted access, user lifecycle permissions, and privileged role-assumption paths so the graph has meaningful relationships to inspect.

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

Failures are concise messages on stderr with a non-zero exit code. AWS collection remains read-only and is separate from the local JSON workflow.
