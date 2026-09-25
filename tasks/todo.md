# Labeling Rewrite Execution Ledger

Source plan: `tasks/plan.md`
Design spec: `docs/superpowers/specs/2026-09-25-kmeans-labeling-rewrite-design.md`

## Phase 1 — Foundation

- [x] Task 1: Establish failing labeling contract tests — RED: `ImportError: cannot import name 'labeling_service'`
- [ ] Task 2: Implement labeling models and relationships

### Checkpoint: Foundation
- [ ] Model imports succeed
- [ ] Focused tests fail only for unimplemented service behavior
- [ ] No out-of-scope files changed

## Phase 2 — Algorithm and persistence

- [ ] Task 3: Implement feature extraction and clustering core
- [ ] Task 4: Implement run persistence, apply, and discard

### Checkpoint: Algorithm
- [ ] Focused labeling tests pass
- [ ] Defaults and deterministic mapping are proven
- [ ] Existing labels remain unchanged until apply

## Phase 3 — HTTP workflow

- [ ] Task 5: Rewrite labeling controller

## Phase 4 — UI

- [ ] Task 6: Implement configuration and review templates
- [ ] Task 7: Rewrite manual edit template and list states

### Checkpoint: Workflow/UI
- [ ] Config → Run → Review → Terapkan/Buang works
- [ ] Manual edit works independently
- [ ] Focused UI/controller tests pass
- [ ] Responsive/accessibility review passes

## Phase 5 — Migration and verification

- [ ] Task 8: Create and validate database migration
- [ ] Task 9: Full test, scope, and data-preservation verification

### Checkpoint: Complete
- [ ] All acceptance criteria met
- [ ] Code review completed
- [ ] Verification evidence recorded

## Decisions / Rulings

- Ruling: Keep execution in the current worktree — the design/spec commit already exists on `main`, and no isolated worktree was requested; cost is reduced isolation during implementation.
- Ruling: Do not execute database deletion or migration against an unverified target — `DATABASE_URL` is unavailable in the working copy; cost is that external database cleanup may remain pending.
- Ruling: Preserve the existing labeling URL namespace and admin/CSRF conventions — this minimizes integration risk while changing only workflow semantics.
