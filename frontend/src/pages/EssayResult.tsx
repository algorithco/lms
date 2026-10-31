import { useCallback, useEffect, useMemo, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { useLang } from '../i18n/LangContext';
import { Essays } from '../lib/api';
import HologramRadar3D from '../components/HologramRadar3D';
import TiltCard from '../components/TiltCard';
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
 * - AI improved version via POST /api/v1/essays/<id>/improve/ (JWT)
 * - teacher-review request via POST /api/v1/essays/<id>/request-review/ (JWT)
 */

interface SpellingError {
  word: string;
  correction: string;
  explanation: string;
}

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
  /** Provenance of this student's own grade (never another account's data). */
  grading_source?: 'ai' | 'cache' | 'mock' | string;
  cached?: boolean;
  total_score: number | null;
  max_score: number;
  converted_score: number | null;
  score_percentage?: number;
  final_score: number | null;
  summary: string;
  word_count: number;
  is_off_topic: boolean;
  is_completely_off_topic?: boolean;
  topic_status?: 'on_topic' | 'partially_off_topic' | 'completely_off_topic' | string;
  topic_match_reason?: string;
  topic_title: string;
  topic_id?: number | null;
  essay_text?: string;
  can_retry?: boolean;
  criteria: Criterion[];
  spelling_errors?: SpellingError[];
  strengths?: string[];
  weaknesses?: string[];
  teacher_recommendation?: string;
  improved_text?: string;
  graded_at?: string | null;
  poll_after?: number;
  error?: string | null;
  subject?: string;
  rubric_type?: string;
  overall_band?: number | null;
  cefr_level?: string | null;
}

function renderHighlightedText(text?: string, errors?: SpellingError[]) {
  if (!text) return '(Asl matn topilmadi)';
  if (!errors || !errors.length) return text;
  const words = errors.map((e) => e.word.trim()).filter((w) => w.length > 0);
  if (!words.length) return text;
  try {
    const escaped = words.map((w) => w.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('|');
    const regex = new RegExp(`(${escaped})`, 'gi');
    const parts = text.split(regex);
    return parts.map((part, i) => {
      const match = errors.find((e) => e.word.toLowerCase() === part.toLowerCase());
      if (match) {
        return (
          <mark
            key={i}
            style={{
              background: 'rgba(239, 68, 68, 0.25)',
              color: '#ef4444',
              padding: '1px 4px',
              borderRadius: '4px',
              fontWeight: 600,
              borderBottom: '2px solid #ef4444',
            }}
            title={`${match.word} ➔ ${match.correction} (${match.explanation})`}
          >
            {part}
          </mark>
        );
      }
      return part;
    });
  } catch {
    return text;
  }
}

function getBmbGrade(totalScore: number | null, maxScore: number): { grade: string; color: string; bg: string } | null {
  if (totalScore === null || totalScore === undefined) return null;
  const score60 = Math.round((totalScore / maxScore) * 60);
  if (score60 >= 54) return { grade: 'A+', color: '#10b981', bg: 'rgba(16, 185, 129, 0.12)' };
  if (score60 >= 48) return { grade: 'A', color: '#10b981', bg: 'rgba(16, 185, 129, 0.10)' };
  if (score60 >= 42) return { grade: 'B+', color: '#3b82f6', bg: 'rgba(59, 130, 246, 0.12)' };
  if (score60 >= 36) return { grade: 'B', color: '#3b82f6', bg: 'rgba(59, 130, 246, 0.10)' };
  if (score60 >= 30) return { grade: 'C+', color: '#f59e0b', bg: 'rgba(245, 158, 11, 0.12)' };
  if (score60 >= 24) return { grade: 'C', color: '#f59e0b', bg: 'rgba(245, 158, 11, 0.10)' };
  return { grade: 'F', color: '#ef4444', bg: 'rgba(239, 68, 68, 0.10)' };
}

export default function EssayResult() {
  const { id = '' } = useParams();
  const { t } = useLang();
  const [res, setRes] = useState<Result | null>(null);
  const [err, setErr] = useState<string | null>(null);

  // Improved version (session improve endpoint).
  const [improvedOpen, setImprovedOpen] = useState(false);
  const [improved, setImproved] = useState<string | null>(null);
  const [improvedBusy, setImprovedBusy] = useState(false);
  const [improvedErr, setImprovedErr] = useState<string | null>(null);
  const [improvedView, setImprovedView] = useState<'diff' | 'after' | 'before'>('diff');
  const [copied, setCopied] = useState(false);

  // Teacher-review request (session form endpoint).
  const [reason, setReason] = useState('');
  const [reviewBusy, setReviewBusy] = useState(false);
  const [reviewSent, setReviewSent] = useState(false);
  const [reviewErr, setReviewErr] = useState<string | null>(null);

  // One-click retry for failed grading (status=error).
  const [retryBusy, setRetryBusy] = useState(false);
  const [retryErr, setRetryErr] = useState<string | null>(null);
  const [pollNonce, setPollNonce] = useState(0);
  const [selectedCritId, setSelectedCritId] = useState<number>(1);

  // Grammarly-style Interactive Inline Reviewer
  const [workingEssayText, setWorkingEssayText] = useState<string>('');
  const [activeError, setActiveError] = useState<SpellingError | null>(null);
  const [fixedErrors, setFixedErrors] = useState<Record<string, string>>({});
  const [copiedWorkingText, setCopiedWorkingText] = useState(false);

  useEffect(() => {
    if (res?.essay_text && !workingEssayText) {
      setWorkingEssayText(res.essay_text);
    }
  }, [res?.essay_text, workingEssayText]);

  const handleReplaceError = (errToFix: SpellingError) => {
    const current = workingEssayText || res?.essay_text || '';
    if (!current) return;
    try {
      const escaped = errToFix.word.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
      const regex = new RegExp(`\\b${escaped}\\b`, 'gi');
      const updated = current.replace(regex, errToFix.correction);
      setWorkingEssayText(updated);
      setFixedErrors((prev) => ({ ...prev, [errToFix.word.toLowerCase()]: errToFix.correction }));
      setActiveError(null);
    } catch {
      const updated = current.split(errToFix.word).join(errToFix.correction);
      setWorkingEssayText(updated);
      setFixedErrors((prev) => ({ ...prev, [errToFix.word.toLowerCase()]: errToFix.correction }));
      setActiveError(null);
    }
  };

  const handleFixAllErrors = () => {
    if (!res?.spelling_errors?.length) return;
    let txt = workingEssayText || res.essay_text || '';
    if (!txt) return;
    const nextFixed = { ...fixedErrors };
    for (const errItem of res.spelling_errors) {
      try {
        const escaped = errItem.word.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
        const regex = new RegExp(`\\b${escaped}\\b`, 'gi');
        txt = txt.replace(regex, errItem.correction);
        nextFixed[errItem.word.toLowerCase()] = errItem.correction;
      } catch {
        txt = txt.split(errItem.word).join(errItem.correction);
        nextFixed[errItem.word.toLowerCase()] = errItem.correction;
      }
    }
    setWorkingEssayText(txt);
    setFixedErrors(nextFixed);
    setActiveError(null);
  };

  const renderInlineGrammarlyText = (text: string, errors: SpellingError[]) => {
    if (!text) return <span className="muted">(Asl matn topilmadi)</span>;
    if (!errors || !errors.length) return <span>{text}</span>;

    const activeList = errors.filter((e) => !fixedErrors[e.word.toLowerCase()]);
    if (!activeList.length) {
      return <span>{text}</span>;
    }

    try {
      const words = activeList.map((e) => e.word.trim()).filter((w) => w.length > 0);
      const sorted = [...words].sort((a, b) => b.length - a.length);
      const escaped = sorted.map((w) => w.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('|');
      const regex = new RegExp(`(${escaped})`, 'gi');
      const parts = text.split(regex);

      return parts.map((part, i) => {
        const match = activeList.find((e) => e.word.toLowerCase() === part.toLowerCase());
        if (match) {
          const isSelected = activeError?.word.toLowerCase() === match.word.toLowerCase();
          return (
            <span
              key={i}
              onClick={() => setActiveError(match)}
              style={{
                textDecoration: 'underline wavy #ef4444',
                textUnderlineOffset: '4px',
                fontWeight: 600,
                color: isSelected ? '#f87171' : '#ef4444',
                background: isSelected ? 'rgba(239, 68, 68, 0.25)' : 'rgba(239, 68, 68, 0.08)',
                padding: '1px 4px',
                borderRadius: '4px',
                cursor: 'pointer',
                transition: 'all 0.15s ease',
              }}
              title={`❌ ${match.word} ➔ ✅ ${match.correction} (${match.explanation}) — Bosib almashtirish`}
            >
              {part}
            </span>
          );
        }
        return part;
      });
    } catch {
      return <span>{text}</span>;
    }
  };

  const radarItems = useMemo(() => {
    if (!res?.criteria || !res.criteria.length) return [];
    return res.criteria.map((c) => {
      const max = c.max_score || 2;
      return {
        id: c.id,
        name: c.name,
        score: `${c.score} / ${max}`,
        percent: Math.min(Math.round((c.score / max) * 100), 100),
      };
    });
  }, [res?.criteria]);

  useEffect(() => {
    let stop = false;
    let timer: ReturnType<typeof setTimeout>;
    const poll = async () => {
      try {
        const r = (await Essays.result(id)) as unknown as Result;
        if (stop) return;
        setRes({ ...r, criteria: r.criteria ?? [] });
        if (r.improved_text) {
          setImproved(r.improved_text);
        }
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
  }, [id, pollNonce]);

  const loadImproved = useCallback(async () => {
    if (improved !== null || improvedBusy) return;
    setImprovedBusy(true);
    setImprovedErr(null);
    try {
      const r = await Essays.improve(id);
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
  }, [id, improved, improvedBusy, t]);

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
    try {
      const r = await requestTeacherReview(id, reason.trim());
      if (r.ok) {
        setReviewSent(true);
      } else {
        setReviewErr(t('essay_js_error'));
      }
    } catch {
      setReviewErr(t('essay_js_error'));
    } finally {
      setReviewBusy(false);
    }
  };

  const retryGrading = async () => {
    if (!res || retryBusy) return;
    setRetryBusy(true);
    setRetryErr(null);
    try {
      const text = (res.essay_text ?? '').trim();
      if (!text) {
        setRetryErr(t('essay_js_error'));
        setRetryBusy(false);
        return;
      }
      await Essays.submit(id, text);
      // Backend re-queues grading (ERROR without result → PENDING).
      // Switch to polling UI immediately and restart the poll loop.
      setRes({ ...res, status: 'pending' });
      setPollNonce((n) => n + 1);
    } catch (e) {
      setRetryErr(e instanceof Error ? e.message : t('essay_js_error'));
    } finally {
      setRetryBusy(false);
    }
  };

  if (err) return <p className="error">{err}</p>;
  if (!res) return <p className="muted">{t('loading')}</p>;

  const pending = !isEssayTerminal(res.status);
  const done = isEssayDone(res.status);
  const displayScore = res.final_score ?? res.total_score;
  const isEnglish =
    res.subject === 'english' ||
    res.rubric_type?.startsWith('ielts') ||
    (res.overall_band !== null && res.overall_band !== undefined);

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

      {pending && res.status !== 'draft' && (
        <div className="card">
          <p>{t('essay_grading_pending')}</p>
          <div className="progress">
            <div style={{ width: '45%' }} />
          </div>
        </div>
      )}

      {res.status === 'pending_teacher' && !reviewSent && (
        <div className="card">
          <strong>{t('essay_grading_recheck')}</strong>
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
          <strong className="error">{t('essay_grading_failed')}</strong>
          <p className="error">{t('essay_error')}</p>
          {res.error && <p className="muted">{res.error}</p>}
          {retryErr && <p className="error">{retryErr}</p>}
          <div className="toolbar">
            <button
              className="btn primary sm"
              disabled={retryBusy || !(res.essay_text ?? '').trim()}
              onClick={retryGrading}
            >
              {retryBusy ? t('loading') : t('essay_error_retry')}
            </button>
            {res.topic_id ? (
              <Link className="btn sm" to={`/essays/write/${res.topic_id}`}>
                {t('essay_continue_writing')}
              </Link>
            ) : (
              <Link className="btn sm" to="/essays">
                {t('essay_back_topics')}
              </Link>
            )}
          </div>
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
          {(res.is_completely_off_topic || res.topic_status === 'completely_off_topic') ? (
            <div
              className="card error-card"
              style={{
                marginBottom: 20,
                border: '1px solid rgba(239, 68, 68, 0.4)',
                background: 'rgba(239, 68, 68, 0.08)',
                padding: '16px 20px',
                borderRadius: '12px',
              }}
            >
              <h4 style={{ color: '#ef4444', margin: '0 0 8px', display: 'flex', alignItems: 'center', gap: 8 }}>
                <span>⛔</span> DIQQAT: Mavzuga mutlaqo mos emas (0 ball)
              </h4>
              <p style={{ margin: 0, color: 'var(--text-color, #e2e8f0)', fontSize: '0.95rem', lineHeight: 1.5 }}>
                Taqdim etilgan esse berilgan mavzuga mutlaqo mos kelmaydi (Off-topic). Mavzudan butunlay chetlashilganligi sababli barcha mezonlar bo'yicha 0 ball qo'yildi.
              </p>
            </div>
          ) : (res.is_off_topic || res.topic_status === 'partially_off_topic') ? (
            <div
              className="card warning-card"
              style={{
                marginBottom: 20,
                border: '1px solid rgba(245, 158, 11, 0.4)',
                background: 'rgba(245, 158, 11, 0.08)',
                padding: '16px 20px',
                borderRadius: '12px',
              }}
            >
              <h4 style={{ color: '#f59e0b', margin: '0 0 8px', display: 'flex', alignItems: 'center', gap: 8 }}>
                <span>⚠️</span> OGOHLANTIRISH: Mavzudan jiddiy chetlanish
              </h4>
              <p style={{ margin: 0, color: 'var(--text-color, #e2e8f0)', fontSize: '0.95rem', lineHeight: 1.5 }}>
                Esseda mavzudan jiddiy chetlanish kuzatildi. Asosiy savolga to'liq javob berilmaganligi sababli baho 2 – 35 ball oralig'iga keskin tushirildi.
              </p>
            </div>
          ) : null}
          {!isEnglish && (() => {
            const bmbGrade = getBmbGrade(displayScore, res.max_score);
            const score60 = displayScore !== null ? Math.round((displayScore / res.max_score) * 60) : null;
            return bmbGrade ? (
              <div style={{
                display: 'flex',
                alignItems: 'center',
                gap: 16,
                padding: '16px 20px',
                background: bmbGrade.bg,
                border: `2px solid ${bmbGrade.color}`,
                borderRadius: 16,
                marginBottom: 20,
              }}>
                <div style={{
                  fontSize: '3.5rem',
                  fontWeight: 900,
                  color: bmbGrade.color,
                  lineHeight: 1,
                  minWidth: 80,
                  textAlign: 'center',
                }}>
                  {bmbGrade.grade}
                </div>
                <div>
                  <div style={{ fontSize: '1.1rem', fontWeight: 700, color: 'var(--text, #f3f4f6)' }}>
                    🏆 BMB Rasmiy Baho
                  </div>
                  <div style={{ fontSize: '0.9rem', color: 'var(--muted, #9ca3af)', marginTop: 4 }}>
                    {score60 !== null ? `${score60} / 60 ball` : ''} · 12 mezon bo’yicha baholandi
                  </div>
                  <div style={{ fontSize: '0.8rem', color: bmbGrade.color, fontWeight: 600, marginTop: 4 }}>
                    {bmbGrade.grade === 'A+' ? '⭐ Ajoyib! Eng yuqori daraja' :
                     bmbGrade.grade === 'A' ? "🎉 A'lo! Yuqori daraja" :
                     bmbGrade.grade === 'B+' ? "✅ Yaxshi+! Yuqori o'rta" :
                     bmbGrade.grade === 'B' ? "✅ Yaxshi! O'rta daraja" :
                     bmbGrade.grade === 'C+' ? '⚠️ Qoniqarli+! Rivojlanish kerak' :
                     bmbGrade.grade === 'C' ? "⚠️ Qoniqarli. Ko'proq mashq qiling" :
                     '❌ Qoniqarsiz. Qayta yozish tavsiya etiladi'}
                  </div>
                </div>
              </div>
            ) : null;
          })()}
          <h2>{t('essay_grading_graded')}</h2>
          {res.cached && (
            <p className="muted small">{t('essay_grading_cached')}</p>
          )}
          {res.grading_source === 'mock' && (
            <p className="muted small">{t('essay_grading_mock')}</p>
          )}
          <div className="grid">
            {isEnglish ? (
              <>
                <div
                  className="card stat"
                  style={{
                    borderColor: 'rgba(245, 158, 11, 0.45)',
                    background: 'linear-gradient(135deg, rgba(245, 158, 11, 0.08), rgba(16, 185, 129, 0.08))',
                  }}
                >
                  <span className="stat-label">🏆 IELTS Overall Band Score</span>
                  <span className="stat-value" style={{ color: '#f59e0b', fontSize: '2rem' }}>
                    {res.overall_band !== null && res.overall_band !== undefined
                      ? Number(res.overall_band).toFixed(1)
                      : displayScore !== null
                      ? Number(displayScore).toFixed(1)
                      : '—'}
                    <small className="muted" style={{ fontSize: '1rem' }}> / 9.0</small>
                  </span>
                </div>
                <div className="card stat">
                  <span className="stat-label">🎓 CEFR Equivalency</span>
                  <span className="stat-value" style={{ color: '#10b981' }}>
                    {res.cefr_level || (displayScore && displayScore >= 7 ? 'C1' : 'B2')}
                  </span>
                </div>
                <div className="card stat">
                  <span className="stat-label">{t('words')}</span>
                  <span className="stat-value">{res.word_count}</span>
                </div>
              </>
            ) : (
              <>
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
              </>
            )}
          </div>
          {res.summary && (
            <div className="card" style={{ marginTop: 16 }}>
              <p>{res.summary}</p>
            </div>
          )}
          <h2>{isEnglish ? '🇬🇧 Official IELTS 4 Criteria (Band 1.0 – 9.0)' : t('essay_12_criteria')}</h2>
          {radarItems.length > 0 && (
            <div style={{ display: 'flex', justifyContent: 'center', margin: '20px 0 28px' }}>
              <HologramRadar3D
                items={radarItems}
                activeId={selectedCritId}
                size={270}
              />
            </div>
          )}
          <div className="grid">
            {res.criteria.map((c) => (
              <TiltCard
                key={c.id}
                glare
                maxTilt={6}
                scale={1.02}
                style={{ borderRadius: 'var(--radius)', height: '100%' }}
              >
                <div
                  className="card"
                  style={{
                    height: '100%',
                    margin: 0,
                    cursor: 'pointer',
                    borderColor: selectedCritId === c.id ? '#f59e0b' : undefined,
                    boxShadow: selectedCritId === c.id ? '0 0 16px rgba(245, 158, 11, 0.25)' : undefined,
                    transition: 'all 0.2s ease',
                  }}
                  onClick={() => setSelectedCritId(c.id)}
                  onMouseEnter={() => setSelectedCritId(c.id)}
                >
                  <strong>{c.name}</strong>
                  <p className="stat-value" style={{ margin: '6px 0 2px' }}>
                    {c.score}
                    <small className="muted"> / {c.max_score ?? 2}</small>
                  </p>
                  {/* Progress bar */}
                  <div style={{ height: 6, background: 'rgba(255,255,255,0.08)', borderRadius: 3, overflow: 'hidden', margin: '4px 0 8px' }}>
                    <div
                      style={{
                        height: '100%',
                        width: `${Math.min(100, Math.round((c.score / (c.max_score || 2)) * 100))}%`,
                        background: c.score >= (c.max_score || 2) ? '#10b981' : c.score >= (c.max_score || 2) * 0.7 ? '#f59e0b' : '#ef4444',
                        borderRadius: 3,
                        transition: 'width 0.4s ease',
                      }}
                    />
                  </div>
                  <p className="muted small">{c.reason}</p>
                  {!!c.errors?.length && (
                    <ul className="muted small" style={{ marginTop: 4, paddingLeft: 18 }}>
                      {c.errors.map((e, i) => (
                        <li key={i}>“{e}”</li>
                      ))}
                    </ul>
                  )}
                </div>
              </TiltCard>
            ))}
          </div>

          {/* Strengths, Weaknesses, and Teacher Recommendation */}
          {(!!res.strengths?.length || !!res.weaknesses?.length || !!res.teacher_recommendation) && (
            <div className="grid" style={{ marginTop: 20 }}>
              {!!res.strengths?.length && (
                <div className="card" style={{ borderLeft: '4px solid #10b981' }}>
                  <h4 style={{ color: '#10b981', margin: '0 0 8px', display: 'flex', alignItems: 'center', gap: 6 }}>
                    <span>💪</span> Kuchli tomonlari
                  </h4>
                  <ul className="muted small" style={{ margin: 0, paddingLeft: 18 }}>
                    {res.strengths.map((s, i) => (
                      <li key={i} style={{ marginBottom: 4 }}>{s}</li>
                    ))}
                  </ul>
                </div>
              )}
              {!!res.weaknesses?.length && (
                <div className="card" style={{ borderLeft: '4px solid #f59e0b' }}>
                  <h4 style={{ color: '#f59e0b', margin: '0 0 8px', display: 'flex', alignItems: 'center', gap: 6 }}>
                    <span>⚠️</span> E'tibor qaratish kerak
                  </h4>
                  <ul className="muted small" style={{ margin: 0, paddingLeft: 18 }}>
                    {res.weaknesses.map((w, i) => (
                      <li key={i} style={{ marginBottom: 4 }}>{w}</li>
                    ))}
                  </ul>
                </div>
              )}
              {!!res.teacher_recommendation && (
                <div className="card" style={{ borderLeft: '4px solid #3b82f6', gridColumn: '1 / -1' }}>
                  <h4 style={{ color: '#3b82f6', margin: '0 0 8px', display: 'flex', alignItems: 'center', gap: 6 }}>
                    <span>💡</span> Ustoz / AI Tavsiyasi
                  </h4>
                  <p className="small" style={{ margin: 0, color: 'var(--text, #f3f4f6)', lineHeight: 1.6 }}>
                    {res.teacher_recommendation}
                  </p>
                </div>
              )}
            </div>
          )}

          {/* 📝 Yozilgan Esse va Interaktiv Grammatika Tahrirchisi (Grammarly rejimida) */}
          {(res.essay_text || !!res.spelling_errors?.length) && (
            <div
              className="card"
              style={{
                marginTop: 20,
                border: '1px solid rgba(239, 68, 68, 0.35)',
                background: 'linear-gradient(180deg, rgba(239, 68, 68, 0.04) 0%, rgba(16, 185, 129, 0.02) 100%)',
                borderRadius: 14,
                padding: 20,
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 12, marginBottom: 14 }}>
                <div>
                  <h3 style={{ margin: 0, display: 'flex', alignItems: 'center', gap: 8, fontSize: '1.15rem' }}>
                    <span>✍️</span> Yozilgan Esse va Interaktiv Grammatika Tahrirchisi
                  </h3>
                  <p className="muted small" style={{ margin: '4px 0 0' }}>
                    Grammarly rejimida to&apos;g&apos;ridan-to&apos;g&apos;ri matn ustida to&apos;lqinsimon qizil chiziqli xatoni bosib tuzatish mumkin
                  </p>
                </div>

                <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                  {!!res.spelling_errors?.length && Object.keys(fixedErrors).length < res.spelling_errors.length && (
                    <button
                      type="button"
                      className="btn sm"
                      onClick={handleFixAllErrors}
                      style={{
                        background: 'rgba(16, 185, 129, 0.15)',
                        borderColor: '#10b981',
                        color: '#10b981',
                        fontWeight: 700,
                        fontSize: '0.8rem',
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: 6,
                      }}
                      title="Barcha aniqlangan xatolarni bir zumda to'g'ri shakliga almashtirish"
                    >
                      <span>⚡</span> Barchasini to&apos;g&apos;rilash ({res.spelling_errors.length - Object.keys(fixedErrors).length} ta)
                    </button>
                  )}

                  <button
                    type="button"
                    className="btn sm ghost"
                    onClick={() => {
                      navigator.clipboard.writeText(workingEssayText || res.essay_text || '');
                      setCopiedWorkingText(true);
                      setTimeout(() => setCopiedWorkingText(false), 2000);
                    }}
                    style={{ fontSize: '0.8rem' }}
                  >
                    {copiedWorkingText ? '✓ Nusxalandi' : '📋 Matnni nusxalash'}
                  </button>
                </div>
              </div>

              {/* Interactive Grammarly Error Popover / Inspector */}
              {activeError && (
                <div
                  style={{
                    marginBottom: 16,
                    padding: 14,
                    borderRadius: 10,
                    background: 'rgba(24, 24, 27, 0.95)',
                    border: '1.5px solid #ef4444',
                    boxShadow: '0 8px 24px rgba(239, 68, 68, 0.25)',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: 10,
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <span style={{ fontSize: '0.85rem', fontWeight: 700, color: '#f87171', display: 'flex', alignItems: 'center', gap: 6 }}>
                      <span>💡</span> Grammatika &amp; Imlo Tavsiyasi
                    </span>
                    <button
                      type="button"
                      className="btn sm ghost"
                      onClick={() => setActiveError(null)}
                      style={{ padding: '2px 8px', fontSize: '0.78rem' }}
                    >
                      ✕
                    </button>
                  </div>

                  <div style={{ display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
                    <div>
                      <span style={{ fontSize: '0.78rem', color: 'var(--muted)', display: 'block' }}>Matndagi xato:</span>
                      <span style={{ fontSize: '1rem', fontWeight: 700, color: '#ef4444', textDecoration: 'line-through' }}>
                        {activeError.word}
                      </span>
                    </div>
                    <span style={{ color: 'var(--muted)' }}>➔</span>
                    <div>
                      <span style={{ fontSize: '0.78rem', color: 'var(--muted)', display: 'block' }}>Tavsiya etilgan to&apos;g&apos;ri shakl:</span>
                      <span style={{ fontSize: '1.05rem', fontWeight: 800, color: '#10b981' }}>
                        {activeError.correction}
                      </span>
                    </div>
                  </div>

                  {activeError.explanation && (
                    <p style={{ margin: 0, fontSize: '0.84rem', color: 'var(--ink)', lineHeight: 1.5 }}>
                      <strong>Izoh:</strong> {activeError.explanation}
                    </p>
                  )}

                  <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end', marginTop: 4 }}>
                    <button
                      type="button"
                      className="btn sm ghost"
                      onClick={() => setActiveError(null)}
                      style={{ fontSize: '0.8rem' }}
                    >
                      Yopish
                    </button>
                    <button
                      type="button"
                      className="btn sm primary"
                      onClick={() => handleReplaceError(activeError)}
                      style={{
                        background: '#10b981',
                        borderColor: '#10b981',
                        color: '#ffffff',
                        fontWeight: 700,
                        fontSize: '0.82rem',
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: 6,
                      }}
                    >
                      <span>🪄</span> Matnda almashtirish
                    </button>
                  </div>
                </div>
              )}

              {/* The Essay Text with Wave Underlines */}
              <div
                style={{
                  whiteSpace: 'pre-line',
                  lineHeight: 1.85,
                  fontSize: '0.98rem',
                  color: 'var(--ink)',
                  background: 'rgba(0, 0, 0, 0.15)',
                  padding: '16px 18px',
                  borderRadius: 10,
                  border: '1px solid rgba(255, 255, 255, 0.06)',
                }}
              >
                {renderInlineGrammarlyText(workingEssayText || res.essay_text || '', res.spelling_errors || [])}
              </div>

              {/* Status footer */}
              <div style={{ marginTop: 12, display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 8 }}>
                <span className="muted small">
                  {res.word_count || countEssayWords(workingEssayText || res.essay_text || '')} ta so&apos;z
                </span>
                {Object.keys(fixedErrors).length > 0 && (
                  <span style={{ fontSize: '0.8rem', color: '#10b981', fontWeight: 600 }}>
                    ✓ {Object.keys(fixedErrors).length} ta xato muvaffaqiyatli almashtirildi
                  </span>
                )}
              </div>
            </div>
          )}

          {/* Spelling Errors Table/List */}
          {!!res.spelling_errors?.length && (
            <div
              className="card"
              style={{
                marginTop: 20,
                border: '1px solid rgba(239, 68, 68, 0.3)',
                background: 'rgba(239, 68, 68, 0.02)',
              }}
            >
              <h3 style={{ margin: '0 0 12px', color: '#ef4444', display: 'flex', alignItems: 'center', gap: 8, fontSize: '1.05rem' }}>
                <span>✍️</span> Aniqlangan imlo va grammatika xatoliklari ({res.spelling_errors.length} ta)
              </h3>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: 10 }}>
                {res.spelling_errors.map((err, idx) => {
                  const isFixed = Boolean(fixedErrors[err.word.toLowerCase()]);
                  return (
                    <div
                      key={idx}
                      onClick={() => !isFixed && setActiveError(err)}
                      style={{
                        padding: '10px 14px',
                        background: isFixed ? 'rgba(16, 185, 129, 0.05)' : 'rgba(239, 68, 68, 0.05)',
                        borderRadius: 8,
                        border: isFixed ? '1px solid rgba(16, 185, 129, 0.3)' : '1px solid rgba(239, 68, 68, 0.2)',
                        cursor: isFixed ? 'default' : 'pointer',
                        transition: 'all 0.15s ease',
                      }}
                      title={isFixed ? "To'g'rilandi" : "Bosib matnda almashtirish"}
                    >
                      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 4 }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                          <span style={{ textDecoration: 'line-through', color: '#ef4444', fontWeight: 600 }}>{err.word}</span>
                          <span style={{ color: 'var(--text-muted, #9ca3af)' }}>➔</span>
                          <span style={{ color: '#10b981', fontWeight: 700 }}>{err.correction}</span>
                        </div>
                        {isFixed ? (
                          <span style={{ fontSize: '0.75rem', color: '#10b981', fontWeight: 700 }}>✓ To&apos;g&apos;rilandi</span>
                        ) : (
                          <span style={{ fontSize: '0.72rem', color: '#f59e0b', fontWeight: 600 }}>🪄 Tuzatish</span>
                        )}
                      </div>
                      {err.explanation && (
                        <p className="muted small" style={{ margin: 0, fontSize: '0.8rem' }}>{err.explanation}</p>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* 🪄 AI tahriri (Oldin / Keyin) - Interactive Redactor */}
          <div
            className="card"
            style={{
              marginTop: 20,
              background: 'linear-gradient(135deg, rgba(245, 158, 11, 0.05) 0%, rgba(16, 185, 129, 0.05) 100%)',
              border: '1px solid rgba(245, 158, 11, 0.25)',
              borderRadius: '14px',
              padding: '20px',
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 12 }}>
              <div>
                <h3 style={{ margin: 0, display: 'flex', alignItems: 'center', gap: 8 }}>
                  <span>🪄</span> AI tahriri (Oldin / Keyin)
                </h3>
                <p className="muted small" style={{ margin: '4px 0 0' }}>
                  12 mezon talablari asosida tuzatilgan mukammal namuna matn
                </p>
              </div>
              <button
                type="button"
                className="btn sm"
                disabled={improvedBusy}
                onClick={toggleImproved}
                style={{
                  borderColor: '#f59e0b',
                  color: '#f59e0b',
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: 6,
                }}
              >
                <span>{improvedOpen ? '✕ Yopish' : '✨ AI Tahririni ochish'}</span>
              </button>
            </div>

            {improvedBusy && (
              <p className="muted small" style={{ marginTop: 14 }}>
                🤖 AI matningizni tahrirlamoqda va uslubiy xatolarni tuzatmoqda…
              </p>
            )}
            {improvedErr && <p className="error small" style={{ marginTop: 14 }}>{improvedErr}</p>}

            {improvedOpen && improved && (
              <div style={{ marginTop: 18 }}>
                {/* View Mode Switcher */}
                <div style={{ display: 'flex', gap: 8, marginBottom: 14, flexWrap: 'wrap' }}>
                  <button
                    type="button"
                    className={`btn sm ${improvedView === 'diff' ? 'primary' : 'ghost'}`}
                    onClick={() => setImprovedView('diff')}
                  >
                    🔄 Solishtirish (Oldin / Keyin)
                  </button>
                  <button
                    type="button"
                    className={`btn sm ${improvedView === 'after' ? 'primary' : 'ghost'}`}
                    onClick={() => setImprovedView('after')}
                  >
                    ✨ Faqat AI tahriri
                  </button>
                  <button
                    type="button"
                    className={`btn sm ${improvedView === 'before' ? 'primary' : 'ghost'}`}
                    onClick={() => setImprovedView('before')}
                  >
                    📝 Asl esse matni
                  </button>
                </div>

                {/* Diff: Side-by-side comparison */}
                {improvedView === 'diff' && (
                  <div
                    style={{
                      display: 'grid',
                      gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))',
                      gap: 16,
                    }}
                  >
                    <div
                      style={{
                        background: 'rgba(239, 68, 68, 0.03)',
                        border: '1px solid rgba(239, 68, 68, 0.2)',
                        borderRadius: '10px',
                        padding: '14px',
                      }}
                    >
                      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
                        <strong style={{ color: '#ef4444', fontSize: '0.9rem' }}>
                          📝 Oldin (Siz yozgan asl matn):
                        </strong>
                        <span className="muted small">{res.word_count} so‘z</span>
                      </div>
                      <div
                        style={{
                          whiteSpace: 'pre-line',
                          fontSize: '0.88rem',
                          lineHeight: 1.6,
                          maxHeight: '400px',
                          overflowY: 'auto',
                          color: 'var(--text-muted, #9ca3af)',
                        }}
                      >
                        {renderHighlightedText(res.essay_text, res.spelling_errors)}
                      </div>
                    </div>

                    <div
                      style={{
                        background: 'rgba(16, 185, 129, 0.04)',
                        border: '1px solid rgba(16, 185, 129, 0.25)',
                        borderRadius: '10px',
                        padding: '14px',
                      }}
                    >
                      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8, alignItems: 'center' }}>
                        <strong style={{ color: '#10b981', fontSize: '0.9rem' }}>
                          ✨ Keyin (AI tuzatgan namuna):
                        </strong>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                          <span className="muted small">{countEssayWords(improved)} so‘z</span>
                          <button type="button" className="btn sm ghost" onClick={copyImproved} style={{ padding: '2px 8px', fontSize: '0.78rem' }}>
                            {copied ? '✓ Nusxalandi' : '📋 Nusxa'}
                          </button>
                        </div>
                      </div>
                      <div
                        style={{
                          whiteSpace: 'pre-line',
                          fontSize: '0.88rem',
                          lineHeight: 1.6,
                          maxHeight: '400px',
                          overflowY: 'auto',
                          color: 'var(--text, #f3f4f6)',
                        }}
                      >
                        {improved}
                      </div>
                    </div>
                  </div>
                )}

                {/* View only After */}
                {improvedView === 'after' && (
                  <div
                    style={{
                      background: 'rgba(16, 185, 129, 0.04)',
                      border: '1px solid rgba(16, 185, 129, 0.25)',
                      borderRadius: '10px',
                      padding: '16px',
                    }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 10, alignItems: 'center' }}>
                      <span className="muted small">
                        {countEssayWords(improved)} {t('words_suffix')} · AI tomonidan mukammallashtirildi
                      </span>
                      <button type="button" className="btn sm" onClick={copyImproved}>
                        {copied ? '✓ Nusxalandi' : '📋 Matnni nusxalash'}
                      </button>
                    </div>
                    <p style={{ whiteSpace: 'pre-line', fontSize: '0.92rem', lineHeight: 1.7, margin: 0 }}>
                      {improved}
                    </p>
                  </div>
                )}

                {/* View only Before */}
                {improvedView === 'before' && (
                  <div
                    style={{
                      background: 'rgba(255, 255, 255, 0.02)',
                      border: '1px solid rgba(255, 255, 255, 0.08)',
                      borderRadius: '10px',
                      padding: '16px',
                    }}
                  >
                    <p className="muted small" style={{ marginBottom: 10 }}>
                      Asl yozilgan variant · {res.word_count} {t('words_suffix')}
                    </p>
                    <div style={{ whiteSpace: 'pre-line', fontSize: '0.92rem', lineHeight: 1.7, margin: 0 }}>
                      {renderHighlightedText(res.essay_text, res.spelling_errors)}
                    </div>
                  </div>
                )}
              </div>
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
        {/* PDF/Print Button */}
        <div style={{ marginTop: 20, textAlign: 'center' }}>
          <button
            type="button"
            className="btn sm"
            onClick={() => window.print()}
            style={{
              background: 'rgba(59, 130, 246, 0.1)',
              borderColor: '#3b82f6',
              color: '#3b82f6',
              display: 'inline-flex',
              alignItems: 'center',
              gap: 8,
              fontWeight: 700,
            }}
          >
            <span>📄</span> Rasmiy BMB Natija Varaqasini (PDF) yuklab olish
          </button>
        </div>
        </>
      )}

      <p style={{ marginTop: 16 }}>
        <Link to="/essays">{t('essay_back_topics')}</Link>
      </p>
    </div>
  );
}
