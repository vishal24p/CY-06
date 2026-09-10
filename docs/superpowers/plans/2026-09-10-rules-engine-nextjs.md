# Rules Engine and Next.js Frontend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Analyze uploaded AWS IAM JSON for evidence-backed privilege risks and display the findings in a local Next.js interface.

**Architecture:** The Python rules engine remains the source of truth. FastAPI exposes one local analysis endpoint. A Next.js App Router frontend uploads JSON, sends it to FastAPI, and renders summaries, findings, and paths. No agent or browser code evaluates permissions.

**Tech Stack:** Python 3.11+, FastAPI, Uvicorn, pytest, Next.js App Router, React, TypeScript, Tailwind CSS.

**Spec:** `docs/superpowers/plans/2026-09-10-local-json-importer.md`

## Global Constraints

- Do not modify AWS resources or require AWS credentials for local analysis.
- Do not infer employee/admin labels from identity names.
- Explicit Deny overrides Allow where the MVP can verify the same action/resource.
- Unsupported IAM features must produce review warnings, not silent assumptions.
- Never send AWS credentials or policy secrets to the browser or an LLM.

---

### Task 1: Implement deterministic rules

**Files:**
- Create: `src/cy06/rules/__init__.py`
- Create: `src/cy06/rules/engine.py`
- Test: `tests/test_rules.py`
- Modify: `data/sample-iam-inventory.json`

**Interfaces:**
- Consumes: AWS authorization-details JSON and optional context with `approved_admins`.
- Produces: analysis report with `summary`, `findings`, and `warnings`.

- [x] Write tests for group inheritance, privileged role assumption, explicit deny, and unsupported conditions.
- [x] Run focused tests and verify they fail.
- [x] Implement the minimum normalized statement traversal and five MVP rules.
- [x] Run focused tests and verify they pass.

### Task 2: Expose analysis through FastAPI

**Files:**
- Create: `src/cy06/api.py`
- Modify: `pyproject.toml`
- Test: `tests/test_api.py`

**Interfaces:**
- `POST /api/v1/analyze` accepts `{ "inventory": {}, "context": {} }`.
- Returns the rules-engine report.

- [x] Add the endpoint test for valid and invalid input.
- [x] Add FastAPI and Uvicorn dependencies.
- [x] Implement the endpoint with concise validation errors.
- [x] Run API tests.

### Task 3: Add the Next.js frontend

**Files:**
- Create: `frontend/` using Next.js TypeScript App Router and Tailwind.
- Modify: `README.md`

**Interfaces:**
- Uploads one JSON file locally.
- Sends it to FastAPI and renders counts, findings, warnings, and path evidence.

- [x] Scaffold the frontend.
- [x] Add typed API client and components.
- [x] Add loading, invalid-file, API-error, empty-result, and findings states.
- [x] Run the frontend build and the full Python verification loop.

### Task 4: Add graph and inventory tables

**Interfaces:**
- Keep the uploaded inventory in page state after analysis.
- Derive an SVG relationship graph from users, groups, roles, and policies.
- Render responsive tables for each entity type and highlight analyzed risk paths.

- [x] Add graph and table components without a visualization dependency.
- [x] Connect them to the upload result.
- [x] Run the frontend lint/build.
