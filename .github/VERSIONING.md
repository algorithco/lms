# Versioning rule — SemVer, starting at 0.1

Single source of truth: root `VERSION` file (currently `0.1.0`).
Every version is also a git tag `vX.Y.Z` + GitHub Release.
`/healthz/` returns the running version (`{"status":"ok","db":true,"version":"0.2.0"}`).

## Format: MAJOR.MINOR.PATCH

| Part  | When to bump | Example |
| ----- | ------------ | ------- |
| MINOR | **Every update to `main`** (default, automatic) | `0.1.0` → `0.2.0` → `0.3.0` |
| PATCH | Hotfix without new features (manual) | `0.2.0` → `0.2.1` |
| MAJOR | Stable / breaking milestone (manual) | `0.9.0` → `1.0.0` |

Short form `0.1`, `0.2` = `0.1.0`, `0.2.0` (patch zero).

## How it works

1. Merge PR to `main` (CI `test` + `security` green, owner approval).
2. `Release` workflow runs automatically → MINOR bump → pushes tag `v0.N.0`,
   creates GitHub Release with auto notes, commits `chore(release): v0.N.0 [skip ci]`
   which updates `VERSION` without re-triggering CI.
3. First run tags exactly what `VERSION` says (`v0.1.0`); every next push bumps minor.
4. Manual: `Actions → Release → Run workflow → bump: patch|major` for hotfix/stable.
5. Rollback: `Deploy → Run workflow → tag: v0.N-1.0` (previous release tag).

## Rules

- Never edit `VERSION` by hand in feature PRs — the bot owns it.
- Never create tags by hand — use the workflow (keeps tag + Release + file in sync).
- `[skip ci]` on release commits is intentional (tag push already ran CI on the same SHA).
- The only bot allowed to push to `main` is `github-actions[bot]` for `chore(release)`.
  Everyone else: PR only (see `CONTRIBUTING.md`, `.githooks/pre-push`).
