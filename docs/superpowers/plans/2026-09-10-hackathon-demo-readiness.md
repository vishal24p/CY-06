# Hackathon Demo Readiness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make CY-06 judge-ready in one uninterrupted demo: load sample data, explain one dangerous path, show evidence coverage, answer a question, and preview a safe remediation outcome.

**Architecture:** Keep the Python rules engine authoritative and read-only. Add a small demo fixture endpoint, pass the existing report into a deterministic evidence assistant fallback, and add a UI-only remediation preview that re-analyzes a copied inventory after removing the selected action. Keep real provider chat and AWS collection available but optional.

**Tech Stack:** FastAPI, Python standard library, Next.js 16, React, TypeScript, Tailwind CSS.

**Spec:** `README.md` and existing judge-facing findings plan.

## Global Constraints

- No AWS writes, credentials, PostgreSQL requirement, or new dependencies for the demo path.
- The Python analyzer remains the source of truth for findings and projected results.
- Demo simulation must never mutate the uploaded object or call AWS.
- Preserve existing dirty-worktree changes.

### Task 1: Add one-click demo loading

**Files:**
- Modify: `src/cy06/api.py`
- Modify: `frontend/src/app/api/analyze/route.ts`
- Modify: `frontend/src/lib/api.ts`
- Modify: `frontend/src/app/page.tsx`
- Test: `tests/test_api.py`

- [x] Add `GET /api/v1/demo` that loads the checked-in synthetic fixture and returns it.
- [x] Proxy it through Next and add `loadDemoInventory()`.
- [x] Add a visible “Load guided demo” action beside file upload.
- [x] Test endpoint and run backend/frontend verification.

### Task 2: Make evidence coverage and warnings judge-visible

**Files:**
- Create: `frontend/src/components/AnalysisSummary.tsx`
- Modify: `frontend/src/app/page.tsx`

- [x] Show report counts, coverage source counts, and analyzer warnings in one compact summary.
- [x] Explain that missing context becomes `review_required`, preserving security honesty.
- [x] Keep empty and loading states accessible.

### Task 3: Make the assistant work without provider setup

**Files:**
- Modify: `frontend/src/components/ChatPanel.tsx`
- Modify: `frontend/src/app/page.tsx`

- [x] Pass findings into the panel.
- [x] Add two suggested questions and a deterministic evidence-based fallback for demo mode.
- [x] Attempt configured chat first; use fallback only when the provider is unavailable.
- [x] Label fallback responses as local demo answers, not AI-generated claims.

### Task 4: Add safe remediation preview

**Files:**
- Create: `frontend/src/components/RemediationPreview.tsx`
- Modify: `frontend/src/app/page.tsx`
- Modify: `frontend/src/lib/api.ts`
- Modify: `frontend/src/lib/types.ts`

- [x] Clone the uploaded inventory, remove the selected finding action from matching policy statements, and re-run the authoritative analyzer.
- [x] Show before/after finding counts and exact projected change.
- [x] State clearly that preview changes are local and unapplied.

### Task 5: Verify demo path

- [x] Run `.venv\\Scripts\\python.exe -m pytest -q`.
- [x] Run `npm run lint` and `npm run build` in `frontend`.
- [x] Run the one-click demo flow against the local API and inspect the final diff.

## GSTACK REVIEW REPORT

- CEO: proceed with the smallest judge-visible slice; live AWS auth and PostgreSQL setup remain optional because they create demo failure modes.
- Design: prioritize a single guided narrative over adding more dashboard panels; keep simulation and uncertainty visibly labeled.
- Engineering: keep analysis authoritative in Python and isolate demo-only UI behavior; clone input before simulation.
- DX: README must explain the one-command demo path after implementation.
