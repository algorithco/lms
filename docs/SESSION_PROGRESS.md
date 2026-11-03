# Session progress — feat/ui-qa-real-exams

Branch: `feat/ui-qa-real-exams` (from `main` @ `ec34526`). **Never merge it to `main` directly: a merge auto-deploys to production** (CI → Build → Deploy, no database backup in the pipeline). Finish with a PR and stop.

## Stage 0 — start: done
- #116 is in `main` and deployed (see `docs/DEPLOY_LOG.md`). Still open from #116: a real FREE-account check on production (receipt stays pending, group join grants nothing, `/my-subscription` = `/profile` limits) — needs a test account from the owner.
- Decisions: (a) exam priority CEFR → IELTS → BMB → Attestatsiya; (b) no official IELTS table → public table labelled "taxminiy" in a JSON scale; (c) listening audio comes later (upload + player + "audio not uploaded" state); (d) QA accounts only in the LOCAL DB via `seed_qa_accounts`.
- Server access needs the owner's permission each time; `bestway-vps` may be used read-only inside `/opt/lms`.

## Stage 1 — real QA: done for what could be run
`docs/QA_REPORT.md` has the table. 8 bugs fixed with commits (IELTS unusable, invented topic analysis, result under exam, false pricing promise, teacher endpoints, flags/subject switcher, landing claims, audit command). Not tested: Telegram, AI (essay/speaking/vision), audio, arena, external payment.

## Stage 2 — real exams: partly done
- Done: answer keys never leave the server (test); autosave + server timer + reload survive (BMB checked in the browser); confirm dialog with unanswered count; IELTS and plain CEFR run on the CD screen via `cdAdapter`; IELTS result = raw score + **estimated** band (no certificate wording).
- Not done: IELTS band table → JSON scale per section (existing tests pin the old values; needs its own change); audio upload + once-only player; JSON/Excel bulk import with preview; `Attestatsiya` walkthrough (no local content); tab-switch warning and offline retry were not exercised; CEFR-301 L/R split needs sections in the content; removing the dead legacy English screen.

## Stage 3 — design: partly done
`docs/DESIGN_AUDIT.md` (15 items). Fixed: flags, subject vs language switchers, header tag by subject, landing claims/buttons, pricing copy, typo. Open: Tailwind remnants, 44 px targets on legacy pages, referral card, onboarding contrast, header overlap, hard-coded strings.

## Stage 4 — feedback: done (except screenshot)
Extended `UserFeedback` (migration `notifications.0013`, columns only). Modal, admin inbox, my feedback, landing block (consent + approval only), one-tap result prompt, Celery alerts/replies, 14 backend tests. Not built: optional screenshot attachment (needs file storage and a privacy decision).

## Stage 5 — final
See the PR description for checks, migrations and open questions.
