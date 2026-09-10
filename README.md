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

### Coverage input contract

The required AWS-shaped sections remain `UserDetailList`, `GroupDetailList`, `RoleDetailList`, and `Policies`. The following optional sections add context without changing the IAM export:

- `IdentityMetadata`: trusted HR/IdP rows joined by `PrincipalArn`; includes `EmployeeId`, `DisplayName`, `JobTitle`, `Department`, `Manager`, `EmploymentType`, `Status`, and `IdentityProvider`. CY-06 never guesses these fields from an IAM username.
- `ResourcePolicies`: `{PolicyName, PolicyArn, ResourceArn, ResourceType, PolicyDocument}` rows for S3, KMS, and similar resources.
- `Organizations`: `{OrganizationId, RootId, OUs, Accounts, SCPs}` with parent IDs and SCP target IDs.
- `Sessions`: `{SessionArn, SourcePrincipal, RoleArn, SessionPolicy}` for temporary STS sessions.
- `PermissionsBoundary`: an optional object on a user or role, with `PermissionsBoundaryArn`, `PolicyName`, and `PolicyDocument`.

The analyzer combines these sources conservatively. Explicit Deny wins; boundaries and SCPs restrict permissions rather than granting them. Missing session or policy context is surfaced as `review_required`. The current release models resource-policy relationships and Deny gates; it does not claim access solely from a resource policy or fully evaluate every AWS condition key.

For the included fixture, the analyzer returns 53 graph nodes, 41 graph edges, and coverage counts of 8 metadata rows, 2 resource policies, 1 boundary, 1 SCP, and 2 sessions. All fixture people and HR values are synthetic.

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

## Local identity-security database

The PostgreSQL-backed identity-security tools use only a local database. Set `CY06_DATABASE_URL` in your shell, then create an `IdentitySecurityTools` instance and call `initialize()` before importing local IAM-shaped JSON. Do not commit database URLs, passwords, tokens, or imported production data.

```powershell
$env:CY06_DATABASE_URL = "postgresql://<local-user>@localhost:<port>/<database>"
python -m pip install -e .
```

Use `simulate_remediation()` first. `apply_remediation()` accepts only the exact approval text `Approve this change`, then rebuilds evidence, verifies the stored result, and writes an audit record in one database transaction.

## Read-only chat agent

The chat agent uses the locally imported analysis data and exposes no mutation actions. Configure these environment variables as needed:

- `CY06_DATABASE_URL`
- `CY06_CHAT_BASE_URL`
- `CY06_CHAT_MODEL`
- `CY06_CHAT_API_KEY` (optional)
- `CY06_CHAT_TIMEOUT_SECONDS` (optional; defaults to 30, maximum 300)

The browser posts `{ "messages": [{ "role": "user" | "assistant", "content": "..." }] }` to `/api/chat`, which proxies to `POST /api/v1/chat`; replies contain a message and read-only tool names. When configured with a remote provider, that provider receives chat messages plus read-only tool-call and tool-result data.
