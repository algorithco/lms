# Milliy Sertifikat Exam Engine

First-class exam domain on top of the canonical Grandec test/essay
architecture. Legacy SINGLE/MULTIPLE/TEXT behavior is preserved; WRITTEN and
READING are never faked as MCQ.

## Domain model (`apps/tests/models.py`)

- `ExamSection` — configurable section (test FK, name, code, order,
  duration_minutes, weight). Questions without a section keep working
  (ordinary tests are unaffected).
- `ReadingPassage` — first-class passage (test FK, optional section FK,
  title, content, source, order). Many questions attach via
  `Question.reading_passage`; the text is stored once. The legacy free-text
  `Question.passage` field is untouched.
- `Question` — new types `gap_fill`, `matching`, `written` alongside
  `single`/`multiple`/`text`; optional `section` + `reading_passage` FKs;
  `config` JSON only for optional flags (`partial_credit`,
  `case_sensitive`, `min_words`/`max_words` guidance).
- `GapBlank` — one row per accepted answer per blank position
  (question, position, answer_text). Relational, no JSON blobs.
- `MatchingPrompt` / `MatchingOption` (stable ids, positions) /
  `MatchingPair` (prompt OneToOne → correct option; the answer key).
- `GapResponse` (answer, blank_position, response_text; unique together),
  `MatchingResponse` (answer, prompt, selected_option NULL-able; unique).
- `StudentAnswer` += `written_text`, `written_word_count` (draft autosave).
- `ExamWrittenBridge` — idempotent (attempt, question) link:
  answer OneToOne ↔ `essays.EssaySubmission` OneToOne + rubric_version.
- `AttemptSectionProgress` — per-section server-side timer
  (attempt, section, started_at, completed_at; unique together).
- `ExamScoringProfile` — named-versioned config (weights JSON,
  certificate_min_percentage). NO official coefficients: the shipped
  `default:v1` profile carries empty weights (equal) and must be configured
  with verified rules before real use.
- `TestAttempt.Status` += `PENDING_GRADING`.
- `Result` += `grading_status` (graded/pending_grading), `objective_score`,
  `writing_score`, `scoring_profile` FK, `scoring_version`
  (`name:version`), `rubric_version`. Plus `ResultSectionScore`
  (result, section FK, code, name, earned, maximum, weight; relational).

## Question types

| Type | Storage | Grading | Autosave |
|---|---|---|---|
| SINGLE/MULTIPLE/TEXT | Choice M2M / text_answer | unchanged (exact-match, all-or-nothing multiple, normalized text) | unchanged |
| GAP_FILL | GapBlank rows; GapResponse per position | all blanks correct → full; `partial_credit` → proportional; normalization follows TEXT | debounced per-blank upsert; extras ignored |
| MATCHING | Prompt/Option/Pair rows; MatchingResponse per prompt | all pairs → full; `partial_credit` → proportional; id-based (shuffle-safe) | immediate upsert; invalid ids rejected |
| WRITTEN | written_text draft | never objective; essay bridge scales effective_score | debounced textarea draft + word count |

Gap text convention: `___` (2+ underscores) markers map in order to blank
positions; questions without markers render one input per blank.

## Attempt lifecycle

`IN_PROGRESS → COMPLETED | TIMEOUT | PENDING_GRADING | CANCELLED`;
`PENDING_GRADING → COMPLETED` (finalize, idempotent). Terminal states have
no outgoing transitions (`TestAttempt.STATUS_TRANSITIONS`). Only IN_PROGRESS
accepts autosave; re-submit on PENDING_GRADING finalizes; completed/timeout
re-submit errors; finalize on non-pending errors (202 pending via API).

## Autosave contract

One endpoint `POST /api/tests/attempts/<id>/save-answer/` accepts
`choice_ids`, `text_answer`, `gap_answers {pos: text}`,
`matching {prompt_id: option_id|null}`, `written_text`. Atomic upsert,
ownership (404 for foreign/missing), active-attempt + attempt/section timer
gates (server authority), no duplicate rows. Frontend debounces text-like
inputs (800ms); choice/matching save immediately. States: saving/saved/error
inline — no disruptive alerts.

## Essay bridge (`ExamBridgeService`)

Submit with written text → `get_or_create` bridge → create ONE
topic-less `EssaySubmission` (DRAFT) → `start_grading()` (canonical engine).
Idempotent: repeated submits reuse the submission; AI failure keeps the exam
PENDING_GRADING and finalize retries DRAFT submissions. Objective portions
complete independently. `written_earned()` scales effective_score (24-base)
onto question points; ungraded writing is pending, never zero.

## Scoring (`apps/tests/scoring.py` — single source)

`grade_gap_fill`, `grade_matching`, `written_earned`, `normalize_text`,
`aggregate()` → per-question scores, per-section earned/max, objective and
writing subtotals, weighted percentage (equal weights ⇒ legacy formula).
`_grade_attempt` prefetches (questions+choices+gaps+matching, answers,
M2M/through tables) and scores in Python with one `bulk_update`; Result +
section rows persist via `get_or_create`/`update_or_create` (no
IntegrityError-driven flow). Certificates/notifications dispatch ONLY when
fully graded; finalize dispatches on completion.

## Profiles, versions, thresholds

- `ExamScoringProfile(name, version)`: weights per section code, cert minimum,
  `is_verified` (default False). `Test.scoring_profile` links an exam to its
  rules (NULL = legacy path). Effective profile = linked, else auto-created
  UNVERIFIED `default:v1`. Result pins `scoring_profile` + `scoring_version`.
- `ESSAY_RUBRIC_VERSION = "grandec-essay-12x2-v1"` (`apps/essays/services.py`):
  INTERNAL identifier (official status UNVERIFIED), pinned on bridge + result.
  Bump with rubric semantic changes; never rewrite history.
- **No official Uzbek scoring coefficients or thresholds are encoded.**
  `default:v1` is an equal-weight placeholder. Configure a verified profile
  before real Milliy Sertifikat content goes live; history never rewrites
  (pinned versions).

## Official Rules Integration (readiness status: architecture ready, rules pending)

- Engine architecture is implemented; **official coefficients/thresholds are
  NOT supplied** and none are hardcoded.
- `is_verified` separates DRAFT/UNVERIFIED from VERIFIED/ACTIVE.
  `certificate_min_percentage` (default 60) is INERT until its profile is
  verified — an unverified profile never issues certificates regardless of
  score. No substitute value was invented.
- `certificate_status(result)` (`apps/certificates/services/generation.py`)
  is canonical: `pending_writing` | `rules_unverified` | `not_passed` |
  `below_threshold` | `eligible`. Only `eligible` generates. Legacy plain
  tests bypass milliy rules entirely (historical behavior preserved).
- Changing a profile later never rewrites historical Results (values +
  `scoring_version` pinned at grade time; covered by test).
- Result detail exposes `certificate_status`; the UI shows pending/unverified
  wording instead of pass/fail in those states and gates the certificate CTA.

## E2E contract (student exam lifecycle)

discover (`GET /api/tests/`, detail) → start (`POST .../start/`) → payloads
(sections, passages, per-type questions, NO answer keys) → autosave per type
(debounced text-like, immediate choice/matching; saving/saved/error inline) →
resume (`GET attempt/` — same `started_at`, server timers, stable ids) →
submit → objective graded, `PENDING_GRADING` when writing present →
mutations rejected → essay grades canonically → `finalize` (explicit
`POST .../finalize/`, re-submit, or attempt-view auto-finalize) → COMPLETED,
Result + section rows refreshed → result detail shows sections, versions,
`certificate_status` → certificate only when eligible (verified + threshold).
TMA supports legacy choice/text only and returns
`unsupported_question_type` for new types without touching attempts;
bulk import accepts SINGLE-column CSVs only and rejects unknown columns.

## API paths

- Existing `/api/tests/...` unchanged + `POST .../attempts/<id>/finalize/`
  (200 completed / 202 pending / 400 invalid).
- Attempt/test detail now include `sections`, `passages`, `section_progress`
  and per-type student payloads WITHOUT keys (no is_correct, no accepted
  answers, no mappings).
- Panel (admin): question CRUD accepts `gaps`/`matching` payloads;
  `GET|POST /api/v1/panel/tests/<id>/sections|/passages/`.
- Results: list adds `grading_status`; detail adds grading/objective/writing
  scores, versions, `section_scores`, `certificate_status`, per-type review blocks.

## Grading lifecycle (written)

autosave draft → submit creates submission (PENDING) → objective graded,
attempt PENDING_GRADING → AI/teacher grades essay → `finalize` (explicit
endpoint, re-submit, or attempt-view auto-finalize) → COMPLETED + Result
refresh + cert dispatch if passed. AI failure never corrupts exam state.

## Known limitations

- TMA (`apps/telegram_app/test_api.py`) and the bot quiz flow drive legacy
  choice/text answers; new types are explicitly rejected with
  `unsupported_question_type` (no silent empty submissions). Full TMA parity
  for gap/matching/written is future work.
- `bulk_import` creates single-choice questions only; unknown columns
  (including any `type` request) are rejected loudly.
