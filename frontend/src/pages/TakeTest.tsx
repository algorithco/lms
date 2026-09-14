import { useCallback, useEffect, useRef, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { useLang } from '../i18n/LangContext';
import { Tests as TestsApi } from '../lib/api';
import {
  clearDraft,
  formatClock,
  loadDraft,
  num,
  storeDraft,
  type DraftMap,
} from '../lib/testing';
import { ClockIcon } from '../components/icons';

interface Choice {
  id: number;
  text: string;
}

interface Question {
  id: number;
  text: string;
  passage?: string;
  question_type: 'single' | 'multiple' | 'text';
  points: number;
  position: number;
  choices: Choice[];
  selected_choice_ids: number[];
  /** REST AttemptDetailSerializer currently omits text answers — drafts fill the gap. */
  text_answer?: string;
}

interface AttemptDetail {
  id: number;
  test: number;
  test_title: string;
  status: string;
  remaining_seconds: number | null;
  questions: Question[];
  answered_count: number;
}

interface SubmitResult {
  attempt_id: number;
  total_questions: number;
  correct_answers: number;
  wrong_answers: number;
  unanswered: number;
  score: string | number;
  max_score: string | number;
  percentage: string | number;
  is_passed: boolean;
  time_taken_seconds: number;
}

type Answers = Record<number, { choices: number[]; text: string }>;

const TEXT_DEBOUNCE_MS = 800;

function qtypeLabel(qtype: string, t: (k: string) => string): string {
  if (qtype === 'single') return t('take_single');
  if (qtype === 'multiple') return t('take_multiple');
  return t('take_text');
}

export default function TakeTest() {
  const { attemptId = '' } = useParams();
  const navigate = useNavigate();
  const { t } = useLang();
  const [attempt, setAttempt] = useState<AttemptDetail | null>(null);
  const [answers, setAnswers] = useState<Answers>({});
  const [saved, setSaved] = useState<Record<number, boolean>>({});
  const [failed, setFailed] = useState<Record<number, string>>({});
  const [remaining, setRemaining] = useState<number | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [result, setResult] = useState<SubmitResult | null>(null);
  const [savingAll, setSavingAll] = useState(false);
  const timers = useRef<Record<number, ReturnType<typeof setTimeout>>>({});
  const submittedRef = useRef(false);

  const load = useCallback(async () => {
    setLoadError(null);
    try {
      const a = (await TestsApi.attempt(attemptId)) as unknown as AttemptDetail;
      setAttempt(a);
      setRemaining(a.remaining_seconds);
      const draft = loadDraft(attemptId);
      setAnswers((prev) => {
        if (Object.keys(prev).length > 0) return prev;
        const init: Answers = {};
        for (const q of a.questions ?? []) {
          const d: DraftMap[number] | undefined = draft[q.id];
          init[q.id] = {
            choices: d ? [...d.choices] : [...(q.selected_choice_ids ?? [])],
            // Server does not return text answers on the attempt endpoint,
            // so a local draft is the only resume source for text questions.
            text: d ? d.text : String(q.text_answer ?? ''),
          };
        }
        return init;
      });
      setSaved((prev) => {
        if (Object.keys(prev).length > 0) return prev;
        const s: Record<number, boolean> = {};
        for (const q of a.questions ?? []) {
          s[q.id] = (q.selected_choice_ids ?? []).length > 0 || Boolean(q.text_answer);
        }
        return s;
      });
    } catch (e) {
      setLoadError(e instanceof Error ? e.message : t('err_retry_js'));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [attemptId]);

  useEffect(() => {
    load();
    return () => {
      for (const id of Object.values(timers.current)) clearTimeout(id);
      timers.current = {};
    };
  }, [load]);

  const persist = useCallback(
    (next: Answers) => {
      const draft: DraftMap = {};
      for (const [qid, a] of Object.entries(next)) {
        draft[Number(qid)] = { choices: a.choices, text: a.text, updatedAt: Date.now() };
      }
      storeDraft(attemptId, draft);
    },
    [attemptId],
  );

  // Countdown — backend auto-timeouts on expiry (AttemptDetailView +
  // SaveAnswerService), so at zero we auto-submit once.
  useEffect(() => {
    if (remaining === null || remaining <= 0) return;
    const id = setInterval(() => setRemaining((r) => (r !== null ? r - 1 : r)), 1000);
    return () => clearInterval(id);
  }, [remaining]);

  const doSubmit = useCallback(
    async (auto = false) => {
      if (submittedRef.current || submitting) return;
      submittedRef.current = true;
      setSubmitting(true);
      setErr(null);
      try {
        // Flush unsaved answers first (best effort, incl. retries).
        for (const q of attempt?.questions ?? []) {
          const a = answers[q.id];
          if (!a) continue;
          const dirty = !saved[q.id] || failed[q.id];
          if (dirty && (a.choices.length > 0 || a.text.trim())) {
            await TestsApi.saveAnswer(attemptId, {
              question_id: q.id,
              choice_ids: a.choices,
              text_answer: a.text,
            }).catch(() => undefined);
          }
        }
        const out = (await TestsApi.submit(attemptId)) as unknown as {
          result?: SubmitResult;
        } & SubmitResult;
        const r: SubmitResult = (out.result ?? out) as SubmitResult;
        setResult(r);
        clearDraft(attemptId);
      } catch (e) {
        submittedRef.current = false;
        setErr(
          (e instanceof Error ? e.message : t('err_retry_js')) +
            (auto ? ` (${t('take_auto_submit')})` : ''),
        );
        setSubmitting(false);
      }
    },
    [attempt, answers, saved, failed, attemptId, submitting, t],
  );

  useEffect(() => {
    if (remaining === 0 && attempt && !result) {
      doSubmit(true);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [remaining]);

  const save = useCallback(
    async (q: Question, a?: { choices: number[]; text: string }) => {
      const cur = a ?? answers[q.id] ?? { choices: [], text: '' };
      // Empty choice answers cannot be saved (backend requires ≥1 choice);
      // empty text clears remotely only when the backend supports it.
      if (q.question_type !== 'text' && cur.choices.length === 0) {
        setSaved((s) => ({ ...s, [q.id]: false }));
        return;
      }
      setFailed((f) => {
        if (!(q.id in f)) return f;
        const next = { ...f };
        delete next[q.id];
        return next;
      });
      try {
        const res = (await TestsApi.saveAnswer(attemptId, {
          question_id: q.id,
          choice_ids: cur.choices,
          text_answer: cur.text,
        })) as unknown as { remaining_seconds?: number | null };
        setSaved((s) => ({ ...s, [q.id]: true }));
        if (typeof res?.remaining_seconds === 'number') {
          setRemaining(res.remaining_seconds);
        }
      } catch (e) {
        setSaved((s) => ({ ...s, [q.id]: false }));
        setFailed((f) => ({
          ...f,
          [q.id]: e instanceof Error ? e.message : t('take_save_failed'),
        }));
      }
    },
    [answers, attemptId, t],
  );

  const pick = (q: Question, choiceId: number) => {
    setAnswers((prev) => {
      const cur = prev[q.id] ?? { choices: [], text: '' };
      const has = cur.choices.includes(choiceId);
      const choices =
        q.question_type === 'multiple'
          ? has
            ? cur.choices.filter((c) => c !== choiceId)
            : [...cur.choices, choiceId]
          : [choiceId];
      const next = { ...prev, [q.id]: { ...cur, choices } };
      persist(next);
      return next;
    });
    setSaved((s) => ({ ...s, [q.id]: false }));
    // Choice answers auto-save immediately (legacy take_test.html parity).
    const cur = answers[q.id] ?? { choices: [], text: '' };
    const has = cur.choices.includes(choiceId);
    const choices =
      q.question_type === 'multiple'
        ? has
          ? cur.choices.filter((c) => c !== choiceId)
          : [...cur.choices, choiceId]
        : [choiceId];
    save(q, { choices, text: cur.text });
  };

  const editText = (q: Question, text: string) => {
    setAnswers((prev) => {
      const next = { ...prev, [q.id]: { choices: [], text } };
      persist(next);
      return next;
    });
    setSaved((s) => ({ ...s, [q.id]: false }));
    // Debounced autosave for text (legacy oninput parity without flooding).
    if (timers.current[q.id]) clearTimeout(timers.current[q.id]);
    timers.current[q.id] = setTimeout(() => {
      save(q, { choices: [], text });
    }, TEXT_DEBOUNCE_MS);
  };

  const retryFailed = async () => {
    setSavingAll(true);
    try {
      for (const q of attempt?.questions ?? []) {
        if (failed[q.id]) {
          const a = answers[q.id];
          if (a) await save(q, a);
        }
      }
    } finally {
      setSavingAll(false);
    }
  };

  if (loadError && !attempt) {
    return (
      <div>
        <h1>{t('take_title')}</h1>
        <p className="error">{loadError}</p>
        <div className="toolbar">
          <button className="btn primary" onClick={load}>
            {t('essay_error_retry')}
          </button>
          <Link className="btn ghost" to="/tests">
            {t('back')}
          </Link>
        </div>
      </div>
    );
  }
  if (!attempt) return <p className="muted">{t('loading')}</p>;

  const finished =
    attempt.status === 'completed' ||
    attempt.status === 'timeout' ||
    attempt.status === 'cancelled';

  const answeredCount = attempt.questions.filter((q) => {
    const a = answers[q.id];
    if (!a) return false;
    return a.choices.length > 0 || a.text.trim().length > 0;
  }).length;
  const unanswered = attempt.questions.length - answeredCount;
  const failedCount = Object.keys(failed).length;
  const timerClass =
    remaining === null ? '' : remaining <= 60 ? ' low' : '';

  return (
    <div>
      <p className="muted small">
        <Link to="/tests">← {t('tests')}</Link>
      </p>
      <h1>{attempt.test_title}</h1>
      {err && <p className="error">{err}</p>}

      {finished && !result && (
        <div className="card">
          <p className="muted">{t('take_already_finished')}</p>
          <Link className="btn primary" to="/results">
            {t('my_results')}
          </Link>
        </div>
      )}

      {failedCount > 0 && (
        <p className="error">
          {t('take_save_failed')} ({failedCount}){' '}
          <button className="btn sm" onClick={retryFailed} disabled={savingAll}>
            {savingAll ? t('loading') : t('essay_error_retry')}
          </button>
        </p>
      )}

      <div className="toolbar">
        {remaining !== null && (
          <span className={`timer${timerClass}`}>
            <ClockIcon size={14} className="ico" /> {formatClock(remaining)}
          </span>
        )}
        <span className="badge">
          {answeredCount}/{attempt.questions.length} ✓
        </span>
        {attempt.status === 'timeout' && (
          <span className="badge rose">{t('take_time_up')}</span>
        )}
      </div>
      <div className="progress" style={{ marginBottom: 16 }}>
        <div
          style={{
            width: `${(answeredCount / Math.max(attempt.questions.length, 1)) * 100}%`,
          }}
        />
      </div>

      {/* Question navigator (legacy take_test.html parity). */}
      <div className="toolbar" style={{ marginBottom: 16 }} aria-label={t('questions')}>
        {attempt.questions.map((q, i) => {
          const a = answers[q.id];
          const done = Boolean(a && (a.choices.length > 0 || a.text.trim()));
          return (
            <a
              key={q.id}
              href={`#question-${q.id}`}
              className={`badge${done ? ' green' : ''}${failed[q.id] ? ' rose' : ''}`}
            >
              {i + 1}
            </a>
          );
        })}
      </div>

      {attempt.questions.map((q, i) => {
        const a = answers[q.id] ?? { choices: [], text: '' };
        return (
          <div key={q.id} id={`question-${q.id}`} className="card" style={{ marginBottom: 12 }}>
            <p className="muted small">
              {t('th_questions')} {i + 1}/{attempt.questions.length} · {q.points}{' '}
              {t('points')} · {qtypeLabel(q.question_type, t)}
            </p>
            {q.passage && (
              <p className="muted" style={{ whiteSpace: 'pre-line' }}>
                {q.passage}
              </p>
            )}
            <p style={{ fontWeight: 700 }}>{q.text}</p>
            {q.question_type === 'text' ? (
              <textarea
                rows={3}
                value={a.text}
                disabled={finished || submitting}
                onChange={(e) => editText(q, e.target.value)}
                onBlur={() => {
                  if (timers.current[q.id]) clearTimeout(timers.current[q.id]);
                  if (a.text.trim()) save(q, a);
                }}
                placeholder={t('take_text_ph')}
                style={{ width: '100%', marginTop: 8 }}
              />
            ) : (
              <div style={{ display: 'grid', gap: 8, marginTop: 8 }}>
                {q.choices.map((c, ci) => {
                  const on = a.choices.includes(c.id);
                  const letter = String.fromCharCode(65 + ci);
                  return (
                    <button
                      key={c.id}
                      type="button"
                      disabled={finished || submitting}
                      className={`quiz-opt${on ? ' picked' : ''}`}
                      aria-pressed={on}
                      onClick={() => pick(q, c.id)}
                    >
                      <span className="quiz-key">
                        {on ? '✓' : letter}
                      </span>
                      <span>{c.text}</span>
                    </button>
                  );
                })}
              </div>
            )}
            <div style={{ marginTop: 8 }} className="toolbar">
              {q.question_type !== 'text' || a.text.trim() ? (
                <button
                  className="btn sm ghost"
                  disabled={finished || submitting}
                  onClick={() => save(q, a)}
                >
                  {saved[q.id] && !failed[q.id]
                    ? `✓ ${t('essay_js_saved')}`
                    : t('save')}
                </button>
              ) : null}
              {failed[q.id] && (
                <span className="error small">
                  {failed[q.id]}{' '}
                  <button className="btn sm ghost" onClick={() => a && save(q, a)}>
                    {t('essay_error_retry')}
                  </button>
                </span>
              )}
            </div>
          </div>
        );
      })}

      {!finished && !result && (
        <button
          className="btn primary"
          disabled={submitting}
          onClick={() => setConfirmOpen(true)}
        >
          {submitting ? t('loading') : t('take_finish')}
        </button>
      )}

      {confirmOpen && !result && (
        <div className="card" role="dialog" aria-modal="true" style={{ marginTop: 16 }}>
          <h3>{t('take_confirm_title')}</h3>
          <p className="muted">
            {unanswered === 0
              ? t('take_confirm_all')
              : `${answeredCount}/${attempt.questions.length} · ${t('take_confirm_left')}: ${unanswered}`}
          </p>
          <div className="toolbar">
            {attempt.questions.map((q, i) => {
              const a = answers[q.id];
              const done = Boolean(a && (a.choices.length > 0 || a.text.trim()));
              return (
                <span key={q.id} className={`badge${done ? ' green' : ' rose'}`}>
                  {i + 1}
                </span>
              );
            })}
          </div>
          <div className="toolbar" style={{ marginTop: 12 }}>
            <button className="btn ghost" onClick={() => setConfirmOpen(false)}>
              {t('cancel')}
            </button>
            <button
              className="btn primary"
              disabled={submitting}
              onClick={() => {
                setConfirmOpen(false);
                doSubmit(false);
              }}
            >
              {submitting ? t('loading') : t('confirm')}
            </button>
          </div>
        </div>
      )}

      {result && (
        <div className="card" style={{ marginTop: 16 }}>
          <h2 className={result.is_passed ? '' : ''}>
            {result.is_passed ? t('rd_passed_msg') : t('rd_failed_msg')}
          </h2>
          <p className="stat-value">{num(result.percentage, 0)}%</p>
          <div className="toolbar">
            <span className="badge green">
              {t('rd_correct')}: {result.correct_answers}
            </span>
            <span className="badge rose">
              {t('rd_wrong')}: {result.wrong_answers}
            </span>
            <span className="badge">
              {t('rd_unanswered')}: {result.unanswered}
            </span>
            <span className="badge blue">
              {t('rd_time_spent')}: {formatClock(num(result.time_taken_seconds, 0))}
            </span>
          </div>
          <div className="toolbar" style={{ marginTop: 12 }}>
            <button className="btn primary" onClick={() => navigate('/results')}>
              {t('take_view_results')}
            </button>
            {result.is_passed && (
              <button className="btn" onClick={() => navigate('/certificates')}>
                {t('my_certificates')}
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
