# PostgreSQL Snapshot History Design

## Scope

Persist every successful live AWS IAM collection in the existing `cy06_identity_security` PostgreSQL database. Preserve the current normalized latest-state tables and remediation workflow. Do not create another database, Docker service, or AWS write path.

## Existing system

The project already uses `IdentitySecurityTools` and `psycopg`, with its connection supplied only by `CY06_DATABASE_URL`. The existing database holds one canonical active inventory in `identity_state` and rebuilds `identity_entities`, `policies`, `relationships`, `privilege_paths`, and `security_findings` transactionally. Remediation plans and audit logs already store simulated local changes.

The existing PostgreSQL 18 cluster lives at `C:\Users\visha\.codex\local-postgres\cy06-identity-security` and listens on port `5434` when started. The migration must run against this database through the existing environment URL.

## Decision

Add one append-only `inventory_snapshots` table. Each row contains:

- generated snapshot UUID;
- AWS account ID;
- collection timestamp;
- immutable raw IAM inventory as `JSONB`;
- immutable analysis report as `JSONB`;
- summary counts for users, groups, roles, policies, findings, paths, critical findings, and high findings.

Keep existing normalized tables as the latest-state query index. Do not add `snapshot_id` to every normalized table in this version.

## Data flow

1. `GET /api/v1/live` assumes the existing read-only AWS role and collects IAM authorization details.
2. The backend analyzes the collected inventory once.
3. One PostgreSQL transaction inserts the immutable snapshot, replaces `identity_state`, rebuilds latest-state indexes, and records the import audit event.
4. The API returns inventory, report, snapshot ID, and collection timestamp.
5. The frontend displays the persisted snapshot ID and uses the returned report without re-analyzing the same payload.
6. Remediation preview selects a stored snapshot, creates a modified in-memory document, stores a proposed remediation plan, and compares before/after analysis. It does not modify AWS.

## Failure behavior

Live collection is not reported as persisted unless the complete PostgreSQL transaction commits. AWS or database failures return a concise `503` response without credentials, connection strings, partial snapshots, or partial latest-state indexes. Existing saved data remains unchanged after failure.

Schema initialization remains idempotent through `CREATE TABLE IF NOT EXISTS`. Existing tables and rows are preserved. No destructive migration is required.

## API and UI

The live backend response becomes:

```json
{
  "snapshot_id": "uuid",
  "collected_at": "timestamp",
  "inventory": {},
  "report": {}
}
```

Add read-only endpoints for listing snapshot summaries and loading one snapshot. Limit and offset inputs remain bounded and parameterized. The frontend adds a small snapshot-history selector; selecting a snapshot loads its stored inventory and report.

## Security constraints

- AWS connection remains read-only.
- Database URL remains environment-only and is never logged or returned.
- SQL remains static and parameterized.
- Raw snapshots are immutable through the public application surface.
- Remediation remains local simulation with explicit approval and audit records.
- No automatic deletion or retention job is added.

## Verification

- Migration preserves existing rows and can run repeatedly.
- Successful live collection creates exactly one snapshot and updates latest-state indexes in one transaction.
- Failed analysis or database write creates no partial snapshot.
- Snapshot list is newest-first and bounded.
- Loading a snapshot returns its exact stored inventory and report.
- Live endpoint returns its snapshot ID and avoids duplicate analysis.
- Existing analyzer, remediation, connector, API, and frontend tests continue to pass.

## Alternatives rejected

- Adding `snapshot_id` to every normalized table: stronger historical SQL querying, but unnecessary migration size for current product needs.
- Storing only raw snapshots: smaller schema, but loses immutable evidence of the risk score and findings shown to the user.
- New Docker PostgreSQL: duplicates the existing database and violates the selected deployment model.
