# Security Policy

## Supported versions

Only `main` is supported. Security fixes land on `main` via Pull Request and
are deployed from GHCR (`ghcr.io/algorithco/lms`). No LTS branches.

| Branch | Supported |
| ------ | --------- |
| `main` | ✅ |
| feature branches | ❌ (short-lived, reviewed before merge) |

## Reporting a vulnerability

**Do not open public issues, discussions, or PRs for vulnerabilities.**

1. Use GitHub private advisory: `Security → Advisories → Report a vulnerability`
   (`https://github.com/algorithco/lms/security/advisories/new`), or email the maintainer.
2. Include: affected endpoint/version, reproduction steps, impact, and redacted logs.
3. Expect acknowledgement within 48h and a fix timeline within 7 days for critical issues.

## What we already enforce

- No direct pushes to `main` — all changes via PR + green CI (`CONTRIBUTING.md`)
- `CODEOWNERS` review required; squash merge; linear history preferred
- Secrets never committed: `.env`, `.env.prod`, `*.pem`, `*.key`,
  `deploy/secrets/*` are git-ignored; production secrets live only in
  GitHub Actions secrets / VPS `.env.prod` (see `deploy.yml` temp `DOCKER_CONFIG` login)
- Push protection (local): `.githooks/pre-push` blocks `git push origin main`
- Supply chain: Dependabot (pip + Actions, weekly), pinned Docker base images,
  `pip-audit` + `bandit` + `gitleaks` on every PR (`security.yml`)
- Runtime: `check --deploy`, HSTS/secure cookies in prod, rate limits + fail2ban on Nginx,
  `migrate --check` + `/healthz/` gate in deploy

## After a suspected leak

1. Rotate the credential immediately (Telegram token, Django secret, DB password, GHCR PAT).
2. Purge it from git history (`git filter-repo`), force-push a clean branch, open a new PR.
3. Invalidate sessions/tokens and check `NotificationLog` / deploy logs for abuse.
