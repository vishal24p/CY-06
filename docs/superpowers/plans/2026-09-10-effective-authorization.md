# Effective Authorization Coverage Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend CY-06 from basic IAM analysis to an evidence-backed authorization graph covering business identity, boundaries, resource policies, Organizations SCPs, and STS sessions.

**Architecture:** Keep the existing deterministic IAM rules engine authoritative. Normalize optional supplemental data into typed graph nodes/edges and evaluate only permissions with enough evidence; emit `review_required` for missing request context. FastAPI returns the report and graph payload; the Next.js UI renders both without policy evaluation.

**Tech Stack:** Python 3.11+, pytest, FastAPI, Next.js, React, TypeScript, Tailwind.

**Spec:** `docs/superpowers/plans/2026-09-10-rules-engine-nextjs.md`

## Global Constraints

- No AWS mutations or credentials in browser/agent.
- Never infer job title, department, or employee type from IAM names or groups.
- Explicit Deny overrides Allow.
- SCPs and boundaries restrict; they do not grant.
- Missing condition/session context produces `review_required`, not an optimistic Allow.

---

### Task 1: Add normalized coverage model

**Files:**
- Create: `src/cy06/coverage.py`
- Test: `tests/test_coverage.py`

**Interfaces:**
- `build_coverage(inventory: Mapping[str, Any]) -> dict[str, Any]`
- Returns `nodes`, `edges`, `metadata`, `coverage`, and `warnings`.

- [x] Write failing tests for identity metadata joins, boundaries, resource policies, Organizations/SCP ancestry, and sessions.
- [x] Implement tolerant normalization for optional sections and stable IDs.
- [x] Run focused tests.

### Task 2: Add effective-access gates

**Files:**
- Modify: `src/cy06/rules/engine.py`
- Test: `tests/test_rules.py`

**Interfaces:**
- Existing `analyze_inventory()` keeps its return contract and adds `coverage` plus `graph`.
- Findings blocked by verified boundary/SCP/resource Deny are not reported as effective access.
- Findings dependent on absent session/condition context are marked `review_required`.

- [x] Write failing tests for boundary and SCP Deny suppressing a detected path.
- [x] Add shared supplemental-policy matching and report annotations.
- [x] Run all Python tests and lint/type checks.

### Task 3: Extend API and frontend graph

**Files:**
- Modify: `src/cy06/api.py`
- Modify: `frontend/src/lib/types.ts`
- Modify: `frontend/src/components/IamGraph.tsx`
- Modify: `frontend/src/components/InventoryTables.tsx`
- Modify: `frontend/src/app/page.tsx`
- Test: `tests/test_api.py`

**Interfaces:**
- Upload accepts one combined JSON document containing the existing IAM sections plus optional coverage sections.
- UI shows business metadata, control layers, and edge labels from the API graph.

- [x] Add API assertion for graph and coverage fields.
- [x] Add typed rendering for six coverage domains.
- [x] Run frontend lint/build and backend verification.

### Task 4: Add realistic demo fixture and documentation

**Files:**
- Modify: `data/sample-iam-inventory.json`
- Modify: `README.md`

- [x] Add synthetic metadata, resource policy, boundary, Organizations/SCP, and session examples.
- [x] Document exact schemas, limitations, and expected findings.
- [x] Run the sample end to end.
