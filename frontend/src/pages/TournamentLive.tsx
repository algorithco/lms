import { useEffect, useRef, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { api } from '../lib/api';
import { useAuth } from '../auth/AuthContext';
import { ClockIcon, TrophyIcon, ArrowLeftIcon } from '../components/icons';

interface LeaderboardEntry {
  rank: number;
  user_id: number;
  name: string;
  score: number;
  correct_answers: number;
  total_questions: number;
  time_taken_seconds: number;
  is_finished: boolean;
}

interface QuestionItem {
  id: number;
  text: string;
  options: { [key: string]: string };
  order: number;
}

interface TournamentDetails {
  id: number;
  title: string;
  description: string;
  scheduled_at: string;
  duration_minutes: number;
  status: 'upcoming' | 'live' | 'finished';
  prize_fund_description: string;
  participants_count: number;
  questions_count: number;
}

export default function TournamentLive() {
  const { id } = useParams<{ id: string }>();
  const { user } = useAuth();

  const [tournament, setTournament] = useState<TournamentDetails | null>(null);
  const [questions, setQuestions] = useState<QuestionItem[]>([]);
  const [leaderboard, setLeaderboard] = useState<LeaderboardEntry[]>([]);
  const [loading, setLoading] = useState(true);

  // User test state
  const [currentQIndex, setCurrentQIndex] = useState(0);
  const [selectedAnswers, setSelectedAnswers] = useState<{ [qId: number]: string }>({});
  const [isSubmitted, setIsSubmitted] = useState(false);
  const [myResult, setMyResult] = useState<{ score: number; rank: number | null; correct: number } | null>(null);
  const [submitting, setSubmitting] = useState(false);

  // Timer
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  const socketRef = useRef<WebSocket | null>(null);

  // Load tournament data
  const loadData = async () => {
    try {
      const res = await api.get<{
        tournament: TournamentDetails;
        questions: QuestionItem[];
        leaderboard: LeaderboardEntry[];
        my_participation: { score: number; rank: number | null; is_finished: boolean } | null;
      }>(`/tournaments/${id}/`);

      setTournament(res.tournament);
      setQuestions(res.questions || []);
      setLeaderboard(res.leaderboard || []);

      if (res.my_participation && res.my_participation.is_finished) {
        setIsSubmitted(true);
        setMyResult({
          score: res.my_participation.score,
          rank: res.my_participation.rank,
          correct: 0,
        });
      }
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadData();

    // Auto-join if user is logged in
    if (user && id) {
      api.post(`/tournaments/${id}/join/`).catch(() => {});
    }

    // Connect to WebSocket with HTTP polling fallback
    const wsProto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${wsProto}//${window.location.host}/ws/tournaments/${id}/`;

    try {
      const ws = new WebSocket(wsUrl);
      socketRef.current = ws;

      ws.onmessage = (event) => {
        try {
          const payload = JSON.parse(event.data);
          if (payload.type === 'init' || payload.type === 'leaderboard_update') {
            if (payload.leaderboard) {
              setLeaderboard(payload.leaderboard);
            }
          }
        } catch {
          // ignore
        }
      };
    } catch {
      // WebSocket fallback
    }

    // Leaderboard backup polling every 5s
    const pollInterval = setInterval(async () => {
      try {
        const res = await api.get<{ leaderboard: LeaderboardEntry[] }>(`/tournaments/${id}/leaderboard/`);
        if (res.leaderboard) {
          setLeaderboard(res.leaderboard);
        }
      } catch {
        // ignore
      }
    }, 5000);

    return () => {
      clearInterval(pollInterval);
      if (socketRef.current) {
        socketRef.current.close();
      }
    };
  }, [id, user]);

  // Timer effect
  useEffect(() => {
    if (isSubmitted) return;
    const timer = setInterval(() => {
      setElapsedSeconds((prev) => prev + 1);
    }, 1000);
    return () => clearInterval(timer);
  }, [isSubmitted]);

  const handleSelectOption = (qId: number, optKey: string) => {
    if (isSubmitted) return;
    setSelectedAnswers((prev) => ({ ...prev, [qId]: optKey }));
  };

  const handleSubmit = async () => {
    if (!confirm("Barcha savollarga javob berib, natijani tasdiqlamoqchimisiz?")) return;
    setSubmitting(true);
    try {
      const res = await api.post<{
        result: { score: number; rank: number | null; correct_answers: number };
        leaderboard: LeaderboardEntry[];
      }>(`/tournaments/${id}/submit/`, {
        answers: selectedAnswers,
        time_taken_seconds: elapsedSeconds,
      });

      setIsSubmitted(true);
      setMyResult({
        score: res.result.score,
        rank: res.result.rank,
        correct: res.result.correct_answers,
      });
      if (res.leaderboard) {
        setLeaderboard(res.leaderboard);
      }
    } catch (err: any) {
      alert(err?.response?.data?.error || "Xatolik yuz berdi");
    } finally {
      setSubmitting(false);
    }
  };

  if (loading || !tournament) {
    return <div className="card" style={{ padding: 40, textAlign: 'center' }}>Turnir xonasi yuklanmoqda...</div>;
  }

  const currentQ = questions[currentQIndex];

  return (
    <div style={{ maxWidth: 1200, margin: '0 auto', paddingBottom: 60 }}>
      {/* Top Header Bar */}
      <div
        className="card"
        style={{
          padding: '16px 24px',
          borderRadius: 16,
          marginBottom: 20,
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          flexWrap: 'wrap',
          gap: 12,
          background: 'linear-gradient(135deg, var(--card), var(--card-2))',
          border: '1px solid var(--border)',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <Link to="/tournaments" style={{ color: 'var(--muted)', textDecoration: 'none', display: 'flex', alignItems: 'center' }}>
            <ArrowLeftIcon size={18} />
          </Link>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <span style={{ background: '#ef4444', color: '#fff', fontSize: 10, fontWeight: 900, padding: '2px 6px', borderRadius: 4 }}>
                LIVE
              </span>
              <h1 style={{ fontSize: 18, margin: 0, fontWeight: 800 }}>{tournament.title}</h1>
            </div>
            <span className="muted small">Real-vaqt e-Sport reytingi va avtomatik mukofotlar</span>
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 15, fontWeight: 700, color: 'var(--accent)' }}>
            <ClockIcon size={18} />
            <span>
              {Math.floor(elapsedSeconds / 60)}:{(elapsedSeconds % 60).toString().padStart(2, '0')}
            </span>
          </div>

          <div style={{ padding: '6px 12px', borderRadius: 8, background: 'rgba(245, 158, 11, 0.15)', color: 'var(--accent-dark)', fontSize: 13, fontWeight: 800 }}>
            {tournament.participants_count} ishtirokchi
          </div>
        </div>
      </div>

      {/* Main Grid: Test on Left (60%), Live Leaderboard on Right (40%) */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(340px, 1fr))', gap: 20 }}>
        {/* Left: Test Questions Panel */}
        <div className="card" style={{ padding: 24, borderRadius: 16 }}>
          {isSubmitted ? (
            <div style={{ textAlign: 'center', padding: '30px 10px' }}>
              <div style={{ fontSize: 50, marginBottom: 12 }}>🎉</div>
              <h2 style={{ fontSize: 24, fontWeight: 900, margin: '0 0 8px' }}>Test topshirildi!</h2>
              <p className="muted" style={{ margin: '0 0 20px' }}>
                Natijangiz hisoblandi va jonli reyting jadvaliga kiritildi.
              </p>

              <div
                style={{
                  display: 'inline-flex',
                  gap: 20,
                  padding: '16px 24px',
                  borderRadius: 16,
                  background: 'var(--card-2)',
                  border: '1px solid var(--border)',
                  marginBottom: 20,
                }}
              >
                <div>
                  <span className="muted small" style={{ display: 'block' }}>To'plangan ball</span>
                  <strong style={{ fontSize: 22, color: 'var(--accent)' }}>{myResult?.score || 0}%</strong>
                </div>
                <div>
                  <span className="muted small" style={{ display: 'block' }}>Joriy o'rningiz</span>
                  <strong style={{ fontSize: 22, color: '#10b981' }}>#{myResult?.rank || '—'}</strong>
                </div>
              </div>

              <p className="muted small" style={{ margin: 0 }}>
                Turnir yakunlangach, g'oliblar (1-, 2-, 3-o'rinlar) ga bepul obunalar va kubok nishonlari avtomatik beriladi!
              </p>
            </div>
          ) : questions.length === 0 ? (
            <div style={{ textAlign: 'center', padding: 40 }} className="muted">
              Ushbu turnir uchun savollar tez orada boshlanadi.
            </div>
          ) : currentQ ? (
            <div>
              {/* Question Navigation Bubbles */}
              <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 20 }}>
                {questions.map((q, idx) => {
                  const isAnswered = selectedAnswers[q.id] !== undefined;
                  const isCurrent = idx === currentQIndex;

                  return (
                    <button
                      key={q.id}
                      type="button"
                      onClick={() => setCurrentQIndex(idx)}
                      style={{
                        width: 32,
                        height: 32,
                        borderRadius: 8,
                        border: isCurrent ? '2px solid var(--accent)' : '1px solid var(--border)',
                        background: isAnswered ? '#10b981' : isCurrent ? 'var(--card-2)' : 'transparent',
                        color: isAnswered ? '#fff' : 'var(--ink)',
                        fontSize: 12,
                        fontWeight: 700,
                        cursor: 'pointer',
                      }}
                    >
                      {idx + 1}
                    </button>
                  );
                })}
              </div>

              {/* Current Question */}
              <div style={{ marginBottom: 24 }}>
                <span className="muted small" style={{ fontWeight: 700 }}>
                  Savol {currentQIndex + 1} / {questions.length}:
                </span>
                <p style={{ fontSize: 16, fontWeight: 700, marginTop: 8, lineHeight: 1.6 }}>{currentQ.text}</p>
              </div>

              {/* Options */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: 10, marginBottom: 24 }}>
                {['A', 'B', 'C', 'D'].map((key) => {
                  const optText = currentQ.options[key];
                  if (!optText) return null;
                  const isSelected = selectedAnswers[currentQ.id] === key;

                  return (
                    <button
                      key={key}
                      type="button"
                      onClick={() => handleSelectOption(currentQ.id, key)}
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: 12,
                        padding: '12px 16px',
                        borderRadius: 12,
                        border: isSelected ? '2px solid var(--accent)' : '1px solid var(--border)',
                        background: isSelected ? 'rgba(245, 158, 11, 0.12)' : 'var(--card)',
                        color: 'var(--ink)',
                        textAlign: 'left',
                        cursor: 'pointer',
                        transition: 'all 0.15s ease',
                      }}
                    >
                      <span
                        style={{
                          width: 28,
                          height: 28,
                          borderRadius: 6,
                          background: isSelected ? 'var(--accent)' : 'var(--card-2)',
                          color: isSelected ? '#fff' : 'var(--ink)',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          fontWeight: 800,
                          fontSize: 13,
                          flexShrink: 0,
                        }}
                      >
                        {key}
                      </span>
                      <span style={{ fontSize: 14, flex: 1 }}>{optText}</span>
                    </button>
                  );
                })}
              </div>

              {/* Navigation controls */}
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <button
                  type="button"
                  disabled={currentQIndex === 0}
                  onClick={() => setCurrentQIndex((i) => Math.max(0, i - 1))}
                  className="btn secondary"
                >
                  ← Oldingi
                </button>

                {currentQIndex === questions.length - 1 ? (
                  <button
                    type="button"
                    disabled={submitting}
                    onClick={handleSubmit}
                    className="btn primary btn-glow"
                    style={{ fontWeight: 800 }}
                  >
                    {submitting ? "Topshirilmoqda..." : "Turnirni yakunlash ✓"}
                  </button>
                ) : (
                  <button
                    type="button"
                    onClick={() => setCurrentQIndex((i) => Math.min(questions.length - 1, i + 1))}
                    className="btn primary"
                  >
                    Keyingi →
                  </button>
                )}
              </div>
            </div>
          ) : null}
        </div>

        {/* Right: Real-time Live E-Sport Leaderboard */}
        <div className="card" style={{ padding: 24, borderRadius: 16 }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
            <h2 style={{ fontSize: 18, margin: 0, display: 'flex', alignItems: 'center', gap: 8, fontWeight: 900 }}>
              <TrophyIcon size={20} style={{ color: 'var(--accent)' }} /> Jonli E-Sport Reytingi
            </h2>
            <span style={{ fontSize: 11, fontWeight: 700, color: '#10b981', display: 'flex', alignItems: 'center', gap: 4 }}>
              <span style={{ width: 8, height: 8, borderRadius: '50%', background: '#10b981', display: 'inline-block' }}></span>
              Jonli yangilanmoqda
            </span>
          </div>

          {leaderboard.length === 0 ? (
            <div className="muted small" style={{ textAlign: 'center', padding: 20 }}>
              Hali natijalar kiritilmadi. Birinchi bo'lib testni yakunlang!
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8, maxHeight: 540, overflowY: 'auto' }}>
              <AnimatePresence>
                {leaderboard.map((entry) => {
                  const isMe = user && entry.user_id === user.id;
                  const badge = entry.rank === 1 ? '🥇' : entry.rank === 2 ? '🥈' : entry.rank === 3 ? '🥉' : null;

                  return (
                    <motion.div
                      key={entry.user_id}
                      layout
                      initial={{ opacity: 0, y: 10 }}
                      animate={{ opacity: 1, y: 0 }}
                      exit={{ opacity: 0 }}
                      transition={{ type: 'spring', stiffness: 350, damping: 25 }}
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                        padding: '10px 14px',
                        borderRadius: 12,
                        background: isMe ? 'rgba(245, 158, 11, 0.18)' : 'var(--card-2)',
                        border: isMe ? '2px solid var(--accent)' : '1px solid var(--border)',
                      }}
                    >
                      <div style={{ display: 'flex', alignItems: 'center', gap: 10, minWidth: 0 }}>
                        <span
                          style={{
                            width: 28,
                            fontSize: 14,
                            fontWeight: 900,
                            textAlign: 'center',
                            color: entry.rank <= 3 ? 'var(--accent)' : 'var(--muted)',
                          }}
                        >
                          {badge || `#${entry.rank}`}
                        </span>

                        <div style={{ minWidth: 0 }}>
                          <strong
                            style={{
                              display: 'block',
                              fontSize: 13,
                              whiteSpace: 'nowrap',
                              overflow: 'hidden',
                              textOverflow: 'ellipsis',
                              color: isMe ? 'var(--accent-dark)' : 'var(--ink)',
                            }}
                          >
                            {entry.name} {isMe && '(Siz)'}
                          </strong>
                          <span className="muted small" style={{ fontSize: 11 }}>
                            {entry.is_finished ? `✓ Yakunladi (${entry.time_taken_seconds} sek)` : "Javob bermoqda..."}
                          </span>
                        </div>
                      </div>

                      <div style={{ textAlign: 'right' }}>
                        <strong style={{ fontSize: 15, color: 'var(--accent)' }}>{entry.score}%</strong>
                        <span className="muted small" style={{ display: 'block', fontSize: 10 }}>
                          {entry.correct_answers}/{entry.total_questions || '?'} to'g'ri
                        </span>
                      </div>
                    </motion.div>
                  );
                })}
              </AnimatePresence>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
