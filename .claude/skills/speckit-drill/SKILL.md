---
name: "speckit-drill"
description: "Run phase validation drills (checklists, constitution alignment, cross-artifact analysis) before advancing the SDD cycle. Use when speckit-cycle reaches a drill gate, or when the user asks to validate spec, plan, or pre-implement readiness."
argument-hint: "PHASE=spec|plan|pre-implement [FOCUS=optional focus area]"
compatibility: "Requires active feature directory from .specify/feature.json or check-prerequisites.sh"
metadata:
  author: "cma-microvm"
  source: "speckit-cycle drill gates"
user-invocable: true
disable-model-invocation: false
---

# Speckit Drills

**Drills are quality gates** — structured validation that must pass before the cycle advances. They combine checklist review, constitution checks, and (for pre-implement) cross-artifact analysis.

## User Input

```text
$ARGUMENTS
```

You **MUST** consider the user input before proceeding (if not empty).

Parse `PHASE` (required): `spec`, `plan`, or `pre-implement`.
Optional `FOCUS` narrows checklist generation (passed to speckit-checklist when applicable).

## Setup

Resolve `FEATURE_DIR` (first match wins):

1. `.specify/cycle-state.json` → `feature_directory`
2. `.specify/feature.json` → `feature_directory` (relative to repo root)
3. Shell (always safe, no plan.md required):

```bash
.specify/scripts/bash/check-prerequisites.sh --paths-only
```

Parse the `FEATURE_DIR:` line from output.

**Phase-specific scripts** (do not use the wrong one):

| PHASE | Command | Why |
|-------|---------|-----|
| `spec` | `--paths-only` only | `--json` **requires plan.md** and will fail after specify |
| `plan` | `--paths-only`, then verify `plan.md` exists | plan drill runs after plan phase |
| `pre-implement` | `--json --require-tasks --include-tasks` | Full artifact validation |

Abort if `FEATURE_DIR` cannot be resolved — instruct user to run `/speckit-specify` first.

Load `.specify/memory/constitution.md` for all phases.

When `.specify/cycle-state.json` exists, the cycle orchestrator records `drill_results`; standalone invocations should still emit the Drill Result block below.

## Drill Output Format

Always end with:

```markdown
## Drill Result: [PHASE]

**Status**: PASS | FAIL
**Iterations**: N
**Blockers**: (list or "none")

| Check | Result | Notes |
|-------|--------|-------|
| ...   | ✓/✗    | ...   |
```

- **PASS**: all mandatory checks pass; cycle may continue.
- **FAIL**: one or more mandatory checks failed; cycle must fix and re-drill.

---

## PHASE=spec

Validate the specification before planning.

### Checks

1. **Spec file exists**: `FEATURE_DIR/spec.md` is non-empty with all mandatory template sections filled.
2. **Requirements checklist**: `FEATURE_DIR/checklists/requirements.md`
   - Count `- [ ]` vs `- [X]`/`- [x]`.
   - **Mandatory PASS**: 0 incomplete items.
   - If missing, run validation from speckit-specify § Specification Quality Validation and create the checklist.
3. **Clarifications**: no `[NEEDS CLARIFICATION]` markers remain (or user explicitly deferred them in writing).
4. **Constitution (spec-level)**: requirements and success criteria are technology-agnostic (per speckit-specify guidelines); no conflict with constitution Core Principles at the requirements level.

### On FAIL

- List failing checklist items with spec quotes.
- Fix spec and checklist; re-run drill (report iteration count).

### Optional enrichment

If domain-specific risk is high, read `.claude/skills/speckit-checklist/SKILL.md` and generate one focused checklist under `FEATURE_DIR/checklists/` using `FOCUS`. Re-run drill after marking items complete.

---

## PHASE=plan

Validate the implementation plan before task generation.

### Checks

1. **Plan file exists**: `FEATURE_DIR/plan.md` complete (no unresolved `NEEDS CLARIFICATION` in constitution check section).
2. **Constitution Check gate** (from plan template): every MUST principle from constitution addressed; conflicts documented with justification or resolved.
3. **Scope alignment**: plan tech choices match project stack in constitution (UV, async Python, Docker/SAM, Loguru, Pydantic-settings, etc.) unless explicitly justified in Complexity Tracking.
4. **SCOPE filter**: if cycle state has `backend-only` / `frontend-only`, plan boundaries reflect that scope.

### On FAIL

- Cite constitution principle and plan section for each failure.
- Update plan.md; re-drill.

---

## PHASE=pre-implement

Final drill before implementation. Strictest gate.

### Checks

1. **Artifacts present**: `spec.md`, `plan.md`, `tasks.md` all exist.
2. **Checklist sweep**: every file in `FEATURE_DIR/checklists/` — all items marked complete.
   - If checklists missing beyond requirements.md, run speckit-checklist for gaps (security, ux, api, etc. as implied by spec).
3. **Cross-artifact analysis**: read and follow `.claude/skills/speckit-analyze/SKILL.md` (read-only).
   - **FAIL if any CRITICAL findings** (constitution MUST violations, zero task coverage for core requirements).
   - HIGH findings: report but do not block unless user configured strict mode.
4. **Task readiness**: tasks.md has ordered phases with clear dependencies; where the plan scopes testable behavior, test tasks are listed before their corresponding implementation tasks (supports Principle II TDD during implementation — not a plan-time block on all design).

### On FAIL (CRITICAL)

- Output analyze report summary table.
- Do **not** proceed to implement; return FAIL with remediation commands (`/speckit-plan`, manual tasks.md edits, etc.).

### On PASS

- Summarize coverage % and checklist table from analyze report.
- Cycle may proceed to learn → implement.

---

## Retry Policy

- Max **3 drill iterations** per phase within a single cycle invocation.
- After 3 failures, return FAIL with consolidated blocker list and stop the cycle.

## Completion Report

Emit the **Drill Result** block (see above) with status, iterations, blockers, and per-check table.

## Done When

- [ ] PHASE identified and FEATURE_DIR resolved
- [ ] All mandatory checks for the phase executed
- [ ] Drill Result block emitted with PASS or FAIL
- [ ] On FAIL, specific remediation steps provided
