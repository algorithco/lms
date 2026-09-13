## What does this PR change?

<!-- One paragraph. Link related issue: Closes #... -->

## Type

- [ ] feat
- [ ] fix
- [ ] docs / chore / ci
- [ ] security

## Checklist

- [ ] Branch is `feat/*`, `fix/*` or `chore/*` — **not `main`** (direct pushes to `main` are blocked)
- [ ] `ruff check .` passes
- [ ] `python manage.py check` passes
- [ ] `python manage.py test tests` passes (or CI green)
- [ ] No secrets committed (`.env`, `.env.prod`, `*.pem`, `*.key`, `htpasswd-admin`)
- [ ] Migrations included if models changed (`manage.py makemigrations`)
- [ ] Docs updated (`README.md` / `DEPLOYMENT.md` / `RELEASE_NOTES.md` if needed)
- [ ] Add `automerge` label if it should merge itself when green (no `CHANGES_REQUESTED`, checks pass)

## Screenshots / evidence

<!-- Paste CI run link, curl output, or screenshots -->

## Deployment notes

<!-- Anything deploy.yml / VPS needs to know? Leave blank if none. -->
