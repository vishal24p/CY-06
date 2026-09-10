# Local JSON Importer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let CY-06 validate an AWS IAM authorization-details JSON file without requiring AWS login.

**Architecture:** Keep the existing AWS connector unchanged. Add a small standard-library JSON loader and summary function, then route the CLI to local mode when `--input` is provided. Use one sanitized fixture shaped like AWS `get-account-authorization-details` output.

**Tech Stack:** Python 3.11+, standard-library `json`, `pathlib`, `dataclasses`, pytest.

**Spec:** `docs/superpowers/plans/2026-09-10-aws-connector.md`

## Global Constraints

- Keep AWS authentication optional for local mode.
- Do not add permanent credentials or secrets to the repository.
- Accept JSON only for this module.
- Preserve the existing AWS CLI behavior when `--profile` is used.

---

### Task 1: Add the JSON inventory loader

**Files:**
- Create: `src/cy06/inventory.py`
- Test: `tests/test_inventory.py`

**Interfaces:**
- Consumes: a path to an AWS authorization-details JSON document.
- Produces: `load_inventory(path) -> dict[str, object]` and `summarize_inventory(data) -> dict[str, object]`.

- [ ] **Step 1: Write tests for valid counts and invalid input.**
- [ ] **Step 2: Run the focused tests and verify they fail.**
- [ ] **Step 3: Implement minimal JSON loading, top-level list validation, and counts.**
- [ ] **Step 4: Run the focused tests and verify they pass.**

### Task 2: Expose local mode through the CLI

**Files:**
- Modify: `src/cy06/__main__.py`
- Modify: `tests/test_cli.py`
- Create: `data/sample-iam-inventory.json`

**Interfaces:**
- Consumes: `--input <path>`.
- Produces: a JSON import summary with `status`, entity counts, relationships, and warnings.

- [ ] **Step 1: Add a CLI test for `--input`.**
- [ ] **Step 2: Run the focused test and verify it fails.**
- [ ] **Step 3: Implement the local branch while preserving profile mode.**
- [ ] **Step 4: Add a sanitized fixture containing one user, one assumable role, and managed/inline policy relationships.**
- [ ] **Step 5: Run the full verification loop: tests, Ruff, and Pyright.**
- [ ] **Step 6: Commit the completed local importer.**
