# Authorization Graph Layout Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the authorization graph readable by aligning nodes into stable lanes, routing arrows cleanly, and removing the cluttered legend.

**Architecture:** Keep the existing SVG graph and data contract. Replace the current row-only layout with deterministic type lanes and route edges through lane-aware curves; keep zoom, pan, selection, and risk highlighting intact.

**Tech Stack:** Next.js, React, TypeScript, SVG, Tailwind CSS.

**Spec:** User-provided graph screenshot and request in this task.

## Global Constraints

- No new dependencies.
- No backend or analyzer changes.
- Preserve keyboard accessibility and existing graph controls.
- Verify with frontend lint/build and a live guided-demo render.

### Task 1: Align and simplify the graph

**Files:**
- Modify: `frontend/src/components/IamGraph.tsx`
- Test: live guided demo in the local browser

- [x] Replace the current fixed five-column layout with stable lanes for people, relationships, policies, resources, and context.
- [x] Give nodes consistent vertical spacing and route edges with lane-aware cubic paths so arrows do not cross node bodies unnecessarily.
- [x] Remove the scrollable legend and keep risk textually identified.
- [x] Run `npm run lint` and `npm run build`.
- [x] Load the guided demo and verify labels, arrows, zoom, pan, node selection, and fullscreen remain usable.

### Task 2: Scope remediation to the selected finding

**Files:**
- Modify: `frontend/src/lib/api.ts`
- Modify: `frontend/src/app/page.tsx`
- Modify: `frontend/src/components/FindingsList.tsx`

- [x] Select a finding explicitly before previewing remediation.
- [x] Locate the policy named in the finding path and remove only that action from that policy.
- [x] Show the selected finding state in the list and keep the preview report connected to it.

### Task 3: Return findings in risk order

**Files:**
- Modify: `src/cy06/rules/engine.py`
- Test: `tests/test_rules.py`

- [x] Sort critical findings before high findings with deterministic tie-breakers.
- [x] Add a regression test for mixed-severity output.
