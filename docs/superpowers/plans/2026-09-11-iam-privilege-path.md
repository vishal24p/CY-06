# AWS IAM Privilege Path Finder Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make CY-06 prove one concrete claim: a low-privilege AWS identity can reach administrative access through an explainable permission path, and the smallest fix breaks that path.

**Architecture:** Keep `src/cy06/rules/engine.py` authoritative and read-only. Add a bounded path model over the existing AWS-shaped inventory, expose ranked paths through the existing analysis report, then make the existing Next.js page lead with the top path and its before/after remediation result. Keep the graph, chat, database, and AWS connector as supporting or optional features.

**Tech Stack:** Python standard library, FastAPI, pytest, Next.js 16, React, TypeScript, existing Tailwind CSS.

**Spec:** `README.md` and the current hackathon demo plans.

## Global Constraints

- AWS IAM only for the focused demo.
- Analysis remains read-only; no AWS writes and no mutation of uploaded input.
- No new dependencies.
- Explicit Deny, boundaries, SCPs, and missing context remain security-relevant.
- Preserve existing dirty-worktree changes.
- Use the existing fixture and components before adding new abstractions.

---

### Task 1: Define and test the bounded attack path

**Files:**
- Modify: `tests/test_rules.py`
- Modify: `src/cy06/rules/engine.py`

**Interfaces:**
- Consumes: AWS-shaped `UserDetailList`, `GroupDetailList`, `RoleDetailList`, and `Policies`.
- Produces: `report["paths"]`, a list of ranked objects with `principal`, `target`, `risk_score`, `risk`, `hops`, `path`, `reason`, `remediation`, and `confidence`.

- [x] Write a failing test proving a user can reach an administrator role through a group permission and role trust.
- [x] Run `pytest tests/test_rules.py -q` and confirm the new assertion fails because `paths` is absent.
- [x] Implement the smallest bounded traversal: user/group membership, `sts:AssumeRole`, role trust, and administrator-level target detection.
- [x] Reuse current policy parsing, deny, boundary, SCP, and condition checks; do not duplicate IAM document parsing.
- [x] Rank paths by risk score, then hop count, then stable path text.
- [x] Run the focused test and the full backend suite.

### Task 2: Make the checked-in demo contain one obvious path

**Files:**
- Modify: `data/sample-iam-inventory.json`
- Modify: `tests/test_api.py`

**Interfaces:**
- Consumes: Task 1 path output.
- Produces: deterministic demo data with a top-ranked path and stable API assertions.

- [x] Confirm the existing synthetic fixture already contains the minimum relationships needed for one named path.
- [x] Write a failing API test asserting the demo analysis has at least one path and a privileged target.
- [x] Run the test and confirm it fails before the fixture/response change.
- [x] Keep the fixture unchanged because its existing path is sufficient.
- [x] Run backend tests and inspect the demo report.

### Task 3: Return the path through the existing frontend contract

**Files:**
- Modify: `frontend/src/lib/types.ts`
- Modify: `frontend/src/lib/api.ts` only if response mapping requires it
- Modify: `tests/test_api.py` only if API contract coverage is missing

**Interfaces:**
- Consumes: `AnalysisReport.paths` from Task 1.
- Produces: typed `PrivilegePath` data available to the page and remediation preview.

- [x] Add the smallest TypeScript type matching the Python path fields.
- [x] Use the production TypeScript build as the contract check for the new field.
- [x] Update the shared report type and run `npm --prefix frontend run lint`.

### Task 4: Put the top path first in the demo UI

**Files:**
- Modify: `frontend/src/app/page.tsx`
- Create: `frontend/src/components/TopPrivilegePath.tsx` only if page composition becomes materially clearer
- Modify: `frontend/src/components/FindingsList.tsx` only if selection must share path state

**Interfaces:**
- Consumes: typed report paths and existing `IamGraph`, `FindingsList`, and `RemediationPreview`.
- Produces: first-screen narrative showing identity, complete path, risk, reason, and fix.

- [x] Add compile-visible usage for the top path.
- [x] Render the top path before the general graph and source inventory.
- [x] Keep graph and findings as supporting evidence.
- [x] Remove or shorten copy that presents chat/coverage as the primary product.
- [x] Preserve keyboard access, labels, loading, empty, and error states.
- [x] Run lint and production build.

### Task 5: Verify remediation breaks the actual path

**Files:**
- Modify: `frontend/src/components/RemediationPreview.tsx`
- Modify: `frontend/src/lib/api.ts` only if the preview response needs path data
- Modify: `tests/test_rules.py` or `tests/test_api.py`

**Interfaces:**
- Consumes: selected finding/path and copied inventory.
- Produces: before/after path state showing whether the selected path still exists.

- [x] Validate path disappearance through the same analyzer used by the preview flow.
- [x] Confirm the production build catches the updated preview contract.
- [x] Change the preview comparison to compare the selected path, not only matching principal/permission findings.
- [x] Keep preview local and unapplied.
- [x] Run backend tests, lint, and build.

### Task 6: Tighten the guided demo and documentation

**Files:**
- Modify: `README.md`
- Modify: `frontend/src/components/ChatPanel.tsx` only if suggested questions need to reference the top path

**Interfaces:**
- Consumes: completed report and UI flow.
- Produces: judge-ready instructions centered on one attack path.

- [x] Rewrite the product description around AWS IAM privilege-path discovery.
- [x] Document the exact guided demo sequence.
- [x] Mark live AWS, PostgreSQL, and provider chat as optional extensions.
- [x] Run the complete verification suite and validate the guided demo through the API contract and production build.

### Final review

- [x] `pytest -q`
- [x] `npm --prefix frontend run lint`
- [x] `npm --prefix frontend run build`
- [x] Confirm no credentials, AWS writes, or new dependencies were introduced.
- [x] Review `git diff` and preserve unrelated user changes.
