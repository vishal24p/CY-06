# Local Identity Security Agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver local PostgreSQL-backed identity-security tools with evidence, approval-gated remediation, verification, and audit history.

**Architecture:** A new Python module owns static PostgreSQL schema, import/index rebuild, read tools, policy impact, simulation, and transactional remediation. Existing JSON analyzer stays read-only and supplies deterministic risk findings during rebuilds.

**Tech Stack:** Python 3.11+, psycopg 3, PostgreSQL, pytest.

**Spec:** `docs/superpowers/specs/2026-09-10-local-identity-security-agent-design.md`

## Global Constraints

- Use only local PostgreSQL configured through `CY06_DATABASE_URL`.
- Do not accept arbitrary SQL or expose direct mutation helpers.
- Require exact `Approve this change` text before an applied change.
- Every applied change recalculates derived records and writes an audit row in its transaction.

---

### Task 1: Add PostgreSQL schema and connection boundary

**Files:**
- Create: `src/cy06/identity_security.py`
- Modify: `pyproject.toml`
- Test: `tests/test_identity_security.py`

**Interfaces:**
- `IdentitySecurityTools(database_url: str | None = None, connection_factory: Callable | None = None)`
- `initialize() -> None`
- `import_inventory(inventory: Mapping[str, Any]) -> dict[str, int]`

- [x] Write a failing test that rejects an absent database URL and asserts parameterized static schema execution.
- [x] Add psycopg 3 dependency, schema, injected connection boundary, and concise connection errors.
- [x] Run `pytest tests/test_identity_security.py -q`.

### Task 2: Add import, evidence, and read/analysis tools

**Files:**
- Modify: `src/cy06/identity_security.py`
- Test: `tests/test_identity_security.py`

**Interfaces:**
- `list_identity_entities`, `get_identity_entity`, `list_privilege_paths`, `get_privilege_path`, `list_security_findings`, `list_remediation_plans`, `list_audit_logs`, `analyze_policy_impact`.

- [x] Write failing tests for missing policy documents, sort allowlisting, and relationship evidence.
- [x] Normalize imported users, groups, roles, policies, resources, memberships, attachments, and trust relationships; derive findings using existing analyzer.
- [x] Run focused tests.

### Task 3: Add safe simulation and applied remediation

**Files:**
- Modify: `src/cy06/identity_security.py`
- Test: `tests/test_identity_security.py`

**Interfaces:**
- `simulate_remediation(change: Mapping[str, Any]) -> dict[str, Any]`
- `apply_remediation(plan_id: str, approval: str) -> dict[str, Any]`
- `verify_remediation(plan_id: str) -> dict[str, Any]`

- [x] Write failing tests for approval rejection, simulation, and applied transaction ordering.
- [x] Support six approved change types, transactional apply/rebuild/verify/audit, and no public direct updates.
- [x] Run focused tests and full Python suite.

### Task 4: Document setup and verify package

**Files:**
- Modify: `README.md`
- Test: `tests/test_identity_security.py`

- [x] Document local-only database setup with `CY06_DATABASE_URL`; never include credentials.
- [x] Install package dependency, run focused and full tests; live verification is deferred because no database URL is configured.
