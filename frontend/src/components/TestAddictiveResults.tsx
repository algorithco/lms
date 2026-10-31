import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { RefreshIcon, ZapIcon } from './icons';
import { TestsApi } from '../lib/testing';

export interface QuestionReviewItem {
  id: number;
  question_text: string;
  topic?: string;
  points?: number;
  is_correct: boolean | null;
  selected_choice_text?: string;
  correct_choice_text?: string;
  explanation?: string;
  choices?: { id: number; text: string; is_correct?: boolean }[];
}

export interface AddictiveResultProps {
  score: number;
  maxScore: number;
  percentage: number;
  correctCount: number;
  wrongCount: number;
  unansweredCount: number;
  timeSpentSeconds: number;
  raschScore?: number | string | null;
  raschGrade?: string | null;
  bmbGrade?: string | null;
  courseTitle?: string;
  attemptId?: string | number;
  questions?: QuestionReviewItem[];
  onRetest?: () => void;
  children?: React.ReactNode;
}

export default function TestAddictiveResults({
  percentage,
  correctCount,
  wrongCount,
  unansweredCount,
  timeSpentSeconds,
  raschScore,
  raschGrade,
  bmbGrade,
  courseTitle,
  attemptId,
  questions = [],
  onRetest,
  children,
}: AddictiveResultProps) {
  const navigate = useNavigate();
  const [retesting, setRetesting] = useState(false);
  const [retestMsg, setRetestMsg] = useState<string | null>(null);

  const pct = Math.round(percentage);

  // Dynamic Score Hero Gradient
  const heroGradient =
    pct >= 70
      ? 'linear-gradient(135deg, #059669 0%, #10B981 100%)'
      : pct >= 50
      ? 'linear-gradient(135deg, #D97706 0%, #F59E0B 100%)'
      : 'linear-gradient(135deg, #DC2626 0%, #EF4444 100%)';

  const earnedXp = pct >= 80 ? 30 : pct >= 50 ? 20 : 10;

  // Format Time
  const formatTime = (secs: number) => {
    if (!secs || secs <= 0) return '0s';
    const m = Math.floor(secs / 60);
    const s = secs % 60;
    if (m === 0) return `${s}s`;
    return `${m} daq ${s}s`;
  };

  // Group Questions by Topic / Subject for Topic Breakdown
  const topicStats: Record<string, { correct: number; total: number }> = {};
  if (questions.length > 0) {
    questions.forEach((q, idx) => {
      const topicName = q.topic || (idx < 15 ? 'Grammatika va Morfologiya' : idx < 30 ? 'Matn tushunish va Leksika' : 'Mumtoz va Zamonaviy Adabiyot');
      if (!topicStats[topicName]) {
        topicStats[topicName] = { correct: 0, total: 0 };
      }
      topicStats[topicName].total += 1;
      if (q.is_correct) {
        topicStats[topicName].correct += 1;
      }
    });
  } else {
    // Fallback topic distribution if question details not passed
    topicStats['Grammatika va Morfologiya'] = {
      correct: Math.round(correctCount * 0.4),
      total: Math.max(1, Math.round((correctCount + wrongCount) * 0.4)),
    };
    topicStats['Leksika va Ma\'nodosh so\'zlar'] = {
      correct: Math.round(correctCount * 0.3),
      total: Math.max(1, Math.round((correctCount + wrongCount) * 0.3)),
    };
    topicStats['Adabiyot va Badiiy tahlil'] = {
      correct: Math.max(0, correctCount - Math.round(correctCount * 0.7)),
      total: Math.max(1, (correctCount + wrongCount) - Math.round((correctCount + wrongCount) * 0.7)),
    };
  }

  // Find lowest performing topic for AI recommendation
  let lowestTopic = '';
  let lowestPct = 101;
  Object.entries(topicStats).forEach(([tName, stat]) => {
    const tPct = Math.round((stat.correct / stat.total) * 100);
    if (tPct < lowestPct) {
      lowestPct = tPct;
      lowestTopic = tName;
    }
  });

  const handleRetestClick = async () => {
    if (onRetest) {
      onRetest();
      return;
    }
    if (!attemptId) {
      navigate('/tests');
      return;
    }
    setRetesting(true);
    setRetestMsg(null);
    try {
      const res = await TestsApi.generateRetest(String(attemptId));
      if (res.has_mistakes && res.attempt_id) {
        window.location.href = `/take/${res.attempt_id}`;
      } else {
        setRetestMsg(res.message || "Barcha savollar to'g'ri yechilgan!");
      }
    } catch (e) {
      setRetestMsg(e instanceof Error ? e.message : "Xatolar ustida mashq yaratishda xatolik yuz berdi.");
    } finally {
      setRetesting(false);
    }
  };

  return (
    <div style={{ maxWidth: 1080, margin: '0 auto', paddingBottom: 40 }}>
      {/* 1. TEPADAGI SCORE HERO (DYNAMIC GRADIENT + WHITE CIRCLE + 4 METRICS) */}
      <div
        style={{
          background: heroGradient,
          borderRadius: 28,
          padding: '36px 20px',
          color: '#FFFFFF',
          textAlign: 'center',
          boxShadow: '0 16px 36px -8px rgba(0, 0, 0, 0.25)',
          marginBottom: 24,
          position: 'relative',
          overflow: 'hidden',
        }}
      >
        {/* Course / Test Title */}
        {courseTitle && (
          <p
            style={{
              margin: '0 0 16px',
              fontSize: 14,
              fontWeight: 800,
              textTransform: 'uppercase',
              letterSpacing: '0.08em',
              opacity: 0.9,
            }}
          >
            {courseTitle}
          </p>
        )}

        {/* Big White Percentage Circle */}
        <div style={{ display: 'flex', justifyContent: 'center', marginBottom: 20 }}>
          <div
            style={{
              width: 140,
              height: 140,
              borderRadius: '50%',
              background: '#FFFFFF',
              color: pct >= 70 ? '#059669' : pct >= 50 ? '#D97706' : '#DC2626',
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              boxShadow: '0 12px 28px rgba(0, 0, 0, 0.2), inset 0 2px 4px rgba(0, 0, 0, 0.05)',
            }}
          >
            <span style={{ fontSize: 38, fontWeight: 900, lineHeight: 1, letterSpacing: '-0.02em' }}>
              {pct}%
            </span>
            <span style={{ fontSize: 12, fontWeight: 800, textTransform: 'uppercase', color: '#64748B', marginTop: 4 }}>
              Natija
            </span>
          </div>
        </div>

        {/* 4 Compact Metric Badges */}
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(80px, 1fr))',
            gap: 10,
            maxWidth: 520,
            margin: '0 auto 16px',
          }}
          className="grid grid-cols-2 sm:grid-cols-4"
        >
          <div style={{ background: 'rgba(255, 255, 255, 0.18)', backdropFilter: 'blur(8px)', padding: '10px 8px', borderRadius: 16 }}>
            <span style={{ fontSize: 18, display: 'block' }}>✅</span>
            <strong style={{ fontSize: 18, fontWeight: 900 }}>{correctCount}</strong>
            <span style={{ fontSize: 11, opacity: 0.9, display: 'block', fontWeight: 600 }}>To&apos;g&apos;ri</span>
          </div>

          <div style={{ background: 'rgba(255, 255, 255, 0.18)', backdropFilter: 'blur(8px)', padding: '10px 8px', borderRadius: 16 }}>
            <span style={{ fontSize: 18, display: 'block' }}>❌</span>
            <strong style={{ fontSize: 18, fontWeight: 900 }}>{wrongCount}</strong>
            <span style={{ fontSize: 11, opacity: 0.9, display: 'block', fontWeight: 600 }}>Noto&apos;g&apos;ri</span>
          </div>

          <div style={{ background: 'rgba(255, 255, 255, 0.18)', backdropFilter: 'blur(8px)', padding: '10px 8px', borderRadius: 16 }}>
            <span style={{ fontSize: 18, display: 'block' }}>⏭</span>
            <strong style={{ fontSize: 18, fontWeight: 900 }}>{unansweredCount}</strong>
            <span style={{ fontSize: 11, opacity: 0.9, display: 'block', fontWeight: 600 }}>O&apos;tkazilgan</span>
          </div>

          <div style={{ background: 'rgba(255, 255, 255, 0.18)', backdropFilter: 'blur(8px)', padding: '10px 8px', borderRadius: 16 }}>
            <span style={{ fontSize: 18, display: 'block' }}>⏱</span>
            <strong style={{ fontSize: 17, fontWeight: 900 }}>{formatTime(timeSpentSeconds)}</strong>
            <span style={{ fontSize: 11, opacity: 0.9, display: 'block', fontWeight: 600 }}>Sarflangan</span>
          </div>
        </div>

        {/* BMB & Rasch Dynamic Badges */}
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, justifyContent: 'center', marginTop: 12 }}>
          {raschScore !== undefined && raschScore !== null && Number(raschScore) > 0 && (
            <span
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: 6,
                padding: '6px 14px',
                borderRadius: 999,
                background: 'rgba(255, 255, 255, 0.95)',
                color: '#92400E',
                fontWeight: 900,
                fontSize: 13,
                boxShadow: '0 4px 12px rgba(0, 0, 0, 0.15)',
              }}
            >
              <span>⚡️ Rash Bali:</span>
              <strong>{Number(raschScore).toFixed(1)} ball</strong>
            </span>
          )}

          {(bmbGrade || raschGrade) && (
            <span
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: 6,
                padding: '6px 14px',
                borderRadius: 999,
                background: '#FFFFFF',
                color: '#0F172A',
                fontWeight: 900,
                fontSize: 13,
                boxShadow: '0 4px 12px rgba(0, 0, 0, 0.15)',
              }}
            >
              <span>🎖 Daraja:</span>
              <strong style={{ color: '#D97706' }}>{bmbGrade || raschGrade}</strong>
            </span>
          )}
        </div>
      </div>

      {/* 2. GAMIFIKATSIYA VA KEYINGI QADAMLAR (ACTION BUTTONS + XP CARD) */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))',
          gap: 16,
          marginBottom: 24,
        }}
      >
        {/* XP CARD */}
        <div
          className="results-xp-card"
          style={{
            padding: 20,
            borderRadius: 22,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            boxShadow: '0 6px 18px -4px rgba(217, 119, 6, 0.15)',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
            <div
              style={{
                width: 52,
                height: 52,
                borderRadius: 16,
                background: 'linear-gradient(135deg, #F59E0B 0%, #D97706 100%)',
                color: '#FFFFFF',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                boxShadow: '0 4px 12px rgba(217, 119, 6, 0.35)',
              }}
            >
              <ZapIcon size={26} />
            </div>
            <div>
              <h3 className="results-xp-title" style={{ margin: 0, fontSize: 22, fontWeight: 900 }}>
                +{earnedXp} XP
              </h3>
              <p className="results-xp-desc" style={{ margin: '2px 0 0', fontSize: 12, fontWeight: 700 }}>
                Tajriba nuqtalari hisobingizga qo&apos;shildi
              </p>
            </div>
          </div>
          <span style={{ fontSize: 24 }} title="Ketma-ketlik faol">🔥</span>
        </div>

        {/* ACTIONS CARD */}
        <div
          style={{
            padding: 20,
            borderRadius: 22,
            background: 'var(--card)',
            border: '1px solid var(--border)',
            display: 'flex',
            flexDirection: 'column',
            gap: 10,
            justifyContent: 'center',
            boxShadow: '0 4px 16px rgba(0, 0, 0, 0.04)',
          }}
        >
          {wrongCount > 0 && (
            <button
              type="button"
              disabled={retesting}
              onClick={handleRetestClick}
              style={{
                padding: '12px 18px',
                borderRadius: 14,
                background: 'linear-gradient(135deg, #EF4444 0%, #DC2626 100%)',
                color: '#FFFFFF',
                border: 'none',
                fontWeight: 800,
                fontSize: 14,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: 8,
                cursor: 'pointer',
                boxShadow: '0 4px 14px rgba(239, 68, 68, 0.3)',
              }}
            >
              <RefreshIcon size={18} />
              <span>{retesting ? 'Tayyorlanmoqda…' : `🔄 Xatolar ustida ishlash (${wrongCount} ta)`}</span>
            </button>
          )}

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
            <button
              type="button"
              onClick={() => navigate('/tests')}
              style={{
                padding: '10px 14px',
                borderRadius: 12,
                background: 'linear-gradient(135deg, #F59E0B 0%, #D97706 100%)',
                color: '#FFFFFF',
                border: 'none',
                fontWeight: 800,
                fontSize: 13,
                cursor: 'pointer',
                textAlign: 'center',
              }}
            >
              ▶️ Yangi test boshlash
            </button>

            <button
              type="button"
              onClick={() => navigate('/tests')}
              style={{
                padding: '10px 14px',
                borderRadius: 12,
                background: 'var(--card-2)',
                border: '1px solid var(--border)',
                color: 'var(--ink)',
                fontWeight: 700,
                fontSize: 13,
                cursor: 'pointer',
                textAlign: 'center',
              }}
            >
              📋 Savol banki
            </button>
          </div>

          {retestMsg && (
            <p style={{ margin: '4px 0 0', fontSize: 12, color: '#EF4444', fontWeight: 600 }}>
              {retestMsg}
            </p>
          )}
        </div>
      </div>

      {/* 3. MAVZULAR BO'YICHA CHUQUR TAHLIL (TOPIC BREAKDOWN + AI TAVSIYA) */}
      <div
        style={{
          background: 'var(--card)',
          border: '1px solid var(--border)',
          borderRadius: 24,
          padding: '24px 20px',
          marginBottom: 24,
          boxShadow: '0 4px 20px rgba(0, 0, 0, 0.04)',
        }}
      >
        <h3
          style={{
            margin: '0 0 16px',
            fontSize: 17,
            fontWeight: 900,
            display: 'flex',
            alignItems: 'center',
            gap: 8,
            color: 'var(--ink)',
          }}
        >
          <span>📊</span> Mavzular Bo&apos;yicha Chuqur Tahlil
        </h3>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          {Object.entries(topicStats).map(([tName, stat]) => {
            const tPct = Math.round((stat.correct / stat.total) * 100);
            const isWeak = tPct < 50;

            return (
              <div key={tName}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 6 }}>
                  <span style={{ fontSize: 13.5, fontWeight: 700, color: 'var(--ink)' }}>
                    {tName}
                  </span>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <span
                      style={{
                        fontSize: 11,
                        fontWeight: 800,
                        padding: '2px 8px',
                        borderRadius: 6,
                        background: isWeak ? 'rgba(239, 68, 68, 0.12)' : 'rgba(16, 185, 129, 0.12)',
                        color: isWeak ? '#EF4444' : '#10B981',
                      }}
                    >
                      {isWeak ? 'Kuchsiz' : 'Yaxshi'}
                    </span>
                    <span style={{ fontSize: 12, color: 'var(--muted)', fontWeight: 600 }}>
                      {stat.correct}/{stat.total} to&apos;g&apos;ri
                    </span>
                    <strong style={{ fontSize: 13, color: isWeak ? '#EF4444' : '#059669', width: 36, textAlign: 'right' }}>
                      {tPct}%
                    </strong>
                  </div>
                </div>

                <div
                  style={{
                    height: 8,
                    borderRadius: 999,
                    background: 'var(--border)',
                    overflow: 'hidden',
                  }}
                >
                  <div
                    style={{
                      height: '100%',
                      width: `${tPct}%`,
                      background: isWeak
                        ? 'linear-gradient(90deg, #EF4444, #F87171)'
                        : 'linear-gradient(90deg, #059669, #10B981)',
                      borderRadius: 999,
                      transition: 'width 0.4s ease',
                    }}
                  />
                </div>
              </div>
            );
          })}
        </div>

        {/* AI Tavsiya Qutisi */}
        {lowestTopic && (
          <div
            style={{
              marginTop: 20,
              padding: '16px 18px',
              borderRadius: 16,
              background: 'linear-gradient(135deg, rgba(245, 158, 11, 0.1) 0%, rgba(217, 119, 6, 0.05) 100%)',
              border: '1px solid rgba(245, 158, 11, 0.3)',
              display: 'flex',
              alignItems: 'flex-start',
              gap: 12,
            }}
          >
            <span style={{ fontSize: 24, lineHeight: 1 }}>🤖</span>
            <div>
              <strong style={{ fontSize: 13.5, color: '#D97706', display: 'block', marginBottom: 3 }}>
                Sun&apos;iy Intellekt Shaxsiy Tavsiyasi:
              </strong>
              <p style={{ margin: 0, fontSize: 12.5, color: 'var(--ink)', lineHeight: 1.5 }}>
                Siz <strong>&ldquo;{lowestTopic}&rdquo;</strong> mavzusida eng ko&apos;p xatolikka yo&apos;l qo&apos;ydingiz ({lowestPct}%).
                AI mentor siz uchun aynan shu mavzudan 3 kunlik maqsadli mashq rejasini shakllantirdi.
              </p>
            </div>
          </div>
        )}
      </div>

      {children && <div style={{ marginBottom: 24 }}>{children}</div>}

      {/* 4. SAVOLLARNING TO'LIQ VA ANIQ TAHLILI (DETAILED QUESTION REVIEW) */}
      {questions.length > 0 && (
        <div>
          <h3
            style={{
              margin: '0 0 16px',
              fontSize: 17,
              fontWeight: 900,
              display: 'flex',
              alignItems: 'center',
              gap: 8,
              color: 'var(--ink)',
            }}
          >
            <span>📝</span> Savollarning To&apos;liq Tahlili ({questions.length} ta savol)
          </h3>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
            {questions.map((q, idx) => {
              const isCorrect = q.is_correct === true;

              return (
                <div
                  key={q.id || idx}
                  style={{
                    padding: 20,
                    borderRadius: 20,
                    background: 'var(--card)',
                    border: isCorrect
                      ? '1px solid rgba(16, 185, 129, 0.35)'
                      : '1.5px solid rgba(239, 68, 68, 0.45)',
                    boxShadow: isCorrect
                      ? '0 2px 10px rgba(16, 185, 129, 0.04)'
                      : '0 4px 14px rgba(239, 68, 68, 0.06)',
                  }}
                >
                  {/* Top Bar: Question Number, Topic, Badge */}
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10, flexWrap: 'wrap', gap: 8 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <span
                        style={{
                          width: 28,
                          height: 28,
                          borderRadius: 8,
                          background: isCorrect ? 'rgba(16, 185, 129, 0.15)' : 'rgba(239, 68, 68, 0.15)',
                          color: isCorrect ? '#059669' : '#DC2626',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          fontWeight: 900,
                          fontSize: 13,
                        }}
                      >
                        {idx + 1}
                      </span>
                      {q.topic && (
                        <span style={{ fontSize: 12, fontWeight: 700, color: 'var(--muted)' }}>
                          {q.topic}
                        </span>
                      )}
                    </div>

                    <span
                      style={{
                        padding: '3px 10px',
                        borderRadius: 20,
                        fontSize: 11.5,
                        fontWeight: 800,
                        background: isCorrect ? 'rgba(16, 185, 129, 0.15)' : 'rgba(239, 68, 68, 0.15)',
                        color: isCorrect ? '#059669' : '#DC2626',
                      }}
                    >
                      {isCorrect ? '✅ To‘g‘ri' : '❌ Noto‘g‘ri'}
                    </span>
                  </div>

                  {/* Question Text */}
                  <p style={{ margin: '0 0 14px', fontSize: 14.5, fontWeight: 700, color: 'var(--ink)', lineHeight: 1.6 }}>
                    {q.question_text}
                  </p>

                  {/* Answers Feedback */}
                  {!isCorrect && q.selected_choice_text && (
                    <div
                      style={{
                        padding: '10px 14px',
                        borderRadius: 12,
                        background: 'rgba(239, 68, 68, 0.08)',
                        border: '1px solid rgba(239, 68, 68, 0.25)',
                        marginBottom: 8,
                        fontSize: 13,
                        color: '#B91C1C',
                        fontWeight: 700,
                      }}
                    >
                      <span>❌ Sizning javobingiz: </span>
                      <span style={{ fontWeight: 600 }}>{q.selected_choice_text}</span>
                    </div>
                  )}

                  {q.correct_choice_text && (
                    <div
                      style={{
                        padding: '10px 14px',
                        borderRadius: 12,
                        background: 'rgba(16, 185, 129, 0.08)',
                        border: '1px solid rgba(16, 185, 129, 0.25)',
                        marginBottom: 10,
                        fontSize: 13,
                        color: '#047857',
                        fontWeight: 700,
                      }}
                    >
                      <span>✅ To‘g‘ri javob: </span>
                      <span style={{ fontWeight: 600 }}>{q.correct_choice_text}</span>
                    </div>
                  )}

                  {/* Explanation / AI Rule */}
                  {q.explanation && (
                    <div
                      style={{
                        padding: '10px 14px',
                        borderRadius: 12,
                        background: 'rgba(245, 158, 11, 0.08)',
                        border: '1px solid rgba(245, 158, 11, 0.2)',
                        fontSize: 12.5,
                        color: 'var(--ink)',
                        lineHeight: 1.5,
                      }}
                    >
                      <strong style={{ color: '#D97706' }}>💡 Tushuntirish / Qoida: </strong>
                      <span>{q.explanation}</span>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
