# Live AWS Read-Only Inventory Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Configure and verify least-privilege access to account `820919093456`, then connect live IAM inventory to the existing CY-06 analyzer.

**Architecture:** Local profile `cy06-dev` authenticates with IAM Identity Center and assumes `PrivilegePathFinderReadOnlyRole`. After AWS-only smoke tests pass, one boto3 collector paginates `GetAccountAuthorizationDetails` and sends its existing-compatible result through the current analyzer/API/UI path.

**Tech Stack:** AWS IAM Identity Center, IAM, STS, AWS CLI v2, Python 3.11+, boto3, FastAPI, Next.js.

## Global Constraints

- One non-production account: `820919093456`.
- Read-only AWS access; no create, update, delete, or remediation calls from CY-06.
- Temporary SSO/STS credentials only; never expose or commit credentials or tokens.
- Do not edit application code until Tasks 1 and 2 pass against real AWS.
- Keep existing local uploads, fixtures, analysis, and remediation preview behavior.

---

### Task 1: Provision least-privilege AWS access

**Files:** None.

**Interfaces:**
- Consumes: Identity Center user assignment for account `820919093456`.
- Produces: `CY06Connector` source permission set and `PrivilegePathFinderReadOnlyRole` target role.

- [ ] Create Identity Center permission set `CY06Connector` with an inline policy allowing only `sts:AssumeRole` on `arn:aws:iam::820919093456:role/PrivilegePathFinderReadOnlyRole`.
- [ ] Assign `CY06Connector` to the user's Identity Center user for account `820919093456`.
- [ ] Create IAM role `PrivilegePathFinderReadOnlyRole`; trust the account principal only when `aws:PrincipalArn` matches the generated `AWSReservedSSO_CY06Connector_*` ARN.
- [ ] Attach an inline policy allowing only `iam:GetAccountAuthorizationDetails` on `*` because IAM list/read authorization APIs do not support resource-level restriction.
- [ ] Review both policies in AWS Console and confirm neither contains write actions nor wildcard actions.

**Verification:** AWS Console shows assignment, trust policy, and read policy exactly as specified.

### Task 2: Configure and prove local AWS authentication

**Files:** User-local `C:\Users\visha\.aws\config` managed by AWS CLI; never committed.

**Interfaces:**
- Consumes: Identity Center start URL, SSO region, account `820919093456`, and `CY06Connector` assignment.
- Produces: named profile `cy06-dev` and temporary authenticated session.

- [ ] Run `aws configure sso --profile cy06-dev`; select account `820919093456`, role `CY06Connector`, default region `ap-south-1`, and JSON output.
- [ ] Run `aws sso login --profile cy06-dev`; user completes browser authentication/MFA.
- [ ] Run `aws sts get-caller-identity --profile cy06-dev`; require account `820919093456`.
- [ ] Run `python -m cy06 --profile cy06-dev`; require status `ok` and assumed role `PrivilegePathFinderReadOnlyRole`.
- [ ] Invoke `GetAccountAuthorizationDetails` with the assumed-role session; require at least one successful page and no authorization error.

**Verification:** All five gates pass; output contains no credential fields.

### Task 3: Add the minimal live IAM collector

**Files:**
- Create: `src/cy06/aws_inventory.py`
- Modify: `src/cy06/__main__.py`
- Test: `tests/test_aws_inventory.py`
- Test: `tests/test_cli.py`

**Interfaces:**
- Consumes: `boto3.Session` from `Connection.session`.
- Produces: `collect_inventory(session: Any) -> dict[str, Any]` with `UserDetailList`, `GroupDetailList`, `RoleDetailList`, and `Policies`.

- [ ] Write a failing paginator test using a fake IAM client with two pages and assert list fields are merged without losing permission-boundary or policy documents.
- [ ] Run `pytest tests/test_aws_inventory.py -q`; expect failure because `collect_inventory` does not exist.
- [ ] Implement `collect_inventory` with the installed boto3 paginator:

```python
def collect_inventory(session: Any) -> dict[str, Any]:
    pages = session.client("iam").get_paginator("get_account_authorization_details").paginate()
    inventory = {name: [] for name in ("UserDetailList", "GroupDetailList", "RoleDetailList", "Policies")}
    for page in pages:
        for name in inventory:
            inventory[name].extend(page.get(name, []))
    return inventory
```

- [ ] Add CLI `--live` mode requiring `--profile`; connect, collect, validate with `summarize_inventory`, and print only counts.
- [ ] Run focused tests; require pass.
- [ ] Commit collector slice.

### Task 4: Expose live analysis through the local API

**Files:**
- Modify: `src/cy06/api.py`
- Test: `tests/test_api.py`

**Interfaces:**
- Consumes: server-side configured profile name `CY06_AWS_PROFILE=cy06-dev`.
- Produces: `POST /api/v1/analyze-live` returning the existing `AnalysisReport` schema.

- [ ] Write failing API tests for success and concise AWS failure; mock only the AWS boundary.
- [ ] Run focused tests and confirm failure.
- [ ] Add endpoint that calls existing `connect`, new `collect_inventory`, then existing analyzer. Do not accept role ARN or account ID from clients.
- [ ] Map connector/collector failures to safe HTTP errors without AWS credential details.
- [ ] Run `pytest tests/test_api.py -q`; require pass.
- [ ] Commit API slice.

### Task 5: Connect the existing UI only after live API passes

**Files:**
- Modify: `frontend/src/lib/api.ts`
- Modify: `frontend/src/app/page.tsx`
- Test: `frontend/tests/page.test.tsx`

**Interfaces:**
- Consumes: `POST /api/v1/analyze-live`.
- Produces: user-triggered “Scan AWS account” flow rendering the existing report components.

- [ ] Write a failing UI test asserting the scan is explicit, shows loading/error state, and renders the returned existing report shape.
- [ ] Run the focused frontend test and confirm failure.
- [ ] Add one API helper and one button reusing the current report state; keep upload/demo paths unchanged.
- [ ] Keep remediation copy explicit that no AWS change occurs.
- [ ] Run frontend tests and build; require pass.
- [ ] Commit UI slice.

### Task 6: End-to-end verification

**Files:**
- Modify: `README.md`

**Interfaces:**
- Consumes: completed AWS setup and local services.
- Produces: reproducible operator instructions and verified end-to-end live scan.

- [ ] Run Python tests, Ruff, frontend tests, and frontend build.
- [ ] Log in with `cy06-dev`, run CLI live scan, then local API live scan.
- [ ] Open local frontend, trigger “Scan AWS account,” and verify account data renders.
- [ ] Verify remediation preview remains local-only and no CloudTrail write event from CY-06 exists.
- [ ] Document AWS setup, login, scan, expiry/error recovery, and read-only limits in `README.md`.
- [ ] Review git diff for secrets and unrelated user changes; commit docs only after checks pass.

