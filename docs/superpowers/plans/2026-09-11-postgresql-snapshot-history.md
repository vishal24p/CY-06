# PostgreSQL Snapshot History Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Persist each live AWS IAM collection and its analysis as an immutable snapshot in the existing PostgreSQL database, expose snapshot history, and load saved snapshots in the UI.

**Architecture:** Extend `IdentitySecurityTools` with one append-only snapshot table while retaining existing latest-state normalized indexes. Make the Python live endpoint collect, analyze, and persist once in one transaction; Next.js proxies the result and displays saved history.

**Tech Stack:** Python 3.11+, FastAPI, psycopg 3, PostgreSQL 18, pytest, Next.js 16, React 19, TypeScript.

## Global Constraints

- Use existing `CY06_DATABASE_URL` and existing `cy06_identity_security` database only.
- No Docker, replacement database, AWS writes, access keys, or credential logging.
- Schema migration is idempotent and preserves existing rows.
- Raw inventory and analysis report are immutable `JSONB` snapshot evidence.
- SQL is static and parameterized.
- Database failure rolls back snapshot, latest-state rebuild, and audit together.

---

### Task 1: Snapshot persistence boundary

**Files:**
- Modify: `src/cy06/identity_security.py`
- Test: `tests/test_identity_security.py`

**Interfaces:**
- Consumes: `analyze_inventory(inventory)` and existing `_rebuild`, `_write_state`, `_write_audit` methods.
- Produces: `save_snapshot(account_id: str, inventory: Mapping[str, Any], report: Mapping[str, Any]) -> dict[str, Any]`, `list_snapshots(limit: int = 20, offset: int = 0)`, and `get_snapshot(snapshot_id: str)`.

- [ ] **Step 1: Write failing persistence tests**

Add recording-connection tests proving `_SCHEMA` contains `inventory_snapshots`, `save_snapshot` inserts snapshot before latest-state rebuild and commits once, list queries are bounded/newest-first, and missing snapshot raises `IdentitySecurityError("snapshot not found")`.

- [ ] **Step 2: Run focused tests and confirm failure**

Run: `uv run pytest tests/test_identity_security.py -q`
Expected: FAIL because snapshot methods/table do not exist.

- [ ] **Step 3: Add idempotent schema and minimal methods**

Add table columns `snapshot_id UUID PRIMARY KEY`, `account_id TEXT NOT NULL`, `collected_at TIMESTAMPTZ NOT NULL DEFAULT now()`, `inventory JSONB NOT NULL`, `report JSONB NOT NULL`, and integer summary counts. In `save_snapshot`, deep-copy inputs, generate UUID, insert snapshot, update active state, rebuild indexes, and audit within the existing single write transaction. Return snapshot ID, collected timestamp, inventory, and report. List only summary columns; get returns full documents.

- [ ] **Step 4: Run focused tests**

Run: `uv run pytest tests/test_identity_security.py -q`
Expected: PASS.

---

### Task 2: Live and history API

**Files:**
- Modify: `src/cy06/api.py`
- Test: `tests/test_api.py`

**Interfaces:**
- Consumes: Task 1 snapshot methods and existing AWS `connect`/`collect_inventory` functions.
- Produces: persisted `GET /api/v1/live`, `GET /api/v1/snapshots`, and `GET /api/v1/snapshots/{snapshot_id}`.

- [ ] **Step 1: Write failing API tests**

Mock AWS collection and `IdentitySecurityTools`. Assert live analyzes once, saves once, and returns `snapshot_id`, `collected_at`, `inventory`, and `report`. Assert database errors become generic HTTP 503. Assert list/get routes delegate with bounded query parameters.

- [ ] **Step 2: Run focused tests and confirm failure**

Run: `uv run pytest tests/test_api.py -q`
Expected: FAIL because live persistence/history routes do not exist.

- [ ] **Step 3: Implement API wiring**

Create one `IdentitySecurityTools` instance per request. Analyze collected inventory once, pass it into `save_snapshot`, and return saved payload. Map `IdentitySecurityError` to `HTTPException(503, "PostgreSQL snapshot storage unavailable")`; never return connection details. Add `limit` constrained to `1..100` and non-negative `offset`.

- [ ] **Step 4: Run focused tests**

Run: `uv run pytest tests/test_api.py -q`
Expected: PASS.

---

### Task 3: Snapshot history UI

**Files:**
- Modify: `frontend/src/lib/types.ts`
- Modify: `frontend/src/lib/api.ts`
- Modify: `frontend/src/app/page.tsx`
- Modify: `frontend/src/app/api/live/route.ts`
- Create: `frontend/src/app/api/snapshots/route.ts`
- Create: `frontend/src/app/api/snapshots/[snapshotId]/route.ts`

**Interfaces:**
- Consumes: Task 2 response shapes.
- Produces: `SnapshotSummary`, `loadSnapshots()`, `loadSnapshot(snapshotId)`, live saved-status label, and history selector.

- [ ] **Step 1: Simplify live proxy**

Forward Python `/api/v1/live` directly; remove duplicate analysis from the Next.js live route.

- [ ] **Step 2: Add typed history clients and proxies**

Add summary fields for ID, account, timestamp, and counts. Proxy only fixed backend paths; encode `snapshotId`. Validate response objects before returning them to UI.

- [ ] **Step 3: Add minimal accessible selector**

After successful live load, refresh newest-first history. Render native `<select aria-label="Saved AWS snapshot">`; choosing an item loads stored inventory/report and resets selected path/preview state. Show truncated snapshot ID and collection time.

- [ ] **Step 4: Verify frontend**

Run: `npm run lint`
Expected: PASS.

Run: `npm run build`
Expected: PASS with `/api/live`, `/api/snapshots`, and `/api/snapshots/[snapshotId]` routes.

---

### Task 4: Existing database migration and end-to-end verification

**Files:**
- Modify: `README.md`

**Interfaces:**
- Consumes: Tasks 1-3 and existing PostgreSQL cluster at `C:\Users\visha\.codex\local-postgres\cy06-identity-security`.
- Produces: migrated existing database and verified live persisted snapshot flow.

- [ ] **Step 1: Start existing cluster without changing configuration**

Run PostgreSQL 18 `pg_ctl start` against the existing cluster directory. Verify port `5434` listens and load `.env` through `load_project_env`; do not print URL.

- [ ] **Step 2: Apply idempotent migration**

Run `IdentitySecurityTools().initialize()`. Verify existing table row counts remain and `inventory_snapshots` exists.

- [ ] **Step 3: Run all automated checks**

Run: `uv run pytest -q`
Expected: all tests pass.

Run in `frontend`: `npm run lint` and `npm run build`
Expected: PASS.

- [ ] **Step 4: Verify real live persistence**

Call `/api/v1/live`, capture returned snapshot ID, then load the same ID through `/api/v1/snapshots/{snapshot_id}`. Assert account `820919093456`, 8 users, 3 groups, 8 roles, 9 policies, and exact report equality.

- [ ] **Step 5: Document existing-cluster startup and history behavior**

Update README without credentials. State that every successful live load saves an immutable local snapshot and AWS remains read-only.
