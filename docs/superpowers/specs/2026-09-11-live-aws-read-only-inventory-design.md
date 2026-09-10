# Live AWS Read-Only Inventory Design

## Goal

Connect CY-06 to one non-production AWS account (`820919093456`) through AWS IAM Identity Center, fetch live IAM authorization data without changing AWS, and feed it into the existing analyzer only after each connection gate passes.

## Architecture

Use the existing two-hop authentication boundary:

1. Local AWS CLI profile `cy06-dev` authenticates through IAM Identity Center.
2. Its Identity Center permission set may assume only `arn:aws:iam::820919093456:role/PrivilegePathFinderReadOnlyRole`.
3. That dedicated role may call only the IAM read API needed for the first inventory: `iam:GetAccountAuthorizationDetails`.
4. CY-06 uses the temporary assumed-role boto3 session to paginate the live inventory into the same document shape already accepted by the analyzer.
5. The existing analyzer and UI consume that document unchanged. Remediation remains local simulation only.

No access keys, AWS-hosted application deployment, Organizations/SCP collection, CloudTrail session analysis, resource-policy collection, or AWS mutation is included.

## AWS Resources

### Identity Center permission set

- Name: `CY06Connector`
- Assigned to the user's Identity Center user in account `820919093456`
- Permission: `sts:AssumeRole` only for `PrivilegePathFinderReadOnlyRole`

### IAM role

- Name: `PrivilegePathFinderReadOnlyRole`
- Trust: only the account's generated `AWSReservedSSO_CY06Connector_*` role, using AWS's wildcard-safe Identity Center trust-policy pattern
- Permission: `iam:GetAccountAuthorizationDetails`
- No write actions

## Data Flow

`cy06-dev` SSO login -> source STS identity -> assume read-only role -> paginated IAM authorization snapshot -> existing inventory validation -> existing analysis report -> existing UI.

The first live scan includes IAM users, groups, roles, managed policies, inline policies, trust policies, relationships, and permission boundaries returned by `GetAccountAuthorizationDetails`.

## Failure Handling

- Fail closed when the profile is absent or logged out.
- Reject any source account other than `820919093456`.
- Reject any role ARN other than the dedicated role.
- Convert AWS authentication, authorization, throttling, and pagination failures into concise errors without logging credentials or tokens.
- Do not fall back silently to fixtures when a live scan fails.

## Verification Gates

1. `aws sso login --profile cy06-dev` succeeds.
2. `aws sts get-caller-identity --profile cy06-dev` reports account `820919093456`.
3. Existing connector assumes `PrivilegePathFinderReadOnlyRole` and prints only non-secret metadata.
4. Assumed role completes a paginated `GetAccountAuthorizationDetails` call.
5. Saved live payload passes existing inventory validation and analyzer tests.
6. Local API returns an analysis report from live data.
7. UI renders that report while remediation remains explicitly local-only.

## Security Constraints

- Temporary SSO and STS credentials only.
- Never print, persist, upload, or commit credentials, tokens, or MFA values.
- Least-privilege policies at both hops.
- No AWS-changing API action in this phase.
- User completes browser authentication and any MFA prompts.

## Deferred Scope

- AWS Organizations and SCPs
- CloudTrail-derived active sessions
- Service resource policies
- Multi-account scanning
- AWS deployment
- Applying remediations to AWS

