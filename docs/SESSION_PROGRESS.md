# Session progress — feat/ui-qa-real-exams

Branch: `feat/ui-qa-real-exams` (from `main` @ `ec34526`). **Never merge it to `main` directly: a merge auto-deploys to production.** Finish with a PR and stop.

## Stage 0 — start
- [x] PR #116 is in `main` (a39529a, v1.77.0) and deployed (see `docs/DEPLOY_LOG.md`).
- [x] Branch created.
- [x] Fixed `audit_unpaid_subscriptions` (wrong essay field) + regression test.
- [ ] Open from #116: FREE-account behaviour check (receipt stays pending, group join grants nothing, limits equal on `/my-subscription` and `/profile`) — needs a test account from the owner.
- [ ] Questions a–d asked, answers pending.

## Decisions
- Server access in this session needs the owner's permission each time; `bestway-vps` alias is allowed for read-only checks inside `/opt/lms`.
- Subscriptions only through `grant_subscription` (kinds: approved_payment, provider_payment, admin, teacher_quota).
- No new libraries without asking; all UI text through i18n (UZ/EN).

## Stages
- [ ] 1. Real QA of the whole site → `docs/QA_REPORT.md`
- [ ] 2. Real exam experience
- [ ] 3. Design simplification → `docs/DESIGN_AUDIT.md`
- [ ] 4. Feedback system
- [ ] 5. Final checks, PR, stop
