import { useCallback, useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { useLang } from '../i18n/LangContext';
import {
  AiTutor,
  type QuestionMistakeExplanation,
  type ResultDiagnosticsResponse,
  Results as ResultsApi,
} from '../lib/api';
import {
  formatDuration,
  listResultsPage,
  num,
  type ResultListItem,
} from '../lib/testing';

export function getBmbBadge(grade?: string, pct?: number, t?: (k: string) => string): {
  grade: string;
  color: string;
  desc: string;
  bg: string;
} {
  let g = grade;
  const p = pct ?? 0;
  if (!g) {
    if (p >= 86) g = 'A+';
    else if (p >= 75) g = 'A';
    else if (p >= 68) g = 'B+';
    else if (p >= 60) g = 'B';
    else if (p >= 53) g = 'C+';
    else if (p >= 46) g = 'C';
    else g = 'Fail';
  }
  switch (g) {
    case 'A+':
      return { grade: 'A+', color: '#10b981', desc: t ? t('bmb_grade_ap') : 'Maksimal imtiyoz (86–100%)', bg: 'rgba(16, 185, 129, 0.15)' };
    case 'A':
      return { grade: 'A', color: '#059669', desc: t ? t('bmb_grade_a') : 'Yuqori daraja (75–85%)', bg: 'rgba(5, 150, 105, 0.15)' };
    case 'B+':
      return { grade: 'B+', color: '#0284c7', desc: t ? t('bmb_grade_bp') : 'Yaxshi daraja (68–74%)', bg: 'rgba(2, 132, 199, 0.15)' };
    case 'B':
      return { grade: 'B', color: '#3b82f6', desc: t ? t('bmb_grade_b') : 'Qoniqarli daraja (60–67%)', bg: 'rgba(59, 130, 246, 0.15)' };
    case 'C+':
      return { grade: 'C+', color: '#f59e0b', desc: t ? t('bmb_grade_cp') : 'O‘rtacha daraja (53–59%)', bg: 'rgba(245, 158, 11, 0.15)' };
    case 'C':
      return { grade: 'C', color: '#d97706', desc: t ? t('bmb_grade_c') : 'Cheklangan daraja (46–52%)', bg: 'rgba(217, 119, 6, 0.15)' };
    default:
      return { grade: 'Fail', color: '#ef4444', desc: t ? t('bmb_grade_fail') : 'Sertifikat berilmaydi (<46%)', bg: 'rgba(239, 68, 68, 0.15)' };
  }
}

interface QuestionDetail {
  question_id: number;
  question_text: string;
  question_type: string;
  points: number;
  correct_choices: { id: number; text: string }[];
  selected_choices: { id: number; text: string }[];
  correct_text?: string;
  student_answer_text?: string;
  is_correct: boolean | null;
  explanation?: string;
}

interface SectionScoreItem {
  section_code: string;
  section_name: string;
  earned: string | number;
  maximum: string | number;
  weight: string | number;
}

interface ResultDetailData extends ResultListItem {
  bmb_grade?: string;
  total_questions?: number;
  correct_answers?: number;
  wrong_answers?: number;
  unanswered?: number;
  question_details?: QuestionDetail[];
  grading_status?: string;
  certificate_status?: string;
  objective_score?: string | number;
  writing_score?: string | number;
  scoring_version?: string;
  rubric_version?: string;
  section_scores?: SectionScoreItem[];
  certificate_info?: {
    certificate_number: string;
    status: string;
    issued_at?: string;
  } | null;
}

export default function Results() {
  const { t } = useLang();
  // Deep link parity with legacy /results/<id>/: /results/:id preselects it.
  const { id: idParam } = useParams();
  const [results, setResults] = useState<ResultListItem[]>([]);
  const [count, setCount] = useState(0);
  const [page, setPage] = useState(1);
  const [hasNext, setHasNext] = useState(false);
  const [hasPrev, setHasPrev] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [openId, setOpenId] = useState<number | null>(
    idParam && /^\d+$/.test(idParam) ? Number(idParam) : null,
  );
  const [detail, setDetail] = useState<ResultDetailData | null>(null);
  const [detailErr, setDetailErr] = useState<string | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);

  const loadPage = useCallback(
    async (p: number) => {
      setLoading(true);
      setErr(null);
      try {
        const out = await listResultsPage(p);
        setResults((out.results ?? []) as ResultListItem[]);
        setCount(out.count ?? 0);
        setHasNext(Boolean(out.next));
        setHasPrev(Boolean(out.previous));
      } catch (e) {
        setErr(e instanceof Error ? e.message : t('err_retry_js'));
      } finally {
        setLoading(false);
      }
    },
    [t],
  );

  useEffect(() => {
    loadPage(page);
  }, [page, loadPage]);

  const toggleDetail = async (id: number) => {
    if (openId === id) {
      setOpenId(null);
      setDetail(null);
      return;
    }
    setOpenId(id);
    await loadDetail(id);
  };

  const loadDetail = async (id: number) => {
    setDetail(null);
    setDetailErr(null);
    setDetailLoading(true);
    try {
      const d = (await ResultsApi.detail(
        String(id),
      )) as unknown as ResultDetailData;
      setDetail(d);
    } catch (e) {
      setDetailErr(e instanceof Error ? e.message : t('err_retry_js'));
    } finally {
      setDetailLoading(false);
    }
  };

  // Deep-linked /results/:id — fetch its detail on mount.
  useEffect(() => {
    if (openId !== null) void loadDetail(openId);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div>
      <h1>{t('my_results')}</h1>
      <p className="muted">
        <Link to="/certificates">{t('my_certificates')} →</Link>
        {' · '}
        <Link to="/verify/">{t('take_verify_link')} →</Link>
      </p>

      {loading && <p className="muted">{t('loading')}</p>}
      {err && (
        <p className="error">
          {err}{' '}
          <button className="btn sm ghost" onClick={() => loadPage(page)}>
            {t('essay_error_retry')}
          </button>
        </p>
      )}

      {!loading && !err && results.length === 0 && (
        <div className="card">
          <h3>{t('no_results_title')}</h3>
          <p className="muted">{t('no_results_hint')}</p>
          <Link className="btn primary" to="/tests">
            {t('view_tests')}
          </Link>
        </div>
      )}

      <div style={{ display: 'grid', gap: 12 }}>
        {results.map((r) => {
          const pct = num(r.percentage, 0);
          const open = openId === r.id;
          return (
            <div key={r.id} className="card">
              <div
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  gap: 12,
                  alignItems: 'center',
                  flexWrap: 'wrap',
                }}
              >
                <div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                    <strong>{String(r.test_title ?? `Test #${r.test ?? r.id}`)}</strong>
                    {(() => {
                      const bmb = getBmbBadge(r.bmb_grade as string | undefined, pct, t);
                      return (
                        <span
                          style={{
                            padding: '2px 8px',
                            borderRadius: '4px',
                            fontWeight: 700,
                            fontSize: '0.78rem',
                            color: bmb.color,
                            background: bmb.bg,
                            border: `1px solid ${bmb.color}40`,
                          }}
                          title={bmb.desc}
                        >
                          BMB: {bmb.grade}
                        </span>
                      );
                    })()}
                  </div>
                  <p className="muted small">
                    {String(r.course_title ?? '')}
                    {r.calculated_at
                      ? ` · ${new Date(String(r.calculated_at)).toLocaleString()}`
                      : ''}
                  </p>
                </div>
                <div style={{ textAlign: 'right' }}>
                  <p
                    className="stat-value small"
                    style={{ color: r.is_passed ? undefined : 'var(--danger)' }}
                  >
                    {pct}%
                    {r.certificate_status === 'rules_unverified' && (
                      <span className="muted small"> {t('raw_score_not_official')}</span>
                    )}
                  </p>
                  {r.grading_status === 'pending_grading' ? (
                    <span className="badge blue">{t('take_pending_title')}</span>
                  ) : r.certificate_status === 'rules_unverified' ? (
                    <span className="badge blue">{t('raw_score_not_official')}</span>
                  ) : (
                    <span className={`badge ${r.is_passed ? 'green' : 'rose'}`}>
                      {r.is_passed ? t('status_passed') : t('status_failed')}
                    </span>
                  )}
                </div>
              </div>
              <div className="progress" style={{ margin: '8px 0' }}>
                <div style={{ width: `${Math.min(100, Math.max(0, pct))}%` }} />
              </div>
              <div className="toolbar">
                <span className="muted small">
                  {t('score')}: {String(r.score ?? '—')}/{String(r.max_score ?? '—')}
                  {' · '}
                  {t('rd_time_spent')}: {formatDuration(r.time_taken_seconds)}
                </span>
                <button className="btn sm ghost" onClick={() => toggleDetail(r.id)}>
                  {open ? t('take_hide_detail') : t('details')}
                </button>
              </div>

              {open && (
                <div style={{ marginTop: 12 }}>
                  {detailLoading && <p className="muted">{t('loading')}</p>}
                  {detailErr && <p className="error">{detailErr}</p>}
                  {detail && detail.id === r.id && (
                    <ResultDetailBody detail={detail} />
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>

      {(hasNext || hasPrev) && (
        <div className="toolbar" style={{ marginTop: 16 }}>
          <button
            className="btn sm"
            disabled={!hasPrev}
            onClick={() => setPage((p) => Math.max(1, p - 1))}
          >
            ← {t('back')}
          </button>
          <span className="muted small">
            {page} · {t('total_tests')}: {count}
          </span>
          <button
            className="btn sm"
            disabled={!hasNext}
            onClick={() => setPage((p) => p + 1)}
          >
            {t('next')} →
          </button>
        </div>
      )}
    </div>
  );
}

function ResultDetailBody({ detail }: { detail: ResultDetailData }) {
  const { t } = useLang();
  const pct = num(detail.percentage, 0);
  const pending = detail.grading_status === 'pending_grading';
  const unverified = detail.certificate_status === 'rules_unverified';
  const bmb = getBmbBadge(detail.bmb_grade, pct, t);

  // 24/7 AI Tutor Diagnostics
  const [showDiag, setShowDiag] = useState(false);
  const [diagLoading, setDiagLoading] = useState(false);
  const [diagData, setDiagData] = useState<ResultDiagnosticsResponse | null>(null);
  const [diagErr, setDiagErr] = useState<string | null>(null);

  // Interactive Question Mistake Explainer
  const [explainingId, setExplainingId] = useState<number | null>(null);
  const [explanations, setExplanations] = useState<
    Record<number, { data?: QuestionMistakeExplanation; err?: string; open: boolean }>
  >({});

  const toggleDiagnostics = async () => {
    if (showDiag) {
      setShowDiag(false);
      return;
    }
    setShowDiag(true);
    if (!diagData && !diagLoading) {
      setDiagLoading(true);
      setDiagErr(null);
      try {
        const res = await AiTutor.getDiagnostics(detail.id);
        setDiagData(res);
      } catch (e) {
        setDiagErr(e instanceof Error ? e.message : t('err_retry_js'));
      } finally {
        setDiagLoading(false);
      }
    }
  };

  const explainQuestion = async (
    questionId: number,
    selectedChoiceId?: number | null,
  ) => {
    const existing = explanations[questionId];
    if (existing?.open) {
      setExplanations((prev) => ({
        ...prev,
        [questionId]: { ...prev[questionId], open: false },
      }));
      return;
    }
    if (existing?.data) {
      setExplanations((prev) => ({
        ...prev,
        [questionId]: { ...prev[questionId], open: true },
      }));
      return;
    }

    setExplainingId(questionId);
    try {
      const res = await AiTutor.explainMistake(questionId, {
        selected_choice_id: selectedChoiceId ?? null,
        attempt_id: detail.id,
      });
      setExplanations((prev) => ({
        ...prev,
        [questionId]: { data: res, open: true },
      }));
    } catch (e) {
      setExplanations((prev) => ({
        ...prev,
        [questionId]: {
          err: e instanceof Error ? e.message : t('err_retry_js'),
          open: true,
        },
      }));
    } finally {
      setExplainingId(null);
    }
  };

  return (
    <div>
      {/* BMB Grade & Result Summary Card */}
      <div
        className="card"
        style={{
          background: 'linear-gradient(135deg, rgba(16, 185, 129, 0.05) 0%, rgba(59, 130, 246, 0.05) 100%)',
          border: `1px solid ${bmb.color}40`,
          borderRadius: '12px',
          padding: '16px',
          marginBottom: '16px',
        }}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 12 }}>
          <div>
            <span
              style={{
                display: 'inline-block',
                padding: '4px 12px',
                borderRadius: '8px',
                fontWeight: 800,
                fontSize: '1rem',
                color: bmb.color,
                background: bmb.bg,
                border: `1px solid ${bmb.color}60`,
                marginBottom: '6px',
              }}
            >
              {t('bmb_official_grade')}: {bmb.grade}
            </span>
            <p style={{ margin: 0, fontWeight: 600, fontSize: '0.95rem' }}>{bmb.desc}</p>
            <p className="muted small" style={{ margin: '4px 0 0' }}>
              {t('overall_score')}: <strong>{pct}%</strong> {detail.is_passed ? `(${t('passed_status')})` : `(${t('failed_status')})`}
            </p>
          </div>
          <button
            type="button"
            className="btn sm"
            onClick={toggleDiagnostics}
            style={{
              borderColor: '#f59e0b',
              color: '#f59e0b',
              display: 'inline-flex',
              alignItems: 'center',
              gap: 6,
            }}
          >
            <span>🧠</span>
            <span>{showDiag ? t('ai_diag_btn_close') : t('ai_diag_btn_open')}</span>
          </button>
        </div>

        {/* AI Diagnostics Panel */}
        {showDiag && (
          <div
            style={{
              marginTop: '16px',
              paddingTop: '16px',
              borderTop: '1px solid rgba(255, 255, 255, 0.08)',
            }}
          >
            {diagLoading && <p className="muted small">🤖 AI repetitor xatolaringizni tahlil qilmoqda…</p>}
            {diagErr && <p className="error small">{diagErr}</p>}
            {diagData && (
              <div style={{ display: 'grid', gap: 12 }}>
                <div
                  style={{
                    background: 'rgba(245, 158, 11, 0.08)',
                    border: '1px solid rgba(245, 158, 11, 0.25)',
                    borderRadius: '8px',
                    padding: '12px',
                  }}
                >
                  <strong style={{ color: '#f59e0b', display: 'block', marginBottom: 4 }}>
                    💡 Shaxsiy AI Repetitor Xulosasi:
                  </strong>
                  <p style={{ margin: 0, fontSize: '0.9rem', lineHeight: 1.5 }}>
                    {diagData.general_advice}
                  </p>
                </div>

                {diagData.weak_topics.length > 0 && (
                  <div>
                    <h5 style={{ margin: '8px 0', fontSize: '0.9rem' }}>
                      Aniqlangan zaif mavzular ({diagData.weak_topics.length} ta):
                    </h5>
                    <div style={{ display: 'grid', gap: 8 }}>
                      {diagData.weak_topics.map((wt, idx) => {
                        const sevColor =
                          wt.severity === 'high'
                            ? '#ef4444'
                            : wt.severity === 'medium'
                              ? '#f59e0b'
                              : '#3b82f6';
                        return (
                          <div
                            key={idx}
                            style={{
                              background: 'rgba(255, 255, 255, 0.02)',
                              border: '1px solid rgba(255, 255, 255, 0.06)',
                              borderRadius: '8px',
                              padding: '10px 12px',
                            }}
                          >
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                              <strong style={{ fontSize: '0.88rem' }}>{wt.topic}</strong>
                              <span
                                style={{
                                  fontSize: '0.75rem',
                                  padding: '2px 8px',
                                  borderRadius: '4px',
                                  color: sevColor,
                                  background: `${sevColor}20`,
                                  fontWeight: 600,
                                }}
                              >
                                {wt.incorrect_count} ta xato ·{' '}
                                {wt.severity === 'high'
                                  ? 'Yuqori xavf'
                                  : wt.severity === 'medium'
                                    ? 'O‘rta xavf'
                                    : 'Takrorlash lozim'}
                              </span>
                            </div>
                            <p className="muted small" style={{ margin: '4px 0 0', fontSize: '0.82rem' }}>
                              👉 {wt.recommendation}
                            </p>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        )}
      </div>

      {pending ? (
        <>
          <h3>{t('take_pending_title')}</h3>
          <p className="muted">{t('take_pending_msg')}</p>
          <p className="muted small">
            {t('take_objective_done')} · {t('take_writing_pending')}
          </p>
        </>
      ) : unverified ? (
        <>
          <h3>
            {t('take_rules_unverified_title')} — {pct}%
          </h3>
          <p className="muted">{t('take_rules_unverified_msg')}</p>
          <p className="badge blue">{t('raw_score_not_official')}</p>
        </>
      ) : (
        <h3>
          {detail.is_passed ? t('rd_passed_msg') : t('rd_failed_msg')} — {pct}%
        </h3>
      )}

      {(detail.section_scores ?? []).length > 0 && (
        <div
          className="card"
          style={{
            margin: '16px 0',
            background: 'rgba(59, 130, 246, 0.04)',
            border: '1px solid rgba(59, 130, 246, 0.25)',
            borderRadius: '12px',
            padding: '16px',
          }}
        >
          <h4 style={{ margin: '0 0 12px', display: 'flex', alignItems: 'center', gap: 8, fontSize: '1rem', color: '#60a5fa' }}>
            <span>📊</span> Bo‘limlar kesimidagi batafsil tahlil
          </h4>
          <div style={{ display: 'grid', gap: 10 }}>
            {(detail.section_scores ?? []).map((s) => {
              const earnedNum = Number(s.earned) || 0;
              const maxNum = Number(s.maximum) || 1;
              const secPct = Math.round((earnedNum / maxNum) * 100);
              const barColor = secPct >= 70 ? '#10b981' : secPct >= 50 ? '#f59e0b' : '#ef4444';
              return (
                <div
                  key={s.section_code || s.section_name}
                  style={{
                    background: 'var(--card)',
                    border: '1px solid var(--border)',
                    borderRadius: '8px',
                    padding: '10px 14px',
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6, flexWrap: 'wrap', gap: 6 }}>
                    <strong style={{ fontSize: '0.92rem', color: 'var(--ink)' }}>
                      {s.section_name || s.section_code}
                    </strong>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <span className="badge" style={{ fontSize: '0.8rem', fontWeight: 700 }}>
                        {String(s.earned)} / {String(s.maximum)} ball
                      </span>
                      <span
                        style={{
                          fontWeight: 800,
                          fontSize: '0.85rem',
                          color: barColor,
                        }}
                      >
                        {secPct}%
                      </span>
                    </div>
                  </div>
                  <div className="progress" style={{ height: '6px', margin: 0 }}>
                    <div style={{ width: `${Math.min(100, Math.max(0, secPct))}%`, background: barColor }} />
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      <div className="toolbar">
        <span className="badge green">
          {t('rd_correct')}: {Number(detail.correct_answers ?? 0)}
        </span>
        <span className="badge rose">
          {t('rd_wrong')}: {Number(detail.wrong_answers ?? 0)}
        </span>
        <span className="badge">
          {t('rd_unanswered')}: {Number(detail.unanswered ?? 0)}
        </span>
        <span className="badge blue">
          {t('score')}: {String(detail.score ?? '—')}/{String(detail.max_score ?? '—')}
        </span>
      </div>
      <p className="muted small">
        {t('rd_time_spent')}: {formatDuration(detail.time_taken_seconds)}
      </p>
      {unverified && <p className="badge blue">{t('raw_score_not_official')}</p>}
      {detail.certificate_info && (
        <p className="muted small">
          {t('mc_number')} {detail.certificate_info.certificate_number} (
          {detail.certificate_info.status}){' '}
          <Link to="/certificates">{t('my_certificates')} →</Link>
        </p>
      )}

      <h4 style={{ marginTop: '20px' }}>{t('rd_analysis')}</h4>
      <div style={{ display: 'grid', gap: 12 }}>
        {(detail.question_details ?? []).map((qd) => {
          const isWrong = qd.is_correct === false;
          const selectedChoiceId = qd.selected_choices?.[0]?.id ?? null;
          const expl = explanations[qd.question_id];
          const isThisLoading = explainingId === qd.question_id;

          // Student javobini aniqlash (variant yoki ochiq matn)
          const studentAnswerDisplay =
            (qd.selected_choices ?? []).length > 0
              ? qd.selected_choices.map((c) => c.text).filter(Boolean).join(', ')
              : (qd.student_answer_text || '').trim() || 'Javob berilmagan';

          // Rasmiy to'g'ri javobni aniqlash (barcha savol turlarida yashil blokda ko'rinadi)
          let correctAnswerDisplay =
            (qd.correct_choices ?? []).length > 0
              ? qd.correct_choices.map((c) => c.text).filter(Boolean).join(', ')
              : (qd.correct_text || '').trim();

          if (!correctAnswerDisplay && qd.explanation) {
            const m = qd.explanation.match(/To['`’ʻʼ]g['`’ʻʼ]ri javob[:\s—]+['"«]?(.*?)['"»]?(?:\.|\n|$)/i);
            if (m && m[1]) {
              correctAnswerDisplay = m[1].trim();
            }
          }
          if (!correctAnswerDisplay) {
            correctAnswerDisplay = '—';
          }

          // AI tushuntirishini toza qoida va tahlil qilib ko'rsatish
          const explanationClean = qd.explanation
            ? qd.explanation.replace(/^To['`’ʻʼ]g['`’ʻʼ]ri javob[:\s—]+['"«]?[^.'"]+['"»]?[.]?\s*/i, '').trim() || qd.explanation
            : '';

          return (
            <div
              key={qd.question_id}
              className="card"
              style={
                isWrong
                  ? {
                      borderLeft: '4px solid #ef4444',
                      background: 'radial-gradient(circle at top right, rgba(239, 68, 68, 0.03) 0%, var(--card) 100%)',
                    }
                  : qd.is_correct
                  ? {
                      borderLeft: '4px solid #10b981',
                    }
                  : undefined
              }
            >
              <p style={{ whiteSpace: 'pre-line', margin: '0 0 10px', lineHeight: 1.5 }}>
                <span
                  className={`badge ${qd.is_correct ? 'green' : isWrong ? 'rose' : ''}`}
                  style={{ marginRight: 8 }}
                >
                  {qd.is_correct ? '✓ To‘g‘ri' : isWrong ? '✗ Xato' : '—'}
                </span>{' '}
                <strong>{qd.question_text}</strong>
              </p>

              <div style={{ display: 'grid', gap: 6, marginTop: 8 }}>
                {/* ❌ Sizning javobingiz (agar xato bo'lsa) */}
                {isWrong && (
                  <div
                    style={{
                      padding: '8px 12px',
                      borderRadius: 8,
                      background: 'rgba(239, 68, 68, 0.08)',
                      border: '1px solid rgba(239, 68, 68, 0.3)',
                      color: '#f87171',
                      fontSize: '0.92rem',
                    }}
                  >
                    <strong style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
                      ❌ Sizning javobingiz:
                    </strong>{' '}
                    <span>{studentAnswerDisplay}</span>
                  </div>
                )}

                {/* ✅ To'g'ri javob */}
                <div
                  style={{
                    padding: '8px 12px',
                    borderRadius: 8,
                    background: 'rgba(16, 185, 129, 0.08)',
                    border: '1px solid rgba(16, 185, 129, 0.3)',
                    color: '#34d399',
                    fontSize: '0.92rem',
                  }}
                >
                  <strong style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
                    ✅ To‘g‘ri javob:
                  </strong>{' '}
                  <span>{correctAnswerDisplay}</span>
                  {qd.is_correct && (
                    <span className="small muted" style={{ marginLeft: 6 }}>
                      (Siz ham to‘g‘ri belgiladingiz)
                    </span>
                  )}
                </div>
              </div>

              {/* 💡 Nega bu javob xato? AI tushuntirishi (Ochiq tursin) */}
              {explanationClean && (
                <div
                  style={{
                    marginTop: 10,
                    padding: '12px 14px',
                    background: 'rgba(59, 130, 246, 0.06)',
                    border: '1px solid rgba(59, 130, 246, 0.25)',
                    borderRadius: 8,
                    fontSize: '0.9rem',
                    lineHeight: 1.6,
                    color: 'var(--ink)',
                  }}
                >
                  <strong style={{ color: '#60a5fa', display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
                    <span>💡</span> {isWrong ? 'Nega bu javob xato? AI tushuntirishi:' : t('bmb_rule_explanation')}
                  </strong>
                  <span>{explanationClean}</span>
                </div>
              )}

              {/* Interactive AI Mistake Explainer */}
              {isWrong && (
                <div style={{ marginTop: '10px' }}>
                  <button
                    type="button"
                    className="btn sm ghost"
                    disabled={isThisLoading}
                    onClick={() => explainQuestion(qd.question_id, selectedChoiceId)}
                    style={{
                      borderColor: '#10b981',
                      color: '#10b981',
                      fontSize: '0.8rem',
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: 6,
                    }}
                  >
                    <span>💡</span>
                    <span>
                      {isThisLoading
                        ? t('ai_explaining')
                        : expl?.open
                          ? t('ai_explain_hide')
                          : t('ai_explain_btn')}
                    </span>
                  </button>

                  {expl?.open && (
                    <div
                      style={{
                        marginTop: '10px',
                        background: 'rgba(16, 185, 129, 0.05)',
                        border: '1px solid rgba(16, 185, 129, 0.25)',
                        borderRadius: '8px',
                        padding: '12px 14px',
                        fontSize: '0.88rem',
                        lineHeight: 1.5,
                      }}
                    >
                      {expl.err && <p className="error small" style={{ margin: 0 }}>{expl.err}</p>}
                      {expl.data && (
                        <div style={{ display: 'grid', gap: 8 }}>
                          <div>
                            <strong style={{ color: '#ef4444' }}>{t('why_wrong_title')}</strong>
                            <p style={{ margin: '2px 0 0', color: 'var(--text)' }}>
                              {expl.data.why_wrong}
                            </p>
                          </div>
                          <div>
                            <strong style={{ color: '#10b981' }}>{t('correct_rule_title')}</strong>
                            <p style={{ margin: '2px 0 0', color: 'var(--text)' }}>
                              {expl.data.correct_rule}
                            </p>
                          </div>
                          {expl.data.memory_tip && (
                            <div
                              style={{
                                background: 'rgba(245, 158, 11, 0.08)',
                                border: '1px dashed rgba(245, 158, 11, 0.3)',
                                borderRadius: '6px',
                                padding: '8px 10px',
                              }}
                            >
                              <strong style={{ color: '#f59e0b', fontSize: '0.84rem' }}>
                                {t('mnemonic_title')}
                              </strong>
                              <p style={{ margin: '2px 0 0', fontSize: '0.84rem' }}>
                                {expl.data.memory_tip}
                              </p>
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              )}
            </div>
          );
        })}
        {(detail.question_details ?? []).length === 0 && (
          <p className="muted">{t('take_no_analysis')}</p>
        )}
      </div>
    </div>
  );
}
