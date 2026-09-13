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

1. CI (`test` job) + Security (`gitleaks`, `pip-audit`, `bandit`) are green
2. `CODEOWNERS` approval given, conversations resolved
3. Branch is up to date with `main`
4. Squash-merge, delete the branch after merge

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
