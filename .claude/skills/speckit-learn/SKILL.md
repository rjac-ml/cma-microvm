---
name: "speckit-learn"
description: "Capture institutional knowledge from the current SDD cycle into KNOWLEDGE.md per the constitution Development Workflow (Learning annotations). Use after drills pass or after implementation when issues were encountered and resolved, or when the user asks to record learnings."
argument-hint: "Optional summary of issues/learnings to record"
compatibility: "Requires .specify/memory/constitution.md (Development Workflow — Learning annotations)"
metadata:
  author: "cma-microvm"
  source: ".specify/memory/constitution.md"
user-invocable: true
disable-model-invocation: false
---

# Speckit Learn

Records **institutional knowledge** — issues encountered and their resolutions — so the team does not rediscover the same problems. Required by the constitution **Development Workflow** section (*Learning annotations*).

## User Input

```text
$ARGUMENTS
```

You **MUST** consider the user input before proceeding (if not empty).

Use explicit user notes when provided; otherwise infer from the current conversation and cycle state (`.specify/cycle-state.json`).

## Knowledge File Location

Primary: **`KNOWLEDGE.md`** at repository root.

If the active feature lives in a multi-repo workspace and the issue is repo-specific, also append a short cross-reference under `workspace/<repo>/KNOWLEDGE.md` when that path exists.

Create `KNOWLEDGE.md` if missing using the template below.

## When to Run

| Trigger | What to capture |
|---------|-----------------|
| After pre-implement drill passes | Spec/plan/tasks friction, toolchain surprises, clarification decisions |
| After implement completes | Test failures, env/Docker/SAM/CI issues, workarounds, credential-handling notes (never actual secrets) |
| User request | Any resolved issue the user describes |

**Skip silently** if there are zero new learnings (report: *"No new learnings to record."*).

## Entry Template

Append new entries (newest first under today's date heading):

```markdown
## YYYY-MM-DD

### [SHORT-TITLE] — [feature-or-area]

**Context**: What we were doing (phase, GOAL, component).

**Issue**: What went wrong or was unclear.

**Resolution**: What fixed it (commands, config, code approach).

**Prevention**: How to avoid next time.

**Refs**: `specs/NNN-name/`, PR links, docs (optional).
```

## Execution Steps

1. Load cycle state if present — note `goal`, `feature_directory`, `current_phase`.
2. Collect candidate learnings from:
   - User `$ARGUMENTS`
   - Drill FAIL/PASS notes and remediation applied this session
   - Implementation errors and fixes
   - Clarification decisions from specify/clarify
3. **Deduplicate**: search existing `KNOWLEDGE.md` for similar titles; merge or skip duplicates.
4. **Redact**: never write credentials, tokens, connection strings, API keys, or `.env` values. Reference env var *names* only. Honor the repo credential boundary (org API keys stay operator-only; never record secret values).
5. Append new entries to `KNOWLEDGE.md`.
6. Update `.specify/cycle-state.json` → append entry titles to `learnings_recorded`.

## Initial File Template

When creating `KNOWLEDGE.md`:

```markdown
# Institutional Knowledge

Issues encountered and resolutions for CMA-MicroVM. Per constitution Development Workflow (Learning annotations).

<!-- Entries below: newest date sections first -->
```

## Completion Report

```markdown
## Learning Capture

**Entries added**: N
**File**: KNOWLEDGE.md

| Title | Area |
|-------|------|
| ...   | ...  |
```

If N = 0, state that no file changes were made.

## Done When

- [ ] Candidates reviewed and deduplicated
- [ ] No secrets in written content
- [ ] KNOWLEDGE.md updated or confirmed empty
- [ ] Cycle state `learnings_recorded` updated when cycle state exists
