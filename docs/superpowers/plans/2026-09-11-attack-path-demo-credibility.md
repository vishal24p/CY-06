# Attack-Path Demo Credibility Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the guided AWS IAM demo show truthful attack-path totals, explainable risk ranking, and an exact local remediation preview.

**Architecture:** Keep `src/cy06/rules/engine.py` authoritative. Each returned path gains a score breakdown, starting-privilege label, and precise final-hop remediation locator. The existing Next.js client renders a selectable ranked path list and uses the locator to change only one policy statement in a copied snapshot before re-analysis.

**Tech Stack:** Python standard library, pytest, Next.js 16, React, TypeScript, Tailwind CSS.

**Spec:** `README.md`, `docs/superpowers/plans/2026-09-11-iam-privilege-path.md`, and user-approved scope in this task.

## Global Constraints

- AWS IAM only; model is a conservative partial evaluator.
- Analysis and preview are read-only against AWS and never mutate uploaded input.
- No dependencies or live-cloud APIs.
- Preserve pre-existing dirty worktree changes.
- Explicit Deny, boundaries, SCPs, unsupported policy context, and existing warnings remain intact.

---

### Task 1: Return truthful, explainable attack-path data

**Files:**
- Modify: `src/cy06/rules/engine.py`
- Modify: `tests/test_rules.py`

**Interfaces:**
- Produces `summary.paths`, a critical count including critical attack paths, and each `paths[]` object with `risk_score`, `risk`, `score_breakdown`, `starting_privilege`, and `remediation`.
- `remediation` is `{ policy_name, statement_index, action, resource }` for the final role-assumption edge.

- [ ] Add failing tests that guided two-hop path has nonzero summary path/critical totals, `starting_privilege == "low"`, score breakdown totals score, and locator identifies `CanEnterAdmin` statement zero.
- [ ] Implement bounded scoring: target impact, assumption-resource breadth, hop directness, source context, and confidence; sort paths by score then stable path text.
- [ ] Determine low starting privilege from current user/group effective statements: no administrator policy, unrestricted action/resource, or sensitive IAM mutation before traversal.
- [ ] Carry policy statement index from current parser into the selected final-hop remediation locator without changing deny/boundary/SCP behavior.
- [ ] Run `pytest tests/test_rules.py -q` and then `pytest -q`.

### Task 2: Show ranked paths and truthful metrics

**Files:**
- Modify: `frontend/src/lib/types.ts`
- Modify: `frontend/src/app/page.tsx`
- Create: `frontend/src/components/PrivilegePathList.tsx`

**Interfaces:**
- Consumes backend `summary.paths` and enriched `PrivilegePath`.
- Produces selectable ranked paths; selected path drives focused graph card and preview.

- [ ] Extend shared TypeScript report and path types for totals, score breakdown, privilege label, and remediation locator.
- [ ] Render metric labels as Findings, Attack paths, Critical so guided demo cannot imply zero risk.
- [ ] Render paths in backend rank order with score, starting privilege, confidence, and factor chips; selection changes `selectedPathIndex`.
- [ ] Pass selected path to existing focused card and remediation preview.
- [ ] Run `npm run lint` and `npm run build` from `frontend`.

### Task 3: Make local preview exact and show residual risk

**Files:**
- Modify: `frontend/src/lib/api.ts`
- Modify: `frontend/src/components/RemediationPreview.tsx`

**Interfaces:**
- Consumes `PrivilegePath.remediation`.
- Produces a copied inventory with action removed only from its uniquely identified policy and statement index; reports selected-path state and remaining path count.

- [ ] Replace recursive first-matching-action removal with a unique-policy check plus exact statement-index action removal.
- [ ] Reject no-match or duplicate-policy locators rather than applying an ambiguous preview.
- [ ] Display policy, action, resource, selected-path result, and remaining path count after re-analysis.
- [ ] Run `npm run lint` and `npm run build` from `frontend`.

### Final verification

- [ ] `\.venv\Scripts\python.exe -m pytest -q`
- [ ] `npm run lint` and `npm run build` from `frontend`
- [ ] Verify guided demo report: at least one path, nonzero critical total, low starting privilege, exact local preview breaks selected path.
