import { useEffect, useState } from 'react';
import {
  type AttemptQuestionDetail,
  type TeacherAttemptDetailsResponse,
  TeacherGradebookApi,
} from '../lib/api';
import {
  ClockIcon,
  XIcon,
} from './icons';

interface StudentAttemptReviewModalProps {
  attemptId: number | null;
  isOpen: boolean;
  onClose: () => void;
}

export default function StudentAttemptReviewModal({
  attemptId,
  isOpen,
  onClose,
}: StudentAttemptReviewModalProps) {
  const [data, setData] = useState<TeacherAttemptDetailsResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [filter, setFilter] = useState<'all' | 'mistakes' | 'correct'>('all');

  useEffect(() => {
    if (!isOpen || !attemptId) {
      setData(null);
      return;
    }

    let alive = true;
    setLoading(true);
    setErr(null);

    TeacherGradebookApi.attemptDetails(attemptId)
      .then((res) => {
        if (alive) {
          setData(res);
          setLoading(false);
        }
      })
      .catch((e) => {
        if (alive) {
          setErr(e instanceof Error ? e.message : 'Urinish tafsilotlarini yuklab bo‘lmadi.');
          setLoading(false);
        }
      });

    return () => {
      alive = false;
    };
  }, [isOpen, attemptId]);

  // Close on ESC
  useEffect(() => {
    if (!isOpen) return;
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  const filteredQuestions = (data?.questions || []).filter((q) => {
    if (filter === 'mistakes') return !q.is_correct;
    if (filter === 'correct') return q.is_correct;
    return true;
  });

  const handlePrint = () => {
    window.print();
  };

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 9999,
        background: 'rgba(15, 23, 42, 0.75)',
        backdropFilter: 'blur(8px)',
        WebkitBackdropFilter: 'blur(8px)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: 16,
      }}
      role="dialog"
      aria-modal="true"
      onClick={onClose}
    >
      <div
        style={{
          width: '100%',
          maxWidth: 880,
          maxHeight: '90vh',
          background: 'var(--card, #FFFFFF)',
          color: 'var(--ink, #0F172A)',
          borderRadius: 24,
          boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.35)',
          border: '1px solid var(--border, rgba(148, 163, 184, 0.25))',
          display: 'flex',
          flexDirection: 'column',
          overflow: 'hidden',
          position: 'relative',
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* MODAL HEADER */}
        <div
          style={{
            padding: '20px 24px 16px',
            borderBottom: '1px solid var(--border, rgba(148, 163, 184, 0.2))',
            display: 'flex',
            alignItems: 'flex-start',
            justifyContent: 'space-between',
            gap: 16,
          }}
        >
          <div style={{ minWidth: 0, flex: 1 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
              <span
                style={{
                  fontSize: 11,
                  fontWeight: 800,
                  textTransform: 'uppercase',
                  letterSpacing: '0.06em',
                  padding: '3px 8px',
                  borderRadius: 6,
                  background: 'rgba(245, 158, 11, 0.15)',
                  color: '#D97706',
                }}
              >
                🔍 O‘quvchi xatolari tahlili
              </span>
              {data?.mock_code && (
                <span
                  style={{
                    fontSize: 11,
                    fontWeight: 700,
                    padding: '3px 8px',
                    borderRadius: 6,
                    background: 'rgba(16, 185, 129, 0.15)',
                    color: '#059669',
                  }}
                >
                  Kod: {data.mock_code}
                </span>
              )}
            </div>

            <h2
              style={{
                margin: 0,
                fontSize: 20,
                fontWeight: 900,
                color: 'var(--ink, #0F172A)',
                lineHeight: 1.3,
                whiteSpace: 'nowrap',
                overflow: 'hidden',
                textOverflow: 'ellipsis',
              }}
            >
              {data?.student.full_name || "O'quvchi natijasi"}
            </h2>

            <p style={{ margin: '4px 0 0', fontSize: 13, color: 'var(--muted, #64748B)' }}>
              Test: <b>{data?.test_title || 'Noma‘lum test'}</b> · Topshirilgan: <b>{data?.completed_at || '-'}</b>
            </p>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <button
              type="button"
              onClick={handlePrint}
              className="btn sm"
              style={{
                padding: '6px 12px',
                borderRadius: 8,
                border: '1px solid var(--border, #E2E8F0)',
                background: 'var(--card-2, #F8FAFC)',
                color: 'var(--ink, #0F172A)',
                cursor: 'pointer',
                fontSize: 12,
                fontWeight: 700,
                display: 'inline-flex',
                alignItems: 'center',
                gap: 5,
              }}
              title="Chop etish"
            >
              <span>🖨️</span>
              <span>Chop etish</span>
            </button>

            <button
              type="button"
              onClick={onClose}
              style={{
                background: 'transparent',
                border: 'none',
                color: 'var(--muted, #64748B)',
                cursor: 'pointer',
                padding: 6,
                borderRadius: 8,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}
              aria-label="Yopish"
            >
              <XIcon size={20} />
            </button>
          </div>
        </div>

        {/* LOADING & ERROR STATES */}
        {loading && (
          <div style={{ padding: 48, textAlign: 'center', color: 'var(--muted)' }}>
            <p style={{ fontSize: 15, fontWeight: 700 }}>Xatolar tahlili yuklanmoqda…</p>
          </div>
        )}

        {err && (
          <div style={{ padding: 32, textAlign: 'center' }}>
            <div style={{ color: '#EF4444', fontWeight: 800, marginBottom: 12 }}>{err}</div>
            <button
              type="button"
              onClick={onClose}
              className="btn sm"
              style={{
                padding: '6px 16px',
                borderRadius: 8,
                background: 'var(--card-2)',
                border: '1px solid var(--border)',
                cursor: 'pointer',
              }}
            >
              Yopish
            </button>
          </div>
        )}

        {/* CONTENT */}
        {!loading && !err && data && (
          <>
            {/* SCORE SUMMARY STRIP */}
            <div
              style={{
                padding: '12px 24px',
                background: 'var(--card-2, #F8FAFC)',
                borderBottom: '1px solid var(--border, rgba(148, 163, 184, 0.2))',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                flexWrap: 'wrap',
                gap: 12,
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
                <div
                  style={{
                    padding: '4px 12px',
                    borderRadius: 999,
                    background: 'rgba(16, 185, 129, 0.15)',
                    color: '#059669',
                    fontSize: 13,
                    fontWeight: 800,
                  }}
                >
                  Xom ball: {data.raw_score} / {data.total_questions} ({data.percentage}%)
                </div>

                <div
                  style={{
                    padding: '4px 12px',
                    borderRadius: 999,
                    background: 'rgba(245, 158, 11, 0.15)',
                    color: '#D97706',
                    fontSize: 13,
                    fontWeight: 800,
                  }}
                >
                  ⭐️ Rasch: {data.rasch_score} ball ({data.rasch_grade})
                </div>

                <div
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: 4,
                    fontSize: 12,
                    color: 'var(--muted)',
                    fontWeight: 600,
                  }}
                >
                  <ClockIcon size={13} />
                  <span>{data.time_spent_formatted}</span>
                </div>
              </div>

              {/* FILTER BUTTONS */}
              <div style={{ display: 'flex', gap: 6 }}>
                <button
                  type="button"
                  onClick={() => setFilter('all')}
                  style={{
                    padding: '5px 12px',
                    borderRadius: 8,
                    border: 'none',
                    background: filter === 'all' ? 'var(--card, #FFF)' : 'transparent',
                    color: filter === 'all' ? 'var(--ink)' : 'var(--muted)',
                    fontWeight: 800,
                    fontSize: 12,
                    cursor: 'pointer',
                    boxShadow: filter === 'all' ? '0 1px 3px rgba(0,0,0,0.1)' : 'none',
                  }}
                >
                  Barchasi ({data.questions.length})
                </button>

                <button
                  type="button"
                  onClick={() => setFilter('mistakes')}
                  style={{
                    padding: '5px 12px',
                    borderRadius: 8,
                    border: 'none',
                    background: filter === 'mistakes' ? '#FEE2E2' : 'transparent',
                    color: filter === 'mistakes' ? '#DC2626' : '#EF4444',
                    fontWeight: 800,
                    fontSize: 12,
                    cursor: 'pointer',
                    boxShadow: filter === 'mistakes' ? '0 1px 3px rgba(0,0,0,0.1)' : 'none',
                  }}
                >
                  ❌ Xatolar ({data.mistake_count})
                </button>

                <button
                  type="button"
                  onClick={() => setFilter('correct')}
                  style={{
                    padding: '5px 12px',
                    borderRadius: 8,
                    border: 'none',
                    background: filter === 'correct' ? '#D1FAE5' : 'transparent',
                    color: filter === 'correct' ? '#059669' : '#10B981',
                    fontWeight: 800,
                    fontSize: 12,
                    cursor: 'pointer',
                    boxShadow: filter === 'correct' ? '0 1px 3px rgba(0,0,0,0.1)' : 'none',
                  }}
                >
                  ✅ To‘g‘ri ({data.correct_count})
                </button>
              </div>
            </div>

            {/* QUESTIONS SCROLLABLE LIST */}
            <div
              style={{
                flex: 1,
                overflowY: 'auto',
                padding: '20px 24px',
                display: 'flex',
                flexDirection: 'column',
                gap: 16,
              }}
            >
              {filteredQuestions.length === 0 ? (
                <div style={{ textAlign: 'center', padding: '40px 0', color: 'var(--muted)' }}>
                  {filter === 'mistakes'
                    ? '🎉 Ushbu o‘quvchi birorta ham xato qilmagan!'
                    : 'Savollar mavjud emas.'}
                </div>
              ) : (
                filteredQuestions.map((q) => (
                  <QuestionInspectionCard key={q.question_id} question={q} />
                ))
              )}
            </div>
          </>
        )}
      </div>
    </div>
  );
}

function QuestionInspectionCard({ question: q }: { question: AttemptQuestionDetail }) {
  return (
    <div
      style={{
        borderRadius: 16,
        padding: '16px 20px',
        background: 'var(--card, #FFFFFF)',
        border: q.is_correct
          ? '1.5px solid rgba(16, 185, 129, 0.35)'
          : '1.5px solid rgba(239, 68, 68, 0.4)',
        boxShadow: '0 2px 8px rgba(0,0,0,0.04)',
      }}
    >
      {/* CARD TOP META */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span
            style={{
              padding: '3px 10px',
              borderRadius: 8,
              fontSize: 12,
              fontWeight: 900,
              background: q.is_correct ? 'rgba(16, 185, 129, 0.15)' : 'rgba(239, 68, 68, 0.15)',
              color: q.is_correct ? '#059669' : '#DC2626',
            }}
          >
            {q.is_correct ? '✅ To‘g‘ri' : '❌ Xato'}
          </span>

          <strong style={{ fontSize: 14, color: 'var(--ink)' }}>
            #{q.question_number}-savol
          </strong>
        </div>

        <span style={{ fontSize: 12, color: 'var(--muted)', fontWeight: 700 }}>
          ⭐️ Rasch: {q.rasch_weight} ball ({q.points} ball)
        </span>
      </div>

      {/* READING PASSAGE (IF PRESENT) */}
      {q.passage && (
        <div
          style={{
            padding: '10px 14px',
            borderRadius: 10,
            background: 'var(--card-2, #F8FAFC)',
            border: '1px solid var(--border, #E2E8F0)',
            fontSize: 12.5,
            color: 'var(--muted, #475569)',
            marginBottom: 12,
            lineHeight: 1.5,
            maxHeight: 120,
            overflowY: 'auto',
          }}
        >
          {q.passage}
        </div>
      )}

      {/* QUESTION TEXT */}
      <p style={{ margin: '0 0 14px', fontSize: 14.5, fontWeight: 700, color: 'var(--ink)', lineHeight: 1.5 }}>
        {q.question_text}
      </p>

      {/* CHOICES LIST */}
      {q.choices && q.choices.length > 0 ? (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginBottom: 12 }}>
          {q.choices.map((c) => {
            const isStudentSelection = c.is_selected;
            const isAnswerKey = c.is_correct;

            let bgColor = 'var(--card-2, #F8FAFC)';
            let borderColor = 'var(--border, #E2E8F0)';
            let textColor = 'var(--ink, #0F172A)';
            let badgeText = '';
            let badgeBg = '';
            let badgeColor = '';

            if (isStudentSelection && isAnswerKey) {
              // Student correctly selected this
              bgColor = 'rgba(16, 185, 129, 0.12)';
              borderColor = '#10B981';
              textColor = '#065F46';
              badgeText = 'O‘quvchi to‘g‘ri tanlagan';
              badgeBg = '#10B981';
              badgeColor = '#FFFFFF';
            } else if (isStudentSelection && !isAnswerKey) {
              // Student wrongly selected this
              bgColor = 'rgba(239, 68, 68, 0.12)';
              borderColor = '#EF4444';
              textColor = '#991B1B';
              badgeText = 'O‘quvchi xato tanlagan';
              badgeBg = '#EF4444';
              badgeColor = '#FFFFFF';
            } else if (!isStudentSelection && isAnswerKey) {
              // Correct answer that was missed by student
              bgColor = 'rgba(16, 185, 129, 0.08)';
              borderColor = 'rgba(16, 185, 129, 0.5)';
              textColor = '#059669';
              badgeText = 'To‘g‘ri javob';
              badgeBg = 'rgba(16, 185, 129, 0.2)';
              badgeColor = '#059669';
            }

            return (
              <div
                key={c.id}
                style={{
                  padding: '9px 14px',
                  borderRadius: 10,
                  background: bgColor,
                  border: `1.5px solid ${borderColor}`,
                  color: textColor,
                  fontSize: 13.5,
                  fontWeight: isStudentSelection || isAnswerKey ? 700 : 500,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  gap: 12,
                }}
              >
                <span>{c.text}</span>

                {badgeText && (
                  <span
                    style={{
                      fontSize: 11,
                      fontWeight: 800,
                      padding: '2px 8px',
                      borderRadius: 6,
                      background: badgeBg,
                      color: badgeColor,
                      flexShrink: 0,
                    }}
                  >
                    {badgeText}
                  </span>
                )}
              </div>
            );
          })}
        </div>
      ) : (
        /* TEXT MATCH QUESTION */
        <div style={{ marginBottom: 12, padding: 12, borderRadius: 10, background: 'var(--card-2)' }}>
          <div style={{ fontSize: 13, marginBottom: 4 }}>
            O‘quvchi javobi:{' '}
            <strong style={{ color: q.is_correct ? '#059669' : '#DC2626' }}>
              {q.student_text_answer || '(Javob yozilmagan)'}
            </strong>
          </div>
          {q.correct_text && (
            <div style={{ fontSize: 13, color: '#059669' }}>
              To‘g‘ri javob: <strong>{q.correct_text}</strong>
            </div>
          )}
        </div>
      )}

      {/* EXPLANATION / AI FEEDBACK CALLOUT */}
      {q.explanation && (
        <div
          style={{
            padding: '10px 14px',
            borderRadius: 10,
            background: 'linear-gradient(135deg, rgba(245, 158, 11, 0.1) 0%, rgba(217, 119, 6, 0.05) 100%)',
            border: '1px solid rgba(245, 158, 11, 0.25)',
            fontSize: 12.5,
            color: 'var(--ink, #0F172A)',
            lineHeight: 1.5,
          }}
        >
          <strong style={{ color: '#D97706', display: 'block', marginBottom: 2 }}>
            💡 Tushuntirish:
          </strong>
          <span>{q.explanation}</span>
        </div>
      )}
    </div>
  );
}
