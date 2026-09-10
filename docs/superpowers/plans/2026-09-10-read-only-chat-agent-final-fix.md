# Read-only Chat Agent Final Fix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Keep provider and browser chat conversations within the specified read-only and request-size boundaries.

**Architecture:** The server owns and prepends a constant instruction before client conversation messages. The existing panel trims retained history to the API limit and rejects oversized drafts before state or network changes.

**Tech Stack:** Python, pytest, React, TypeScript, Next.js.

**Spec:** `docs/superpowers/specs/2026-09-10-read-only-chat-agent-design.md`

## Global Constraints

- Client chat messages accept only `user` and `assistant` roles, at most 20 messages, each 1–4,000 characters.
- Provider gets only the fixed read-only tool registry; no import, simulation, approval, application, or mutation action is allowed.
- No dependency additions.

---

### Task 1: Pin provider instruction and client validation

**Files:**
- Modify: `tests/test_chat.py`
- Modify: `src/cy06/chat.py`

**Interfaces:**
- Consumes: `run_chat(messages, open_url=...)`.
- Produces: every provider request begins with a server-owned system instruction.

- [ ] **Step 1: Write failing provider-request regression test**

Capture the request JSON in `test_chat.py` and assert first message has role `system`, states fixed read-only registry, and forbids importing, simulation, approval, application, and mutation.

- [ ] **Step 2: Run focused test and verify failure**

Run: `& .\.venv\Scripts\python.exe -m pytest tests/test_chat.py -q`

Expected: FAIL because provider messages begin with client history.

- [ ] **Step 3: Add minimal server-owned constant and validation**

Define one module constant. Initialize provider messages with it followed by validated client messages; accept only `user`/`assistant` client roles.

- [ ] **Step 4: Re-run focused test**

Run: `& .\.venv\Scripts\python.exe -m pytest tests/test_chat.py -q`

Expected: PASS.

### Task 2: Bound browser chat state and requests

**Files:**
- Modify: `frontend/src/components/ChatPanel.tsx`

**Interfaces:**
- Consumes: local `ChatMessage[]` and draft text.
- Produces: `sendChat` inputs and retained UI history limited to newest 20 messages.

- [ ] **Step 1: Add limit constants and input guard**

Before creating a conversation, visibly reject trimmed drafts longer than 4,000 characters. Keep the draft editable and do not change message state.

- [ ] **Step 2: Trim local conversation**

Use `slice(-20)` when adding the user message and the provider reply, so both retained state and every `sendChat` request contain no more than 20 messages.

- [ ] **Step 3: Run frontend static checks**

Run: `npm run lint; npm run build`

Expected: PASS.

### Task 3: Verify and commit

**Files:**
- Create: `.superpowers/sdd/2026-09-10-read-only-chat-agent/final-fix-report.md`

- [ ] **Step 1: Run Python suite**

Run: `& .\.venv\Scripts\python.exe -m pytest`

- [ ] **Step 2: Write concise test/concern report and commit**

Record executed checks and remaining concerns, then commit source, tests, plan, and report.
