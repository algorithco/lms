# Contributing

> **Rule #1: never push directly to `main`.** Every change goes through a Pull Request with green Actions.

## Workflow

```bash
git checkout main && git pull origin main
git checkout -b feat/my-change   # or fix/..., chore/...
# ... edit, keep commits small ...
ruff check .
python manage.py check
python manage.py test tests --verbosity=1
git push -u origin feat/my-change
gh pr create --fill
```

Merge only when:

1. CI (`test` job) + Security (`security` job) are green
2. `CODEOWNERS` approval given, conversations resolved
3. Branch is up to date with `main`
4. Squash-merge, delete the branch after merge

## Automerge (no waiting)

Add the `automerge` label and walk away — `.github/workflows/automerge.yml`
squash-merges + deletes the branch as soon as all gates pass:

- base `main`, not draft, no conflicts, no unresolved `CHANGES_REQUESTED`
- checks `test` + `security` green on the head SHA
- your own PRs: your label counts as approval
- Dependabot PRs: still need 1 human approval first, then they merge themselves

Remove the label any time to stop it. Native GitHub auto-merge is unavailable
here (needs branch protection = Pro plan), so this workflow is the replacement —
see [`.github/BRANCH_PROTECTION.md`](./BRANCH_PROTECTION.md).

## Local guard

Direct pushes to `main` are blocked locally:

```bash
git config core.hooksPath .githooks
# now `git push origin main` fails — open a PR instead
```

## Server-side enforcement (admin, one-time)

This repo is private on the Free plan, where GitHub disables branch protection
via API. Once you upgrade to Pro/Team or go public, enforce it for real —
see [`.github/BRANCH_PROTECTION.md`](./BRANCH_PROTECTION.md) for the exact
UI steps + `gh api` commands (require PR, 1 approval, required checks,
no force-push, no deletions, block bypass).

## Commit style

`feat:`, `fix:`, `docs:`, `chore:`, `ci:`, `deploy:`, `security:` — imperative,
short subject line (e.g. `fix: deterministic TMA essay-start`).
