import { useCallback, useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { useLang } from '../i18n/LangContext';
import { Essays, ensureSession } from '../lib/api';
import { getCachedPassword, useAuth } from '../auth/AuthContext';
import {
  countEssayWords,
  isEssayDone,
  isEssayTerminal,
  requestTeacherReview,
} from '../lib/essays-arena';

/**
 * Essay result — mirrors GET /tma/api/essays/<id>/result/ (JWT), polled
 * while the status is non-terminal (pending/draft), exactly like the legacy
 * polling against GET /essays/api/<id>/status/ (templates/essays/result.html
 * polls until graded/ai_evaluated/pending_teacher/teacher_reviewed/error).
 *
 * Extra legacy behavior ported from templates/essays/result.html:
 * - pending_teacher → "teacher reviewing" card (terminal, no more polling)
 * - error → error card with retry link
 * - final_score (teacher override) takes visual priority over the AI score
 * - AI improved version via POST /essays/result/<id>/improve/ (session-only
 *   JSON; needs ensureSession() first — no JWT equivalent exists)
 * - teacher-review request via POST /essays/<id>/request-review/
 *   (session-only HTML partial; sent as a form POST, no JWT equivalent)
 */

interface Criterion {
  id: number;
  name: string;
  score: number;
  max_score?: number;
  reason: string;
  errors?: string[];
}

interface Result {
  status: string;
  total_score: number | null;
  max_score: number;
  converted_score: number | null;
  score_percentage?: number;
  final_score: number | null;
  summary: string;
  word_count: number;
  is_off_topic: boolean;
  topic_title: string;
  criteria: Criterion[];
  graded_at?: string | null;
  poll_after?: number;
}

export default function EssayResult() {
  const { id = '' } = useParams();
  const { t } = useLang();
  const { user } = useAuth();
  const [res, setRes] = useState<Result | null>(null);
  const [err, setErr] = useState<string | null>(null);

  // Improved version (session improve endpoint).
  const [improvedOpen, setImprovedOpen] = useState(false);
  const [improved, setImproved] = useState<string | null>(null);
  const [improvedBusy, setImprovedBusy] = useState(false);
  const [improvedErr, setImprovedErr] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  // Teacher-review request (session form endpoint).
  const [reason, setReason] = useState('');
  const [reviewBusy, setReviewBusy] = useState(false);
  const [reviewSent, setReviewSent] = useState(false);
  const [reviewErr, setReviewErr] = useState<string | null>(null);

  useEffect(() => {
    let stop = false;
    let timer: ReturnType<typeof setTimeout>;
    const poll = async () => {
      try {
        const r = (await Essays.result(id)) as unknown as Result;
        if (stop) return;
        setRes({ ...r, criteria: r.criteria ?? [] });
        if (!isEssayTerminal(r.status)) {
          timer = setTimeout(poll, (r.poll_after ?? 3) * 1000);
        }
      } catch (e) {
        if (!stop) setErr(e instanceof Error ? e.message : 'Failed.');
      }
    };
    poll();
    return () => {
      stop = true;
      clearTimeout(timer);
    };
  }, [id]);

  const loadImproved = useCallback(async () => {
    if (improved !== null || improvedBusy) return;
    setImprovedBusy(true);
    setImprovedErr(null);
    try {
      const okSession = user
        ? await ensureSession(user.email, getCachedPassword() ?? '')
        : false;
      if (!okSession) {
        setImprovedErr(t('essay_session_needed'));
        setImprovedBusy(false);
        return;
      }
      const r = (await Essays.improve(id)) as {
        ok: boolean;
        content?: string;
        error?: string;
      };
      if (r.ok && r.content) {
        setImproved(r.content);
      } else {
        setImprovedErr(r.error ?? t('essay_improved_error'));
      }
    } catch {
      setImprovedErr(t('essay_improved_error'));
    } finally {
      setImprovedBusy(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id, improved, improvedBusy, user]);

  const toggleImproved = () => {
    const next = !improvedOpen;
    setImprovedOpen(next);
    setCopied(false);
    if (next) void loadImproved();
  };

  const copyImproved = async () => {
    if (!improved) return;
    try {
      await navigator.clipboard.writeText(improved);
      setCopied(true);
    } catch {
      /* clipboard unavailable — user can select manually */
    }
  };

  const sendReview = async () => {
    setReviewBusy(true);
    setReviewErr(null);
    const r = await requestTeacherReview(id, reason.trim());
    setReviewBusy(false);
    if (r.ok) {
      setReviewSent(true);
    } else {
      setReviewErr(t('essay_js_error'));
    }
  };

  if (err) return <p className="error">{err}</p>;
  if (!res) return <p className="muted">{t('loading')}</p>;

  const pending = !isEssayTerminal(res.status);
  const done = isEssayDone(res.status);
  const displayScore = res.final_score ?? res.total_score;

  return (
    <div>
      <h1>{res.topic_title || t('essay_results')}</h1>
      <p>
        <span className={`badge ${done ? 'green' : 'amber'}`}>{res.status}</span>
        {res.final_score !== null && res.final_score !== undefined && (
          <span className="badge green" style={{ marginLeft: 8 }}>
            {t('essay_teacher_done')}
          </span>
        )}
      </p>

      {pending && (
        <div className="card">
          <p>{t('essay_ai_grading_progress')}</p>
          <div className="progress">
            <div style={{ width: '45%' }} />
          </div>
        </div>
      )}

      {res.status === 'pending_teacher' && !reviewSent && (
        <div className="card">
          <p>{t('essay_teacher_reviewing')}</p>
        </div>
      )}

      {reviewSent && (
        <div className="card">
          <strong>{t('essay_review_requested')}</strong>
          <p className="muted small">{t('essay_review_requested_hint')}</p>
        </div>
      )}

      {res.status === 'error' && (
        <div className="card">
          <p className="error">{t('essay_error')}</p>
          <Link className="btn primary sm" to="/essays">
            {t('essay_error_retry')}
          </Link>
        </div>
      )}

      {res.status === 'draft' && (
        <div className="card">
          <p className="muted">{t('essay_status_draft')}</p>
          <Link className="btn primary sm" to="/essays">
            {t('essay_continue_writing')}
          </Link>
        </div>
      )}

      {done && (
        <>
          {res.is_off_topic && <p className="error">{t('off_topic')}</p>}
          <div className="grid">
            <div className="card stat">
              <span className="stat-label">
                {res.final_score !== null && res.final_score !== undefined
                  ? t('essay_final_score')
                  : t('em_overall')}
              </span>
              <span className="stat-value">
                {displayScore ?? '—'}
                <small className="muted"> / {res.max_score}</small>
              </span>
            </div>
            <div className="card stat">
              <span className="stat-label">{t('em_overall')}</span>
              <span className="stat-value">{res.converted_score ?? '—'}</span>
            </div>
            <div className="card stat">
              <span className="stat-label">{t('words')}</span>
              <span className="stat-value">{res.word_count}</span>
            </div>
          </div>
          {res.summary && (
            <div className="card" style={{ marginTop: 16 }}>
              <p>{res.summary}</p>
            </div>
          )}
          <h2>{t('essay_12_criteria')}</h2>
          <div className="grid">
            {res.criteria.map((c) => (
              <div key={c.id} className="card">
                <strong>{c.name}</strong>
                <p className="stat-value">
                  {c.score}
                  <small className="muted"> / {c.max_score ?? 2}</small>
                </p>
                <p className="muted small">{c.reason}</p>
                {!!c.errors?.length && (
                  <ul className="muted small" style={{ marginTop: 4, paddingLeft: 18 }}>
                    {c.errors.map((e, i) => (
                      <li key={i}>“{e}”</li>
                    ))}
                  </ul>
                )}
              </div>
            ))}
          </div>

          <div className="card" style={{ marginTop: 16 }}>
            <button className="btn sm" disabled={improvedBusy} onClick={toggleImproved}>
              {improvedBusy
                ? t('essay_improved_loading')
                : improvedOpen
                  ? t('essay_improved_hide')
                  : t('essay_improved_show')}
            </button>
            {improvedErr && <p className="error">{improvedErr}</p>}
            {improvedOpen && improved && (
              <>
                <p className="muted small">
                  {t('essay_improved_title')} · {countEssayWords(improved)} {t('words_suffix')}
                </p>
                <p style={{ whiteSpace: 'pre-line' }}>{improved}</p>
                <button className="btn sm" onClick={copyImproved}>
                  {copied ? t('essay_improved_copied') : t('essay_improved_copy')}
                </button>
              </>
            )}
          </div>

          {(res.status === 'graded' || res.status === 'ai_evaluated') &&
            res.final_score === null &&
            !reviewSent && (
              <div className="card" style={{ marginTop: 16 }}>
                <strong>{t('essay_ask_teacher')}</strong>
                <div className="form" style={{ maxWidth: '100%' }}>
                  <textarea
                    rows={3}
                    value={reason}
                    onChange={(e) => setReason(e.target.value)}
                    placeholder={t('essay_review_reason_ph')}
                  />
                  <button
                    className="btn primary sm"
                    disabled={reviewBusy}
                    onClick={sendReview}
                  >
                    {reviewBusy ? t('loading') : t('essay_review_send')}
                  </button>
                  {reviewErr && <p className="error">{reviewErr}</p>}
                </div>
              </div>
            )}
        </>
      )}

      <p style={{ marginTop: 16 }}>
        <Link to="/essays">{t('essay_back_topics')}</Link>
      </p>
    </div>
  );
}
