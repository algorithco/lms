# Branch protection — one-time admin setup.
#
# CONTEXT: this repo is PRIVATE on the Free plan. GitHub returns 403 for
#   gh api repos/algorithco/lms/branches/main/protection
# ("Upgrade to GitHub Pro or make this repository public to enable this feature").
# Until you upgrade or go public, enforcement is via process + CI + local hook:
#   CONTRIBUTING.md workflow, .githooks/pre-push, CODEOWNERS, required Actions.
# When eligible, apply the real server-side rule below.

## Option A — UI (recommended)

1. GitHub → algorithco/lms → Settings → Branches → Add classic branch protection rule
2. Branch name pattern: `main`
3. Enable:
   - [x] Require a pull request before merging (required approvals: 1)
   - [x] Dismiss stale pull request approvals when new commits are pushed
   - [x] Require review from Code Owners
   - [x] Require status checks before merging → Require branches to be up to date
     - Required checks: `test`, `security`
   - [x] Require conversation resolution before merging
   - [x] Require signed commits (recommended)
   - [x] Require linear history (squash-merge)
   - [x] Do not allow bypassing the above settings
   - [ ] Allow force pushes → OFF, Allow deletions → OFF
   - Restrict who can push: nobody (PRs only)
4. Save. Verify: try `git push origin main` → must be rejected.

## Option B — API (Pro/Team or public repo)

```bash
gh api repos/algorithco/lms/branches/main/protection -X PUT \
  -f required_status_checks[strict]=true \
  -f required_status_checks[checks][][context]='test' \
  -f required_status_checks[checks][][context]='security' \
  -f enforce_admins=true \
  -f required_pull_request_reviews[dismiss_stale_reviews]=true \
  -f required_pull_request_reviews[require_code_owner_reviews]=true \
  -f required_pull_request_reviews[required_approving_review_count]=1 \
  -f restrictions=null \
  -f allow_force_pushes=false \
  -f allow_deletions=false \
  -f block_creations=false \
  -f required_conversation_resolution=true
```

Verify:

```bash
gh api repos/algorithco/lms/branches/main/protection --jq '{required_checks: .required_status_checks.checks, pr_reviews: .required_pull_request_reviews, admins: .enforce_admins.enabled}'
```

## Merge settings (Settings → General → Pull Requests)

- [x] Allow squash merging (default), [ ] Allow merge commits, [ ] Allow rebase merging
- [x] Automatically delete head branches (enabled 2026-09-13 via API — works on Free)
- [ ] Allow auto-merge → stays OFF: native auto-merge needs branch protection
  (Pro plan); verified `allow_auto_merge=false` is forced on Free private repos.
  Replacement: `.github/workflows/automerge.yml` (label `automerge` + green
  `test`/`security` + reviews OK → squash + delete branch).

## What CI enforces meanwhile

- `ci.yml` `test` job must pass (ruff + migrate check + 300+ tests)
- `security.yml` `security` job must pass (gitleaks + pip-audit + bandit)
- `CODEOWNERS` (@hamroqulovv) must approve; Dependabot PRs still need CI green
- `deploy.yml` only runs after `Build` succeeds on `main` — never from feature branches
