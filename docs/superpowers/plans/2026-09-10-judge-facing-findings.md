# Judge-Facing Findings Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the existing evidence paths and recommendations visible immediately after a JSON upload in the hackathon demo.

**Architecture:** Keep the Python analyzer and API unchanged. Extend the existing Next.js page composition to render the already-built findings and inventory components below a responsive graph-and-assistant workspace. The assistant remains secondary to the evidence sections.

**Tech Stack:** Next.js 16, React, TypeScript, Tailwind CSS, existing Python API.

**Spec:** `README.md` challenge description

## Global Constraints

- Preserve read-only behavior; no AWS mutation or new credentials.
- Reuse existing `FindingsList`, `PathViewer`, and `InventoryTables` components.
- Add no dependencies and no new backend endpoints.
- Keep existing dirty-worktree changes intact.

---

### Task 1: Surface findings and source evidence in the analysis workspace

**Files:**
- Modify: `frontend/src/app/page.tsx:5-7,94-107`
- Test: `npm --prefix frontend run lint` and `npm --prefix frontend run build`

**Interfaces:**
- Consumes: `report.findings`, `report.identity_metadata`, and uploaded `inventory` already held by `Home`.
- Produces: visible Findings and Source inventory sections after a successful upload.

- [x] **Step 1: Add imports for `FindingsList` and `InventoryTables` and render them after the graph.**
- [x] **Step 2: Restore `ChatPanel` beside the graph on desktop and below it on smaller screens.**
- [x] **Step 3: Run `npm --prefix frontend run lint` and confirm no lint errors.**
- [x] **Step 4: Run `npm --prefix frontend run build` and confirm TypeScript plus production compilation pass.**

### Task 2: Verify the full repository

**Files:**
- Test: `tests/` and frontend package scripts

- [x] **Step 1: Run `.venv\\Scripts\\python.exe -m pytest -q` and confirm all backend tests pass.**
- [x] **Step 2: Run `npm --prefix frontend run lint` and `npm --prefix frontend run build`.**
- [x] **Step 3: Check `git diff --stat` and verify only the page composition and this plan changed from this task.**
