<!--
Sync Impact Report
==================
Version change: 1.0.0 → 1.0.1
Rationale: PATCH — clarification of Principle II. TDD's application point is
  narrowed from a "tests-first-blocks-everything" gate to "applied during
  implementation, enforced at the final PR". No principle added, removed, or
  redefined; semantics refined only.

Principle modified:
  II. Test-Driven Development — clarified WHEN the discipline applies
     (during implementation; carried and verified at the final PR), not a
     pre-implementation blocking gate.

---

Prior history:

Initial ratification — placeholder tokens replaced with concrete principles
  derived from the user's standing engineering directives (MAJOR 1.0.0):

  [PRINCIPLE_1_NAME] → I. Twelve-Factor by Default
  [PRINCIPLE_2_NAME] → II. Test-Driven Development (NON-NEGOTIABLE)
  [PRINCIPLE_3_NAME] → III. Async-First Microservices
  [PRINCIPLE_4_NAME] → IV. Modularity & Readability
  [PRINCIPLE_5_NAME] → V. Reproducible Environments & Automation

Added sections: Technology Stack, Development Workflow, Governance.
Removed sections: none (template placeholders resolved, not removed).

Templates requiring updates:
  ✅ .specify/templates/plan-template.md — "Constitution Check" gate is generic
     ("[Gates determined based on constitution file]"); the /speckit-plan command
     derives gates dynamically, so no static edit is needed. Verified aligned.
  ✅ .specify/templates/tasks-template.md — with the v1.0.1 clarification, the
     "Tests are OPTIONAL" language no longer conflicts with Principle II: TDD
     applies at implementation/PR time, not as a plan-time gate. No edit needed.
     The task template remains generic; /speckit-tasks still regenerates
     tasks.md from it per user-story. (Prior TODO(TASKS_TEMPLATE) resolved.)
  ✅ .specify/templates/spec-template.md — generic; no constitution-specific
     references to update.

Follow-up TODOs:
  TODO(RATIFICATION_DATE): Recorded as 2026-07-06 (initial adoption). Replace
    with the actual first-adoption date if a prior ratified version existed.
-->

# CMA-MicroVM Constitution

## Core Principles

### I. Twelve-Factor by Default

Every microservice in this repo MUST follow the [Twelve-Factor App](https://12factor.net)
methodology. The factors are non-negotiable for service code:

- **Codebase**: one codebase tracked in VCS, many deploys.
- **Dependencies**: explicitly declared and isolated (via UV; see Technology
  Stack). No implicit system-package reliance.
- **Configuration**: config in the environment, not in the code. Use
  Pydantic-settings to load and validate it.
- **Backing Services**: treat attached resources (DBs, queues, caches, secrets)
  as swappable external resources addressed via env vars / config.
- **Build, release, run**: strictly separated build, release, and run stages.
- **Processes**: stateless, share-nothing processes.
- **Port binding**: services self-bind ports; no external web server required.
- **Concurrency**: scale out via processes/handlers; design for concurrent units.
- **Disposability**: fast startup and graceful shutdown; processes are
  disposable at any moment.
- **Dev/prod parity**: keep dev, staging, and prod as similar as possible
  (same images, same backing services, same config shape).
- **Logs**: treated as event streams to stdout/stderr — never to files. Loguru
  is the emitter.
- **Admin processes**: one-off admin tasks (migrations, scripts) run in an
  identical environment to the app.

**Rationale**: portability across cloud providers and disposable, observable
services require this baseline. A repo that violates a factor MUST document the
exception in the plan's Complexity Tracking table.

### II. Test-Driven Development (NON-NEGOTIABLE)

TDD is mandatory for all Python code — but it applies **during implementation
and is enforced at the final PR**, not as a plan-time gate that blocks all
design before a test exists. Concretely: while you implement a slice, drive it
Red-Green-Refactor (write the test, watch it fail, implement until green,
refactor), and the PR that merges the work MUST carry those passing tests.

- TDD is the implementation discipline: tests guide and lock the behavior as
  you build, never bolted on after the fact. They are not an upfront approval
  artifact required before any code is written.
- The final PR is the enforcement point: it MUST not merge without tests that
  cover the new/changed behavior, and those tests MUST pass.
- Modules are independently testable: prefer pure functions and injected
  dependencies (see Principle IV) so unit tests need no AWS/network.
- Integration tests are required for new library contracts, contract changes,
  inter-service communication, and shared schemas.
- "Tests are optional" does not apply to Python in this repo.

**Rationale**: the sandbox control plane is security-critical and runs
ephemerally on AWS; behavior must be locked by tests before it is trusted to
launch isolated compute — and the PR merge is the last, reliable point to
guarantee that.

### III. Async-First Microservices

All microservice code MUST be async by default. I/O (HTTP, Secrets Manager,
DynamoDB, the Anthropic API) MUST use async clients; blocking calls are
forbidden in service hot paths unless wrapped or explicitly justified.

**Rationale**: microservices handle concurrent sessions/requests; blocking I/O
wastes the concurrency model and breaks disposability under load.

### IV. Modularity & Readability

- **Modularity in Python**: each capability is a self-contained module/package
  with a clear single purpose. No organizational-only modules. Cross-cutting
  logic lives in a `shared/` namespace, not duplicated.
- **Readability and maintainability**: code is read far more than it is
  written. Optimize for the next reader. Match surrounding style, name things
  explicitly, keep functions small, and comment the *why* (not the *what*).
  Many people will work in this code — leave it clearer than you found it.

**Rationale**: a long-lived reference repo only stays useful if its modules are
independently comprehensible and replaceable.

### V. Reproducible Environments & Automation

Every application MUST run locally AND be reproducible inside Docker / Docker
Compose. The Compose file is the canonical reference for the runtime
topology — local dev and container dev MUST converge on the same
configuration (dev/prod parity, per Factor X).

- Do NOT set the obsolete `version:` key in docker-compose files.
- Repository automation is expressed in a **Justfile** (the `just` command
  runner). Repeatable workflows — build, lint, test, run, image build — are
  `just` recipes, not ad-hoc shell invocations.
- Note: the user runs `make`-style targets themselves — delegate execution of
  build/deploy commands to the user rather than invoking them directly.

**Rationale**: parity between local and container environments is the only way
to reproduce a Lambda/MicroVM behavior offline and to keep cloud-provider
backends interchangeable.

## Technology Stack

- **Language**: Python (the primary working language for this repo).
- **Dependency manager**: **UV**. All dependencies MUST be added with
  `uv add` (and projects initialized with `uv init`). Do not hand-edit
  requirements for app code; `uv` owns the lockfile.
- **Base libraries (always)**: Python 3.11+, **Loguru** (logging),
  **ruff** (lint + format), **Pydantic-settings** (configuration). These are
  the default stack for every service.
- **Databases**: when a database is involved, schema is versioned with
  **Alembic** migrations, and models are defined with **SQLModels**. No
  hand-rolled schema drift.
- **Tooling glue**: **pre-commit** wired to a **Rust-backed** validator to
  validate Python (e.g., via a Rust linter/formatter hook). The pre-commit
  configuration is part of the repo and runs on every commit.
- **Packaging/runtime**: Docker + Docker Compose for local reproduction (per
  Principle V); the AWS control plane here additionally uses SAM + the
  `lambda-microvms` service (see `README.md`) — that does not replace the
  local Docker parity requirement for any new service.

## Development Workflow

- **Trunk-based development + Spec-Driven Development**: `main` is the single
  integration trunk. Work is driven by specifications (the speckit
  `/speckit-*` skills). Never commit to `main` directly.
- **Branching**: open a branch named `<SPEC>—<TOPIC/TASK/SMALL_DEVELOPMENT>`
  per increment. A single spec MAY span multiple PRs (one per
  topic/task/small-development slice). Keep PRs small and reviewable.
- **Merge discipline**: every change reaches `main` via a Pull Request that is
  reviewed and merged. No direct pushes to `main`.
- **Learning annotations**: annotate learnings as you go — capture non-obvious
  decisions, AWS quirks, and rationale in code comments, memory, or docs so
  the next contributor inherits the context. We work mostly in Python here;
  keep notes Python-relevant.

## Governance

- This Constitution supersedes all other practices in the repo. Where a
  template, README, or prior convention conflicts with it, the Constitution
  wins (and the conflicting source should be amended).
- **Amendments** require: (1) a written change proposal, (2) review, and
  (3) a documented migration plan for any code that the amendment would break.
- **Versioning** (semver): MAJOR for principle removals/redefinitions or
  backward-incompatible governance; MINOR for new/expanded principles or
  sections; PATCH for clarifications, wording, typos.
- **Compliance review**: every PR MUST verify compliance with the Core
  Principles (the plan's Constitution Check gate). Complexity that violates a
  principle MUST be justified in the plan's Complexity Tracking table with a
  rejected-simpler-alternative rationale.
- **Runtime guidance**: for day-to-day development guidance, follow
  `CLAUDE.md` (and the current speckit plan injected into it).

**Version**: 1.0.1 | **Ratified**: 2026-07-06 | **Last Amended**: 2026-07-06