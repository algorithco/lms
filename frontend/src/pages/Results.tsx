import { useCallback, useEffect, useState } from 'react';
import TestAddictiveResults, { type QuestionReviewItem } from '../components/TestAddictiveResults';
import { Link, useParams } from 'react-router-dom';
import { useLang } from '../i18n/LangContext';
import {
  AiTutor,
  type ResultDiagnosticsResponse,
  Results as ResultsApi,
} from '../lib/api';
import {
  formatDuration,
  listResultsPage,
  num,
  type ResultListItem,
  TestsApi,
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
  current_rasch_weight?: number;
  difficulty_logit?: number;
  total_attempts?: number;
  correct_attempts?: number;
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
  rasch_score?: string | number;
  max_rasch_score?: string | number;
  rasch_grade?: string;
  rasch_explanation?: string;
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
                    {r.rasch_score !== undefined && r.rasch_score !== null && Number(r.rasch_score) > 0 && (
                      <span
                        style={{
                          padding: '2px 8px',
                          borderRadius: '6px',
                          fontWeight: 800,
                          fontSize: '0.78rem',
                          color: '#b45309',
                          background: 'rgba(245, 158, 11, 0.16)',
                          border: '1px solid rgba(245, 158, 11, 0.45)',
                        }}
                        title={`Rasch dinamik bali: ${r.rasch_score}`}
                      >
                        ⚡️ Rash: {Number(r.rasch_score).toFixed(1)}
                      </span>
                    )}
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
  const bmb = getBmbBadge(detail.bmb_grade, pct, t);

  const [_retesting, setRetesting] = useState(false);
  const [retestErr, setRetestErr] = useState<string | null>(null);

  const handleStartRetest = async () => {
    const targetId = (detail as any).attempt_id || detail.id;
    setRetesting(true);
    setRetestErr(null);
    try {
      const res = await TestsApi.generateRetest(targetId);
      if (res.has_mistakes && res.attempt_id) {
        window.location.href = `/take/${res.attempt_id}`;
      } else {
        alert(res.message || "Barcha savollar to'g'ri yechilgan!");
      }
    } catch (e: unknown) {
      setRetestErr(e instanceof Error ? e.message : "Qayta test yaratishda xatolik yuz berdi.");
    } finally {
      setRetesting(false);
    }
  };

  // 24/7 AI Tutor Diagnostics
  const [showDiag, setShowDiag] = useState(false);
  const [diagLoading, setDiagLoading] = useState(false);
  const [diagData, setDiagData] = useState<ResultDiagnosticsResponse | null>(null);
  const [diagErr, setDiagErr] = useState<string | null>(null);

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

  // Map questions for TestAddictiveResults
  const mappedQuestions: QuestionReviewItem[] = (detail.question_details ?? []).map((qd) => {
    const isWrong = qd.is_correct === false;
    const studentAnswerDisplay =
      (qd.selected_choices ?? []).length > 0
        ? qd.selected_choices.map((c) => c.text).filter(Boolean).join(', ')
        : (qd.student_answer_text || '').trim() || 'Javob berilmagan';

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

    const explanationClean = qd.explanation
      ? qd.explanation.replace(/^To['`’ʻʼ]g['`’ʻʼ]ri javob[:\s—]+['"«]?[^.'"]+['"»]?[.]?\s*/i, '').trim() || qd.explanation
      : '';

    return {
      id: qd.question_id,
      question_text: qd.question_text,
      points: qd.current_rasch_weight ?? qd.points ?? 2,
      is_correct: qd.is_correct,
      selected_choice_text: isWrong ? studentAnswerDisplay : undefined,
      correct_choice_text: correctAnswerDisplay || '—',
      explanation: explanationClean,
    };
  });

  return (
    <div>
      {pending && (
        <div className="card" style={{ padding: 24, textAlign: 'center', marginBottom: 20 }}>
          <h3>{t('take_pending_title')}</h3>
          <p className="muted">{t('take_pending_msg')}</p>
          <p className="muted small">
            {t('take_objective_done')} · {t('take_writing_pending')}
          </p>
        </div>
      )}

      {retestErr && (
        <div style={{ marginBottom: 16, padding: '10px 14px', borderRadius: 10, background: '#FEF2F2', border: '1px solid #FCA5A5', color: '#DC2626', fontSize: 13, fontWeight: 600 }}>
          {retestErr}
        </div>
      )}

      <TestAddictiveResults
        score={Number(detail.score ?? 0)}
        maxScore={Number(detail.max_score ?? 0)}
        percentage={pct}
        correctCount={Number(detail.correct_answers ?? 0)}
        wrongCount={Number(detail.wrong_answers ?? 0)}
        unansweredCount={Number(detail.unanswered ?? 0)}
        timeSpentSeconds={Number(detail.time_taken_seconds ?? 0)}
        raschScore={detail.rasch_score}
        raschGrade={detail.rasch_grade}
        bmbGrade={detail.bmb_grade || bmb.grade}
        courseTitle={detail.test_title}
        attemptId={String((detail as any).attempt_id || detail.id)}
        questions={mappedQuestions}
        onRetest={handleStartRetest}
      >
        {/* Certificate info */}
        {detail.certificate_info && (
          <div
            style={{
              padding: '14px 18px',
              borderRadius: 14,
              background: 'rgba(16, 185, 129, 0.08)',
              border: '1.5px solid rgba(16, 185, 129, 0.3)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              flexWrap: 'wrap',
              gap: 10,
              marginBottom: 16,
            }}
          >
            <div>
              <strong style={{ color: '#059669', fontSize: '0.95rem' }}>
                📜 Rasmiy Elektron Sertifikat Mavjud!
              </strong>
              <p style={{ margin: '2px 0 0', fontSize: '0.85rem', color: 'var(--muted)' }}>
                {t('mc_number')}: <strong>{detail.certificate_info.certificate_number}</strong> ({detail.certificate_info.status})
              </p>
            </div>
            <Link
              to="/certificates"
              className="btn sm"
              style={{
                background: '#10b981',
                color: '#fff',
                fontWeight: 800,
                borderRadius: 10,
                textDecoration: 'none',
              }}
            >
              {t('my_certificates')} →
            </Link>
          </div>
        )}

        {/* 24/7 AI Tutor Diagnostics Accordion */}
        <div
          style={{
            background: 'var(--card)',
            border: '1px solid var(--border)',
            borderRadius: 18,
            padding: '16px 20px',
            marginBottom: 16,
          }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 10 }}>
            <div>
              <strong style={{ fontSize: '0.98rem', display: 'flex', alignItems: 'center', gap: 6, color: 'var(--ink)' }}>
                <span>🧠</span> 24/7 Shaxsiy AI Repetitor Diagnostikasi
              </strong>
              <p className="muted small" style={{ margin: '2px 0 0' }}>
                Xatolar bo&apos;yicha chuqurlashtirilgan tahlil va zaif mavzularni o&apos;rganish.
              </p>
            </div>
            <button
              type="button"
              className="btn sm"
              onClick={toggleDiagnostics}
              style={{
                borderColor: '#f59e0b',
                color: '#d97706',
                fontWeight: 800,
                borderRadius: 10,
                display: 'inline-flex',
                alignItems: 'center',
                gap: 6,
              }}
            >
              <span>{showDiag ? '▲ Yopish' : '▼ AI Tahlilini Ko‘rish'}</span>
            </button>
          </div>

          {showDiag && (
            <div style={{ marginTop: 14, paddingTop: 14, borderTop: '1px solid var(--border)' }}>
              {diagLoading && <p className="muted small">🤖 AI repetitor xatolaringizni tahlil qilmoqda…</p>}
              {diagErr && <p className="error small">{diagErr}</p>}
              {diagData && (
                <div style={{ display: 'grid', gap: 12 }}>
                  <div
                    style={{
                      background: 'rgba(245, 158, 11, 0.08)',
                      border: '1px solid rgba(245, 158, 11, 0.25)',
                      borderRadius: '12px',
                      padding: '14px',
                    }}
                  >
                    <strong style={{ color: '#d97706', display: 'block', marginBottom: 4 }}>
                      💡 Shaxsiy AI Repetitor Xulosasi:
                    </strong>
                    <p style={{ margin: 0, fontSize: '0.9rem', lineHeight: 1.55 }}>
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
                                border: '1px solid var(--border)',
                                borderRadius: '10px',
                                padding: '10px 14px',
                              }}
                            >
                              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                                <strong style={{ fontSize: '0.88rem' }}>{wt.topic}</strong>
                                <span
                                  style={{
                                    fontSize: '0.75rem',
                                    padding: '2px 8px',
                                    borderRadius: '6px',
                                    color: sevColor,
                                    background: `${sevColor}20`,
                                    fontWeight: 700,
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

        {/* Section Scores if present */}
        {(detail.section_scores ?? []).length > 0 && (
          <div
            className="card"
            style={{
              marginBottom: 16,
              background: 'rgba(59, 130, 246, 0.04)',
              border: '1px solid rgba(59, 130, 246, 0.25)',
              borderRadius: '16px',
              padding: '16px 20px',
            }}
          >
            <h4 style={{ margin: '0 0 12px', display: 'flex', alignItems: 'center', gap: 8, fontSize: '0.98rem', color: '#2563eb' }}>
              <span>📊</span> Bo‘limlar kesimidagi rasmiy ballar
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
                      borderRadius: '10px',
                      padding: '10px 14px',
                    }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6, flexWrap: 'wrap', gap: 6 }}>
                      <strong style={{ fontSize: '0.9rem', color: 'var(--ink)' }}>
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
      </TestAddictiveResults>
    </div>
  );
}
