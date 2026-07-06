---
name: "speckit-cycle"
description: "Run the full Spec-Driven Development cycle from a single GOAL: specify → plan → tasks → drills → learning → implement with review gates. Use when the user sets a GOAL, wants the full speckit workflow, end-to-end feature delivery, or says run speckit cycle / full SDD cycle."
argument-hint: "GOAL=<feature description> [SCOPE=full|backend-only|frontend-only] [AUTO_APPROVE=true|false]"
compatibility: "Requires spec-kit project structure with .specify/ directory and sibling skills speckit-specify, speckit-plan, speckit-tasks, speckit-implement, speckit-drill, speckit-learn"
metadata:
  author: "cma-microvm"
  source: ".specify/workflows/speckit/workflow.yml"
user-invocable: true
disable-model-invocation: false
---

# Full SDD Cycle

Orchestrates the bundled **Full SDD Cycle** workflow: turn one **GOAL** into a shipped feature by chaining existing speckit skills with drill gates, institutional learning, and review checkpoints.

## User Input

```text
$ARGUMENTS
```

You **MUST** consider the user input before proceeding (if not empty).

Parse input for:

| Token | Required | Default | Values |
|-------|----------|---------|--------|
| `GOAL` | yes | — | Natural-language feature description |
| `SCOPE` | no | `full` | `full`, `backend-only`, `frontend-only` |
| `AUTO_APPROVE` | no | `false` | `true` skips human review gates after drill pass |

If `GOAL` is missing, ask once: *"What is the GOAL for this cycle?"* then stop.

Pass `GOAL` and `SCOPE` to every downstream skill invocation as context.

## Cycle State

Persist progress in `.specify/cycle-state.json` (create or update after each phase):

```json
{
  "goal": "<GOAL>",
  "scope": "full",
  "auto_approve": false,
  "feature_directory": null,
  "current_phase": "specify",
  "phases_completed": [],
  "drill_results": {},
  "learnings_recorded": [],
  "started_at": "<ISO8601>",
  "updated_at": "<ISO8601>"
}
```

Valid `current_phase` values (in order):

`specify` → `clarify` (optional) → `drill-spec` → `review-spec` → `plan` → `drill-plan` → `review-plan` → `tasks` → `drill-pre-implement` → `learn` → `implement` → `learn-post` → `done`

On resume (state file exists and `current_phase` ≠ `done`), report where the cycle stopped and continue from that phase unless the user provides a new GOAL.

### State Update Rules

After **every** phase transition, write `.specify/cycle-state.json` with:

- `updated_at` — current ISO8601 timestamp
- `current_phase` — next phase identifier
- `phases_completed` — append the phase just finished (e.g. `"specify"`, `"review-spec"`) when that phase succeeds; do not append on FAIL or abort
- `drill_results` — after each drill, record under the phase key:

```json
"drill_results": {
  "spec": { "status": "PASS", "iterations": 1, "completed_at": "<ISO8601>" }
}
```

Use `"FAIL"` for `status` when max retries are exhausted. Overwrite the key on re-drill within the same cycle.

## Orchestration Flow

Copy this checklist and update it as you progress:

```text
Cycle Progress:
- [ ] 1. Specify
- [ ] 1b. Clarify (if [NEEDS CLARIFICATION] remains)
- [ ] 2. Drill (spec)
- [ ] 3. Review spec gate
- [ ] 4. Plan
- [ ] 5. Drill (plan)
- [ ] 6. Review plan gate
- [ ] 7. Tasks
- [ ] 8. Drill (pre-implement)
- [ ] 9. Learn
- [ ] 10. Implement
- [ ] 11. Learn (post-implement)
```

### Phase 1 — Specify

1. Read and follow `.claude/skills/speckit-specify/SKILL.md` with `$ARGUMENTS` = GOAL.
2. Record `feature_directory` from the specify completion report (`SPECIFY_FEATURE_DIRECTORY`) in cycle state.
3. Append `"specify"` to `phases_completed`; update state per State Update Rules.
4. **If spec still has `[NEEDS CLARIFICATION]` markers**:
   - Set `current_phase` → `clarify` and run Phase 1b before drilling.
   - Otherwise set `current_phase` → `drill-spec`.

### Phase 1b — Clarify (conditional)

1. Read and follow `.claude/skills/speckit-clarify/SKILL.md`.
2. Append `"clarify"` to `phases_completed`; set `current_phase` → `drill-spec`.

### Phase 2 — Drill (spec)

1. Read and follow `.claude/skills/speckit-drill/SKILL.md` with `$ARGUMENTS` = `PHASE=spec`.
2. Record result in `drill_results.spec` per State Update Rules.
3. **If FAIL**: fix spec (re-run specify sections as needed), re-drill. Max 3 iterations; then stop and report blockers.
4. **If PASS**: append `"drill-spec"` to `phases_completed`; set `current_phase` → `review-spec`.

### Phase 3 — Review spec gate

Present a 5-line summary: feature name, directory, open clarifications, checklist status, recommended next step.

- If `AUTO_APPROVE=true` or user previously said "approve" / "continue": proceed.
- Otherwise ask: **"Review the generated spec before planning. Approve or reject?"**
  - `reject` / `abort` → set `current_phase` → `done`, stop.
  - `approve` / `continue` → proceed.

Append `"review-spec"` to `phases_completed`; set `current_phase` → `plan`.

### Phase 4 — Plan

1. Read and follow `.claude/skills/speckit-plan/SKILL.md` with GOAL + SCOPE context.
2. Append `"plan"` to `phases_completed`; set `current_phase` → `drill-plan`.

### Phase 5 — Drill (plan)

1. Read and follow `.claude/skills/speckit-drill/SKILL.md` with `$ARGUMENTS` = `PHASE=plan`.
2. Record result in `drill_results.plan` per State Update Rules.
3. On FAIL: fix plan, re-drill (max 3 iterations).
4. On PASS: append `"drill-plan"` to `phases_completed`; set `current_phase` → `review-plan`.

### Phase 6 — Review plan gate

Present: architecture summary, constitution check result, key risks.

Same gate rules as Phase 3. On approve → append `"review-plan"` to `phases_completed`; set `current_phase` → `tasks`.

### Phase 7 — Tasks

1. Read and follow `.claude/skills/speckit-tasks/SKILL.md`.
2. Append `"tasks"` to `phases_completed`; set `current_phase` → `drill-pre-implement`.

### Phase 8 — Drill (pre-implement)

1. Read and follow `.claude/skills/speckit-drill/SKILL.md` with `$ARGUMENTS` = `PHASE=pre-implement`.
   - This runs cross-artifact analysis (constitution alignment, coverage) and checklist completeness.
2. Record result in `drill_results["pre-implement"]` per State Update Rules.
3. On FAIL with CRITICAL findings: stop; recommend fixes before implement.
4. On PASS (no CRITICAL): append `"drill-pre-implement"` to `phases_completed`; set `current_phase` → `learn`.

### Phase 9 — Learn

1. Read and follow `.claude/skills/speckit-learn/SKILL.md` for issues encountered so far in this cycle.
2. Record entry titles in `learnings_recorded`.
3. Append `"learn"` to `phases_completed`; set `current_phase` → `implement`.

### Phase 10 — Implement

1. Read and follow `.claude/skills/speckit-implement/SKILL.md`.
2. Honor implement skill checklist gate: if checklists incomplete, do **not** override unless user explicitly approves.
3. Append `"implement"` to `phases_completed`; set `current_phase` → `learn-post`.

### Phase 11 — Learn (post-implement)

1. Read and follow `.claude/skills/speckit-learn/SKILL.md` for implementation issues, test failures, and workarounds discovered during Phase 10.
2. Record entry titles in `learnings_recorded`.
3. Append `"learn-post"` to `phases_completed`; set `current_phase` → `done`.

## Completion Report

When `current_phase` = `done`, report:

- GOAL and feature directory
- `phases_completed` list and `drill_results` summary table (phase, status, iterations)
- Learnings written (links to `KNOWLEDGE.md` sections)
- Implementation summary (tasks completed, tests status)
- Suggested next steps (PR, `/speckit-taskstoissues`, etc.)

## Operating Rules

1. **Never skip drills** — a phase is not complete until its drill passes or max retries exhausted.
2. **Learning follows drills** — run `speckit-learn` only after pre-implement drill passes and again after implement.
3. **Delegate, don't duplicate** — each phase executes the corresponding skill's full instructions; this skill only orchestrates order and gates.
4. **Constitution authority** — load `.specify/memory/constitution.md` when making gate decisions; constitution MUST violations block progression.
5. **Scope** — when `SCOPE=backend-only`, note in plan/tasks that frontend is out of scope; converse for `frontend-only`.
6. **Extension hooks** — optional hooks (`speckit-agent-context-update`, etc.) are handled inside each child skill's Pre/Post-Execution sections; do not skip them when executing those skills.
7. **Slash commands** — this project uses invoke separator `-` (see `.specify/integration.json`): `/speckit-specify`, `/speckit-plan`, etc.

## How This Differs From `workflow.yml`

The bundled workflow engine dispatches steps programmatically. These skills are **orchestration instructions for the agent**:

- The cycle runs across **multiple chat turns** (review gates, clarifications, implementation length).
- Resume via `.specify/cycle-state.json` or *"Continue the speckit cycle"*.
- Skills are discovered from `.claude/skills/` (`ai_skills: true` in init-options). Start a **new chat** after adding skills so they appear in the agent skill list.
- Custom skills (`speckit-cycle`, `speckit-drill`, `speckit-learn`) are **not** in `claude.manifest.json` — that file tracks spec-kit bundled skill hashes for upgrades; your custom skills are safe alongside it.

## Quick Start Examples

```text
GOAL=Add webhook deduplication metrics to the launcher Lambda
```

```text
GOAL=Implement rate-limiter tuning for RunMicrovm SCOPE=backend-only AUTO_APPROVE=true
```

Resume an interrupted cycle:

```text
Continue the speckit cycle from saved state.
```

## Done When

- [ ] `.specify/cycle-state.json` reflects the latest `current_phase`, `phases_completed`, and `drill_results`
- [ ] Each completed phase delegated to its child skill (including extension hooks)
- [ ] All three drills passed or max retries reported with blockers
- [ ] Learnings captured after pre-implement and post-implement (or confirmed none)
- [ ] Completion Report delivered when `current_phase` = `done`
