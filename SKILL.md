# Project Task Execution Skill

## Purpose

Use this skill whenever you are asked to modify, implement, debug, refactor, review, test, or otherwise change this repository.

The goal is to produce the **correct, minimal, production-quality change** while avoiding unnecessary exploration, token usage, files, dependencies, refactors, or speculative work.

---

## 1. Mandatory First Step: Read Project Guidance

Before changing code, inspect the repository for project-specific instructions.

Read, when present and relevant:

- `CLAUDE.md`
- `AGENTS.md`
- `CONTRIBUTING.md`
- `README.md` / relevant module README
- `implementation_plan.md`
- existing package/tool configuration and scripts
- scoped instruction files nearer to the target files

### Instruction precedence

Use the most specific applicable instruction first. If instructions conflict, prefer:

1. System/developer/user instructions
2. Project/agent instructions explicitly governing the target path
3. This skill
4. General repository conventions
5. Your own assumptions

Do not ignore an applicable `implementation_plan.md` merely because the task appears straightforward.

---

## 2. If `implementation_plan.md` Exists

Treat `implementation_plan.md` as an important implementation context document.

First determine:

- whether it describes the current task
- which files/modules it expects to change
- architectural decisions already made
- dependencies, constraints, edge cases, or acceptance criteria
- sequencing or migration requirements

Use the plan to **reduce rediscovery**, not to blindly obey stale instructions.

If the plan conflicts with the user's current request, the user's current request wins.

If the plan appears stale, validate only the affected assumptions against the codebase and update or work around them as appropriate. Do not rewrite the entire plan unless requested.

---

## 3. Understand Before Editing

Do not begin by scanning the entire repository.

Start with the smallest useful search surface:

1. Identify the exact feature, bug, component, endpoint, command, or module involved.
2. Locate its primary implementation.
3. Locate directly related types/interfaces, services, routes, controllers, tests, configuration, and callers.
4. Read only the surrounding code needed to understand behavior and conventions.
5. Trace outward only when evidence shows it is necessary.

Prefer targeted search, symbol/reference lookup, and directory inspection over broad file dumping.

Never spend tokens reading unrelated modules merely to gain familiarity with the project.

---

## 4. Build a Minimal Mental Model

Before making a meaningful change, identify:

- current behavior
- desired behavior
- entry point
- affected data/control flow
- dependencies
- existing abstractions that should be reused
- validation/error-handling behavior
- relevant tests
- likely regression surface

Do not redesign architecture unless the task requires it or the existing architecture prevents a correct solution.

Prefer extending established patterns over introducing a new pattern.

---

## 5. Reuse Existing Code and Conventions

Before creating new code, search for an existing implementation or convention.

Prefer, in order:

1. Existing project utility/helper/service/component
2. Existing framework/library capability
3. Existing repository pattern
4. Small new abstraction only when genuinely justified

Avoid:

- duplicate helpers
- duplicate validation
- duplicate API clients
- unnecessary wrappers
- unnecessary dependencies
- replacing working libraries without a requirement
- broad refactors unrelated to the task

Keep dependency additions to the absolute minimum. If a dependency is not necessary, do not add it.

---

## 6. Implementation Rules

Make the **smallest change that fully solves the requested problem**.

Code should be:

- correct
- readable
- maintainable
- consistent with the repository
- type-safe where the project supports typing
- defensive at external boundaries
- explicit about failure modes
- free of avoidable duplication

Maintain backwards compatibility unless a breaking change is explicitly requested or required.

Preserve existing public APIs, contracts, response shapes, routes, database semantics, and user-facing behavior unless the task requires changing them.

Do not silently change unrelated formatting or files.

Avoid premature optimization, speculative abstractions, and clever code.

---

## 7. Security and Reliability

Treat external input as untrusted.

Check relevant risks for the task, including:

- authorization/authentication
- input validation
- injection vulnerabilities
- unsafe file/system operations
- secrets and credentials
- sensitive data exposure
- race conditions
- idempotency
- transaction boundaries
- concurrency
- error propagation
- resource cleanup
- timeout/retry behavior

Never hard-code credentials, API keys, private tokens, or secrets.

Never weaken an existing security control just to make the implementation easier.

For financial, destructive, permission-changing, or externally visible operations, inspect existing safeguards before changing behavior.

---

## 8. Tests and Verification

Verification is part of the implementation, not an optional final step.

First inspect existing test conventions and available scripts.

Prefer the narrowest useful checks first:

1. Targeted unit/component/integration test
2. Type checking/static analysis for affected code
3. Lint/format check for affected code
4. Broader relevant test suite
5. Build/package verification when applicable

Do not run expensive repository-wide checks repeatedly when a targeted check is sufficient.

If a test fails:

- determine whether the failure is caused by your change
- inspect the actual error rather than guessing
- fix the root cause
- rerun the smallest relevant verification

Do not weaken tests merely to make them pass.

If tests cannot be run, state exactly what was and was not verified and why.

---

## 9. Database / API / Contract Changes

For schema, API, event, queue, or other contract changes, explicitly consider compatibility.

Check:

- existing consumers
- serialization/deserialization
- nullability/defaults
- migrations
- rollback implications
- versioning
- validation
- pagination/filtering semantics
- error contracts
- caching
- observability

Prefer backwards-compatible migrations and rollout strategies where practical.

Never make destructive data changes without clear authorization from the task or established project requirements.

---

## 10. Frontend-Specific Guidance

When modifying UI/frontend behavior:

- follow existing component and state-management patterns
- preserve accessibility
- preserve responsive behavior
- reuse existing design-system primitives
- preserve loading, empty, error, and success states
- handle user input and async race conditions appropriately
- avoid unnecessary re-renders and effects
- avoid introducing global state for local concerns
- validate form behavior using existing project conventions

Do not redesign UI or introduce visual changes unrelated to the request.

---

## 11. Backend-Specific Guidance

When modifying backend behavior:

- follow existing layering and dependency-injection patterns
- validate at appropriate boundaries
- preserve authorization rules
- keep business logic in the established domain/service layer
- avoid putting business logic into controllers/routes when project conventions separate concerns
- use transactions when multiple writes must remain atomic
- handle retries and idempotency where relevant
- preserve consistent error responses
- consider logging/metrics for important failure paths

---

## 12. Debugging Workflow

For bugs, do not patch the first visible symptom without establishing the cause.

Use this sequence:

1. Reproduce or reconstruct the failure.
2. Identify the failing boundary.
3. Trace the relevant input/state through the system.
4. Determine the root cause.
5. Implement the narrowest robust fix.
6. Add or update a regression test when practical.
7. Re-run verification.

Prefer evidence from code, logs, stack traces, tests, and runtime behavior over speculation.

---

## 13. Planning Discipline

For simple changes, do not create a large plan.

For multi-file, architectural, migration, or high-risk work, write a concise implementation plan before editing if one does not already exist.

A useful plan should contain only:

- objective
- affected areas/files
- implementation approach
- important risks/edge cases
- verification steps

Do not spend tokens producing elaborate prose when a short actionable plan is enough.

If `implementation_plan.md` already exists and is current, use it rather than generating a competing plan.

---

## 14. Token and Context Efficiency

Optimize for **signal per token**.

### Do

- search narrowly
- read relevant ranges instead of entire large files
- summarize findings internally before expanding the search
- reuse information already obtained
- batch closely related searches when supported
- inspect only the relevant portions of configs/logs
- stop exploring once the evidence is sufficient to implement safely

### Do not

- repeatedly reread the same files
- dump huge files when a symbol/range is enough
- inspect unrelated modules
- explain obvious code line-by-line
- generate verbose plans for trivial work
- perform repository-wide refactors “while you are here”
- add comments that merely restate the code

When a broad search returns many matches, rank them by relevance and inspect the top candidates first.

---

## 15. Change Scope Control

At the end, inspect the diff.

The final change should answer:

> “Can every changed line be justified by the user's request, correctness, compatibility, security, testing, or an established project convention?”

If not, remove unrelated changes.

Do not modify generated files, lockfiles, snapshots, or formatting across unrelated files unless required.

Do not commit changes unless explicitly requested or the surrounding workflow clearly requires it.

---

## 16. Final Review Checklist

Before declaring the task complete, verify:

- [ ] User request is fully addressed.
- [ ] Applicable project instructions were followed.
- [ ] `implementation_plan.md` was checked when present.
- [ ] Existing patterns were reused where appropriate.
- [ ] No unnecessary dependency was added.
- [ ] No unrelated files or refactors were introduced.
- [ ] Security/authorization implications were considered where relevant.
- [ ] Edge cases were handled where relevant.
- [ ] Relevant tests/checks were run.
- [ ] Failures were investigated rather than ignored.
- [ ] Final diff was reviewed.
- [ ] Remaining limitations are explicitly stated.

---

## 17. Completion Report

Keep the final response concise and useful.

Report:

**Implemented**
- What changed and where.

**Verification**
- Tests/checks run and their results.

**Notes**
- Only important caveats, assumptions, migrations, follow-up risks, or items that could not be verified.

Do not provide a long narrative of every search or thought process unless the user asks for it.

---

## Core Principle

**Understand only what is necessary, change only what is necessary, verify what matters, and leave the repository cleaner and no more complex than the task requires.**
