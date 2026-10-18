# Repository Agent Instructions

This file is the shared repository instruction source for coding agents. Keep
tool-specific adapters thin: they may import this file or add behavior that is
truly specific to one client, but must not copy these rules.

## Start With the User's Task

- An explicit user request takes precedence over autonomous task selection.
- For an open-ended request such as "continue the project", use
  `docs/plan/roadmap.md` as the only source of truth for current priority,
  milestone status, evidence, blockers, and next work.
- Before editing, run `git status --short` and preserve existing user or agent
  changes. Do not revert, delete, stage, commit, or push them unless requested.

## Read Only What the Task Needs

1. Read `README.md` for the product goal, scope, current status, and repository
   entry points.
2. Read `docs/plan/roadmap.md`, starting with `Current Focus`, when selecting or
   continuing roadmap work.
3. Read `docs/features.md` when product scope, feature boundaries, or non-goals
   affect the task.
4. Read `docs/architecture.md` when accepted system boundaries, input/output
   contracts, or a formally selected architecture affect the task.
5. Read `docs/plan/rally-segmentation-requirement.md` when benchmark data,
   annotations, metrics, or acceptance evidence affect the task.
6. Read `docs/README.md` when document ownership or repository workflow affects
   the task.
7. Read `docs/plan/README.md` when changing roadmap status, evidence, blockers,
   or maintenance rules.
8. Before displaying video annotations or comparing algorithm intervals, read
   `.agents/skills/review-video-results/SKILL.md` and run its fixed viewer with
   saved data. Its scripts, template, data format, and display conventions are
   canonical; do not create another per-experiment HTML generator.

Do not preload every document. If a document appears stale or contradicts the
code, inspect the implementation and then correct the owning document.

`backup/docs/` is not part of the active reading path. Existing implementation
code and archived documents are legacy evidence, not the current architecture,
requirements, roadmap, or proof of completion. Use them only for an explicitly
historical investigation and label any conclusion from them as a historical
hypothesis.

## Repository Skill Routing

- Before searching, downloading, reviewing, sampling, or annotating badminton
  training media, read
  `.agents/skills/curate-badminton-training-data/SKILL.md`.
- `.agents/skills/curate-badminton-training-data/` is the canonical repository
  skill. Agents must read it in place; do not copy or symlink it into
  client-specific directories.
- Run the skill's `status` command before any search or download so cached
  candidates and permanent human decisions are reused.

## Work From First Principles

- Verify the actual code path, data shape, and failure before choosing a fix.
- Prefer the smallest complete change. Do not add unnecessary compatibility,
  abstractions, wrappers, or intermediate states.
- When unknown runtime details require a temporary compatibility assumption,
  leave observable diagnostics and a clear comment. Replace the assumption with
  the verified structure after debugging.
- Search with `rg` or `rg --files` when available and follow existing project
  patterns before introducing a new one.
- Keep product state in `docs/plan/roadmap.md`; do not copy current task status
  into this file, `docs/architecture.md`, or stable product documents.

## Select and Complete Roadmap Work

When the user has not selected a task:

- Start with the lowest-numbered priority in `Current Focus` or the priority
  table.
- At the same priority, prefer `In Progress` over `Next`, then `Todo`.
- If the top-priority item is `Blocked`, only remove or document that blocker;
  do not silently switch to lower-priority feature work.
- If completion standards or evidence are missing, tighten the roadmap before
  implementing.

When a change alters progress, blockers, scope, or contracts, update the
document that owns that information in the same task.

## Verify in Proportion to the Change

- Backend behavior: `pnpm run test:backend`
- Frontend types or shared contracts: `pnpm run typecheck:frontend`
- Every change: `git diff --check`
- Documentation-only changes do not require product tests unless they change a
  documented command that should be exercised.

Before handing off, inspect the focused diff and report changed files,
verification performed, and any unverified assumptions or remaining blockers.
