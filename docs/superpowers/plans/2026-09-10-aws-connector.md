# AWS Connector Module 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prove that CY-06 can use a local AWS SSO profile to assume the existing read-only role and report identity without exposing credentials.

**Architecture:** A small Python module creates a boto3 session from a named local profile, verifies the source identity, assumes `PrivilegePathFinderReadOnlyRole`, and returns a temporary-credential boto3 session. The CLI prints only non-secret connection metadata.

**Tech Stack:** Python 3.11+, boto3, AWS IAM Identity Center/SSO profile.

**Spec:** CY-06 project scope agreed in conversation on 2026-09-10.

## Global Constraints

- Use AWS account `820919093456` and role `arn:aws:iam::820919093456:role/PrivilegePathFinderReadOnlyRole`.
- Read-only AWS access only; do not create, update, or delete AWS resources.
- Never print, persist, or commit access keys, secret keys, session tokens, passwords, or MFA codes.
- Support local AWS CLI profiles; do not add permanent IAM access keys.
- Keep Module 1 limited to authentication and identity verification; inventory collection belongs to Module 2.

---

### Task 1: Create the minimal Python package and connector

**Files:**
- Create: `pyproject.toml`
- Create: `src/cy06/__init__.py`
- Create: `src/cy06/connector.py`

**Interfaces:**
- Consumes: AWS profile name, role ARN, and optional region.
- Produces: `connect(profile_name, role_arn, region_name) -> Connection` and `Connection.session`, a boto3 session backed by temporary assumed-role credentials.

- [ ] **Step 1: Define dependency and package metadata**

Declare Python 3.11+ and `boto3` as the only runtime dependency. Configure the `cy06` package from `src/`.

- [ ] **Step 2: Implement source-identity verification and role assumption**

Use `boto3.Session(profile_name=profile_name)`, call `sts.get_caller_identity()`, call `sts.assume_role(RoleArn=role_arn, RoleSessionName="cy06-local")`, then create a new boto3 session from the returned temporary credentials. Store account ID, source ARN, assumed-role ARN, and expiration in a small immutable result object. Do not include credentials in its representation.

- [ ] **Step 3: Add explicit errors at the AWS boundary**

Raise a concise `ConnectionError` when the profile is missing, SSO login is incomplete, the source account differs from `820919093456`, or `AssumeRole` is denied. Preserve the original AWS error as the exception cause without printing it from library code.

### Task 2: Add a non-secret CLI smoke check

**Files:**
- Create: `src/cy06/__main__.py`

**Interfaces:**
- Consumes: `--profile`, `--role-arn`, and optional `--region`.
- Produces: JSON containing account ID, source ARN, assumed-role ARN, expiration, and `status: "ok"`; failures go to stderr with a non-zero exit code.

- [ ] **Step 1: Parse required CLI arguments**

Require `--profile` and default `--role-arn` to the project role ARN. Accept `--region` with default `ap-south-1`.

- [ ] **Step 2: Print only safe connection metadata**

Call `connect`, serialize its metadata with `json.dumps`, and never serialize the boto3 session or credential object.

- [ ] **Step 3: Add the local run instructions**

Document:

```text
aws sso login --profile <profile>
python -m cy06 --profile <profile>
```

The expected success output contains the account ID and assumed role ARN, not secrets.

### Task 3: Verify Module 1

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Run syntax/package verification**

Run `python -m compileall src` and `python -m cy06 --help`.

- [ ] **Step 2: Run the real AWS smoke check**

After the user configures an SSO profile, run `aws sso login --profile <profile>` and `python -m cy06 --profile <profile>`. Expected result: status `ok`, account `820919093456`, and the exact read-only role ARN.

- [ ] **Step 3: Confirm no secret leakage**

Inspect CLI output and repository status. Confirm no credential fields, `.env` files, or generated credential files are added.

