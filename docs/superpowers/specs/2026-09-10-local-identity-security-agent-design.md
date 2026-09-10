# Local Identity Security Agent Design

## Scope

Add a PostgreSQL-backed local security-tool layer. It imports local IAM-shaped JSON, indexes identities and relationships, records evidence-backed findings, and permits only simulated, explicitly approved remediation. Existing JSON analysis and frontend remain unchanged.

## Data model

PostgreSQL holds one active import document plus normalized `identity_entities`, `relationships`, `privilege_paths`, `security_findings`, `remediation_plans`, and `audit_logs` tables. The import document is canonical so a remediation can be simulated and reapplied deterministically; normalized tables are rebuilt from it inside the same transaction.

## Public tool surface

`list_postgres_tables`, `list_identity_entities`, `get_identity_entity`, `list_privilege_paths`, `get_privilege_path`, `list_security_findings`, `list_remediation_plans`, `list_audit_logs`, `analyze_policy_impact`, `simulate_remediation`, `apply_remediation`, and `verify_remediation` are public methods on `IdentitySecurityTools`.

Direct relationship and policy updates are deliberately private. A caller creates a proposed plan through `simulate_remediation`; `apply_remediation` accepts only the exact approval phrase, locks the plan, updates the active document, rebuilds derived records, verifies the recorded result, and writes an audit event atomically.

## Safety constraints

- PostgreSQL is the only persistence layer; no provider or cloud call occurs.
- Static parameterized SQL only; user input never becomes SQL text.
- Database URLs come only from `CY06_DATABASE_URL`; errors do not echo it.
- Policy detail is not inferred when a document is absent.
- Import, remediation, verification, and auditing use one transaction each.
- A failed or unavailable local connection produces a concise local error.

## Verification

Unit tests use an injected recording connection and cover SQL parameterization, required approval, before/after simulation, transaction ordering, and audit/verification behavior. A live PostgreSQL run is optional because this workstation exposes no configured database URL.
