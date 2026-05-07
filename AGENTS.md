# AGENTS.md

## Agent Fast Path

For a newly cloned repo, optimize for understanding the project quickly and then finding the highest-priority useful task:

1. Read `README.md` for the product summary, runnable baseline, setup commands, and repo structure.
2. Read `docs/plan/roadmap.md`, starting with `Current Focus`, to identify the highest-priority task, success criteria, evidence, and next code entrypoints.
3. Read `docs/features.md` only when product scope, feature boundaries, or non-goals affect the task.
4. Read `docs/architecture.md` only when responsibilities, data flow, transport, storage, or contracts affect the task.
5. Read `docs/README.md` only when document ownership, repository workflow, or handoff rules affect the task.
6. Read `docs/plan/README.md` when updating roadmap status, evidence, blockers, or maintenance rules.

If the roadmap appears stale or contradicts the code, inspect the repository, then update `docs/plan/roadmap.md` with the corrected status before continuing.

## Task Selection Rules

- Treat `docs/plan/roadmap.md` as the only source of truth for current priority, milestone status, evidence, blockers, and next work.
- Start with the lowest-numbered priority in `Current Focus` or the priority table.
- Prefer `In Progress` work over `Next` work at the same priority.
- If the top-priority item is `Blocked`, work only on the smallest step that can remove or document the blocker; do not silently skip to lower-priority feature work.
- Choose tasks with clear completion standards and evidence requirements. If those are missing, tighten the roadmap first.
- When code changes alter progress, blockers, scope, or contracts, update the relevant docs in the same turn.
