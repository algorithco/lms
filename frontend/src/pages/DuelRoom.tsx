import { useCallback, useEffect, useRef, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { useLang } from '../i18n/LangContext';
import { arenaSocketUrl } from '../lib/api';
import { useAuth } from '../auth/AuthContext';
import { FlameIcon, SwordsIcon, TrophyIcon } from '../components/icons';
import confetti from 'canvas-confetti';
import {
  arenaOpponentRows,
  arenaRowOf,
  arenaScoreOf,
  normalizeArenaScores,
} from '../lib/essays-arena';
import type { ArenaScoreRow } from '../lib/essays-arena';

/**
 * Duel room — real-time 1v1 quiz duel over Django Channels.
 *
 * Auth: the WS consumer authenticates via SimpleJWT access token in query string
 * or header; close code 4001 means "not logged in".
 *
 * Protocol (apps/arena/consumers.py + templates/arena/duel_room.html):
 *   → join_room {room_code} · submit_answer {room_code, answer, question_index}
 *     · leave_room
 *   ← connected {user_id} · room_joined {player1, player2, total_questions,
 *     time_per_question, current_question_index, is_bot_duel, status} ·
 *     match_found {room_code, player1, player2, total_questions} ·
 *     queue_update {message, position} · send_question {question_index,
 *     question{question_text, option_a..d, points}, time_limit} ·
 *     answer_result {is_correct, points, base_points, combo_bonus,
 *     time_bonus, correct_answer, streak} · live_score_update {scores[],
 *     answered_by} (scores is a LIST — see services.get_scores) ·
 *     game_over {winner, winner_id, scores[], mode} · error {message}
 *
 * The correct answer is NEVER in send_question — reveal comes only from
 * answer_result. Server timer is authoritative; expiry only locks the
 * options locally. Reconnect mirrors the legacy page (retry after 3s).
 */

type State =
  | 'session'
  | 'connecting'
  | 'waiting'
  | 'countdown'
  | 'playing'
  | 'gameover'
  | 'error';

interface DuelPlayer {
  id: number | null;
  name: string;
  is_bot?: boolean;
}

interface Question {
  question_text: string;
  option_a: string;
  option_b: string;
  option_c: string;
  option_d: string;
  points: number;
}

const OPTS = ['a', 'b', 'c', 'd'] as const;
const COUNTDOWN_FROM = 3;
const BACKOFF_DELAYS = [1000, 2000, 5000];
const MAX_RECONNECTS = 8;

export default function DuelRoom() {
  const { code = '' } = useParams();
  const navigate = useNavigate();
  const { t } = useLang();
  const { user, loading: authLoading } = useAuth();

  const [state, setState] = useState<State>('session');
  const [notice, setNotice] = useState('');
  const [question, setQuestion] = useState<Question | null>(null);
  const [qIndex, setQIndex] = useState(0);
  const [total, setTotal] = useState(10);
  const [timeLeft, setTimeLeft] = useState(15);
  // per-question limit from the server (kept for reset/progress; timeLeft drives the countdown)
  const [, setTimeLimit] = useState(15);
  const [rows, setRows] = useState<ArenaScoreRow[]>([]);
  const [myId, setMyId] = useState<number | null>(null);
  const [p1, setP1] = useState<DuelPlayer | null>(null);
  const [p2, setP2] = useState<DuelPlayer | null>(null);
  const [isBotDuel, setIsBotDuel] = useState(false);
  const [picked, setPicked] = useState<string | null>(null);
  const [reveal, setReveal] = useState<string | null>(null);
  const [gained, setGained] = useState<number | null>(null);
  const [streak, setStreak] = useState(0);
  const [disabled, setDisabled] = useState(false);
  const [opponentAnswered, setOpponentAnswered] = useState(false);
  const [countdown, setCountdown] = useState(COUNTDOWN_FROM);
  const [result, setResult] = useState<'win' | 'lose' | 'draw' | ''>('');
  const [rewards, setRewards] = useState({ xp: 0, coins: 0, elo: 0 });
  const [opponentDisconnected, setOpponentDisconnected] = useState(false);
  const [opponentGraceSeconds, setOpponentGraceSeconds] = useState(30);
  const [isReconnecting, setIsReconnecting] = useState(false);

  const ws = useRef<WebSocket | null>(null);
  const stateRef = useRef<State>('session');
  const myIdRef = useRef<number | null>(null);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const countdownTimer = useRef<ReturnType<typeof setInterval> | null>(null);
  const attempts = useRef(0);
  const left = useRef(false);
  const pingTimer = useRef<ReturnType<typeof setInterval> | null>(null);
  const missedPongs = useRef(0);
  stateRef.current = state;

  const clearTimers = () => {
    if (reconnectTimer.current) clearTimeout(reconnectTimer.current);
    if (countdownTimer.current) clearInterval(countdownTimer.current);
    if (pingTimer.current) clearInterval(pingTimer.current);
    reconnectTimer.current = null;
    countdownTimer.current = null;
  };

  const applyPlayers = useCallback(
    (a: unknown, b: unknown, totalQ?: unknown, botDuel?: unknown) => {
      const norm = (p: unknown): DuelPlayer | null => {
        if (!p || typeof p !== 'object') return null;
        const o = p as Record<string, unknown>;
        return {
          id: o.id === null || o.id === undefined ? null : Number(o.id),
          name: String(o.name ?? '?'),
          is_bot: o.is_bot === true,
        };
      };
      setP1(norm(a));
      setP2(norm(b));
      if (totalQ !== undefined) setTotal(Number(totalQ) || 10);
      if (botDuel !== undefined) setIsBotDuel(botDuel === true);
    },
    [],
  );

  const handleMessage = useCallback(
    (msg: Record<string, unknown>) => {
      switch (msg.type) {
        case 'connected':
          setMyId(Number(msg.user_id));
          myIdRef.current = Number(msg.user_id);
          break;
        case 'pong':
          missedPongs.current = 0;
          break;
        case 'opponent_disconnected':
          setOpponentDisconnected(true);
          setOpponentGraceSeconds(Number(msg.grace_period || 30));
          break;
        case 'opponent_reconnected':
          setOpponentDisconnected(false);
          break;
        case 'room_joined':
          applyPlayers(
            msg.player1,
            msg.player2,
            msg.total_questions,
            msg.is_bot_duel,
          );
          if (msg.time_per_question !== undefined) {
            setTimeLimit(Number(msg.time_per_question) || 15);
          }
          if (msg.current_question_index !== undefined) {
            setQIndex(Number(msg.current_question_index) || 0);
          }
          setState('waiting');
          setNotice(String(msg.message ?? t('arena_wait_hint')));
          break;
        case 'match_found':
          applyPlayers(msg.player1, msg.player2, msg.total_questions);
          if (countdownTimer.current) clearInterval(countdownTimer.current);
          setCountdown(COUNTDOWN_FROM);
          setState('countdown');
          countdownTimer.current = setInterval(() => {
            setCountdown((c) => {
              if (c <= 1 && countdownTimer.current) {
                clearInterval(countdownTimer.current);
                countdownTimer.current = null;
              }
              return c - 1;
            });
          }, 1000);
          break;
        case 'queue_update':
          setNotice(String(msg.message ?? ''));
          break;
        case 'send_question': {
          const q = msg.question as Question;
          setQuestion(q);
          setQIndex(Number(msg.question_index ?? 0));
          const limit = Number(msg.time_limit ?? 15);
          setTimeLimit(limit);
          setTimeLeft(limit);
          setPicked(null);
          setReveal(null);
          setGained(null);
          setDisabled(false);
          setOpponentAnswered(false);
          setState('playing');
          break;
        }
        case 'answer_result':
          setReveal(String(msg.correct_answer ?? ''));
          setStreak(Number(msg.streak ?? 0));
          setGained(Number(msg.points ?? 0));
          break;
        case 'live_score_update': {
          const list = normalizeArenaScores(msg.scores);
          setRows(list);
          const me = arenaRowOf(list, myIdRef.current);
          if (me?.streak !== undefined) setStreak(me.streak);
          if (
            msg.answered_by !== undefined &&
            Number(msg.answered_by) !== myIdRef.current
          ) {
            setOpponentAnswered(true);
          }
          break;
        }
        case 'game_over': {
          const list = normalizeArenaScores(msg.scores);
          setRows(list);
          const me = arenaRowOf(list, myIdRef.current);
          setRewards({
            xp: Number(me?.xp_earned ?? 0),
            coins: Number(me?.coins_earned ?? 0),
            elo: Number(me?.rating_change ?? 0),
          });
          const winnerId =
            msg.winner_id === null || msg.winner_id === undefined
              ? null
              : Number(msg.winner_id);
          if (winnerId === null || String(msg.winner ?? '') === 'Durang') {
            setResult('draw');
          } else if (winnerId === myIdRef.current) {
            setResult('win');
            try {
              confetti({
                particleCount: 80,
                spread: 80,
                origin: { y: 0.55 },
                colors: ['#F59E0B', '#10B981', '#FBBF24', '#34D399', '#8B5CF6'],
              });
            } catch {
              /* ignore */
            }
          } else {
            setResult('lose');
          }
          if (countdownTimer.current) clearInterval(countdownTimer.current);
          setOpponentDisconnected(false);
          setState('gameover');
          break;
        }
        case 'error':
          setNotice(String(msg.message ?? 'Error'));
          break;
        case 'left_room':
          left.current = true;
          navigate('/arena');
          break;
        default:
          break;
      }
    },
    [applyPlayers, navigate, t],
  );

  const connect = useCallback(() => {
    if (left.current) return;
    if (stateRef.current === 'gameover' || stateRef.current === 'error') return;
    setState('connecting');
    const sock = new WebSocket(arenaSocketUrl(code));
    ws.current = sock;
    sock.onopen = () => {
      attempts.current = 0;
      setIsReconnecting(false);
      missedPongs.current = 0;
      if (stateRef.current !== 'playing') {
        setState('waiting');
      }
      setNotice(t('arena_wait_hint'));
      sock.send(JSON.stringify({ type: 'join_room', room_code: code }));
    };
    sock.onmessage = (e: MessageEvent) => {
      try {
        handleMessage(JSON.parse(String(e.data)) as Record<string, unknown>);
      } catch {
        /* malformed frame — ignore */
      }
    };
    sock.onerror = () => {
      // onclose follows with the detail; nothing to do here.
    };
    sock.onclose = (ev) => {
      ws.current = null;
      if (left.current || stateRef.current === 'gameover') return;
      if (ev.code === 4001) {
        setState('error');
        setNotice(t('arena_login_needed'));
        return;
      }
      if (attempts.current >= MAX_RECONNECTS) {
        setState('error');
        setNotice(t('arena_ws_error'));
        setIsReconnecting(false);
        return;
      }
      const delay = BACKOFF_DELAYS[Math.min(attempts.current, BACKOFF_DELAYS.length - 1)];
      attempts.current += 1;
      setIsReconnecting(true);
      setNotice(t('arena_reconnecting'));
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current);
      reconnectTimer.current = setTimeout(() => {
        if (!left.current && stateRef.current !== 'gameover') connect();
      }, delay);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [code, handleMessage, t]);

  // Connect to the room via JWT WebSocket.
  useEffect(() => {
    if (authLoading) return;
    if (!user) {
      setState('error');
      setNotice(t('arena_login_needed'));
      return;
    }
    left.current = false;
    connect();
    if (pingTimer.current) clearInterval(pingTimer.current);
    pingTimer.current = setInterval(() => {
      if (ws.current && ws.current.readyState === WebSocket.OPEN) {
        missedPongs.current += 1;
        if (missedPongs.current >= 2) {
          try {
            ws.current.close();
          } catch {
            /* ignore */
          }
          return;
        }
        try {
          ws.current.send(JSON.stringify({ type: 'ping', timestamp: Date.now() }));
        } catch {
          /* ignore */
        }
      }
    }, 15000);
    return () => {
      left.current = true;
      clearTimers();
      try {
        ws.current?.send(JSON.stringify({ type: 'leave_room' }));
      } catch {
        /* closing */
      }
      try {
        ws.current?.close();
      } catch {
        /* closing */
      }
      ws.current = null;
    };
  }, [code, user, authLoading, connect, t]);

  // Opponent disconnected grace period countdown
  useEffect(() => {
    if (!opponentDisconnected) return;
    const timer = setInterval(() => {
      setOpponentGraceSeconds((s) => {
        if (s <= 1) {
          clearInterval(timer);
          return 0;
        }
        return s - 1;
      });
    }, 1000);
    return () => clearInterval(timer);
  }, [opponentDisconnected]);

  // Local countdown mirror (server is authoritative).
  useEffect(() => {
    if (state !== 'playing') return;
    if (timeLeft <= 0) return;
    const id = setInterval(() => {
      setTimeLeft((v) => {
        if (v <= 1) {
          setDisabled(true);
          return 0;
        }
        return v - 1;
      });
    }, 1000);
    return () => clearInterval(id);
  }, [state, timeLeft, qIndex]);

  const answer = (opt: string) => {
    if (picked || disabled || state !== 'playing') return;
    setPicked(opt);
    ws.current?.send(
      JSON.stringify({
        type: 'submit_answer',
        room_code: code,
        answer: opt,
        question_index: qIndex,
      }),
    );
  };

  const leave = () => {
    left.current = true;
    clearTimers();
    try {
      ws.current?.send(JSON.stringify({ type: 'leave_room' }));
    } catch {
      /* closing */
    }
    try {
      ws.current?.close();
    } catch {
      /* closing */
    }
    navigate('/arena');
  };

  const myScore = arenaScoreOf(rows, myId);
  const oppRows = arenaOpponentRows(rows, myId);
  const otherScore = oppRows.length > 0 ? (oppRows[0]?.score ?? 0) : 0;

  const nameOf = (p: DuelPlayer | null) => p?.name ?? '…';
  const myName =
    myId !== null && p1 && p2
      ? myId === p1.id
        ? nameOf(p1)
        : nameOf(p2)
      : t('arena_you');
  const oppName =
    myId !== null && p1 && p2
      ? myId === p1.id
        ? nameOf(p2)
        : nameOf(p1)
      : '…';

  return (
    <div style={{ maxWidth: 42 * 16, margin: '0 auto' }}>
      <h1>
        <SwordsIcon size={22} className="ico" /> {t('arena')} · {code}
      </h1>
      <p>
        <button className="btn sm" onClick={leave}>
          {t('arena_leave')}
        </button>
      </p>
      {opponentDisconnected && (
        <div
          style={{
            background: 'rgba(239, 68, 68, 0.15)',
            border: '1px solid rgba(239, 68, 68, 0.4)',
            color: '#f87171',
            borderRadius: 12,
            padding: '12px 16px',
            marginBottom: 16,
            display: 'flex',
            alignItems: 'center',
            gap: 12,
            fontWeight: 600,
          }}
        >
          <span style={{ fontSize: 22 }}>⚠️</span>
          <div>
            <div>Raqib interneti qayta ulanmoqda... (qolgan vaqt: {opponentGraceSeconds}s)</div>
            <div style={{ fontSize: 12, opacity: 0.8, marginTop: 2 }}>
              Agar 30 soniya ichida qayta ulanmasa, g‘alaba avtomatik sizga taqdim etiladi.
            </div>
          </div>
        </div>
      )}
      {isReconnecting && (
        <div
          style={{
            background: 'rgba(234, 179, 8, 0.15)',
            border: '1px solid rgba(234, 179, 8, 0.4)',
            color: '#fde047',
            borderRadius: 8,
            padding: '8px 12px',
            marginBottom: 12,
            fontSize: 13,
            fontWeight: 600,
          }}
        >
          ⚡ Tarmoq uzildi. Qayta ulanmoqda...
        </div>
      )}
      {notice && <p className="muted">{notice}</p>}

      {(state === 'session' || state === 'connecting') && (
        <p className="muted">{t('loading')}</p>
      )}
      {state === 'error' && <p className="error">{notice || t('arena_ws_error')}</p>}

      {state === 'waiting' && (
        <div className="card" style={{ textAlign: 'center', padding: '3rem 1rem' }}>
          <SwordsIcon size={56} />
          <h2>{t('arena_waiting')}</h2>
          <p className="muted">{t('arena_wait_hint')}</p>
        </div>
      )}

      {state === 'countdown' && (
        <div className="card" style={{ textAlign: 'center', padding: '3rem 1rem' }}>
          <div style={{
            fontSize: 88,
            fontWeight: 900,
            color: countdown <= 1 ? '#10b981' : '#FACC15',
            lineHeight: 1,
            transition: 'color 0.3s ease',
          }}>
            {countdown <= 0 ? '⚔️' : Math.max(countdown, 1)}
          </div>
          <p className="muted" style={{ marginTop: 14, fontSize: '1.05rem', fontWeight: 600 }}>
            {countdown <= 0 ? 'JANG BOSHLANDI!' : t('arena_starting')}
          </p>
          {p1 && p2 && (
            <p className="muted small" style={{ marginTop: 8 }}>
              <strong style={{ color: '#FACC15' }}>{p1.name}</strong>
              {' '}⚔️{' '}
              <strong style={{ color: '#ef4444' }}>{p2.name}</strong>
            </p>
          )}
        </div>
      )}

      {state === 'playing' && question && (
        <>
          <div className="card">
            <div className="score-head">
              <div className="score-side">
                <span
                  className="score-ava"
                  style={{
                    color: '#111111',
                    background: 'linear-gradient(135deg,#EAB308,#FACC15)',
                  }}
                >
                  {myName.slice(0, 2).toUpperCase()}
                </span>
                <span>
                  <b style={{ display: 'block', fontSize: 13 }}>{myName}</b>
                  <b style={{ color: '#FACC15' }}>{myScore}</b>
                </span>
              </div>
              <span className={`timer${timeLeft <= 5 ? ' low' : ''}`} style={{
                display: 'inline-flex',
                alignItems: 'center',
                justifyContent: 'center',
                minWidth: 48,
                height: 34,
                borderRadius: 17,
                padding: '0 10px',
                background: timeLeft <= 5 ? 'rgba(239, 68, 68, 0.2)' : 'rgba(245, 158, 11, 0.15)',
                border: `1.5px solid ${timeLeft <= 5 ? '#ef4444' : '#f59e0b'}`,
                color: timeLeft <= 5 ? '#ef4444' : '#f59e0b',
                fontWeight: 800,
                fontSize: '1rem',
              }}>
                ⏱️ {timeLeft}s
              </span>
              <div className="score-side right">
                <span>
                  <b style={{ display: 'block', fontSize: 13 }}>
                    {oppName}
                    {isBotDuel ? ` (${t('arena_bot')})` : ''}
                  </b>
                  <b style={{ color: '#e11d48' }}>{otherScore}</b>
                </span>
                <span
                  className="score-ava"
                  style={{
                    color: '#111111',
                    background: 'linear-gradient(135deg,#A16207,#EAB308)',
                  }}
                >
                  {oppName.slice(0, 2).toUpperCase()}
                </span>
              </div>
            </div>
            <div className="laser-beam-wrapper" aria-hidden="true" style={{ margin: '10px 0' }}>
              <div className="laser-beam-line" />
            </div>
            {streak >= 2 && (
              <p style={{ color: '#f59e0b', fontWeight: 800 }}>
                <FlameIcon size={14} className="ico" /> x{streak}
              </p>
            )}
            {gained !== null && reveal !== null && (
              <p className="muted small">
                +{gained} {t('points')}
              </p>
            )}
            {!opponentAnswered && <p className="muted small">{t('arena_thinking')}</p>}
          </div>

          <div className="card" style={{ marginTop: 12 }}>
            <p className="muted small">
              {t('th_questions')} {total > 0 ? qIndex + 1 : qIndex}/{total} ·{' '}
              {question.points} {t('points')}
            </p>
            <div
              className="progress"
              style={{ margin: '8px 0' }}
              aria-hidden="true"
            >
              <div
                style={{
                  width: total > 0 ? `${Math.min(100, ((qIndex + 1) / total) * 100)}%` : '0%',
                }}
              />
            </div>
            <h2>{question.question_text}</h2>
            <div style={{ display: 'grid', gap: 8, marginTop: 12 }}>
              {OPTS.map((opt) => {
                const label = question[`option_${opt}` as keyof Question] as string;
                const cls =
                  reveal !== null
                    ? opt === reveal
                      ? 'quiz-opt right'
                      : opt === picked
                        ? 'quiz-opt wrong'
                        : 'quiz-opt'
                    : picked === opt
                      ? 'quiz-opt picked'
                      : 'quiz-opt';
                return (
                  <button
                    key={opt}
                    className={cls}
                    disabled={picked !== null || disabled}
                    onClick={() => answer(opt)}
                  >
                    <span className="quiz-key">{opt.toUpperCase()}</span>
                    <span>{label}</span>
                  </button>
                );
              })}
            </div>
          </div>
        </>
      )}

      {state === 'gameover' && (
        <div className="card" style={{ textAlign: 'center', padding: '3rem 1rem' }}>
          <TrophyIcon size={56} />
          <h2>
            {result === 'win' && t('arena_win')}
            {result === 'lose' && t('arena_lose')}
            {result === 'draw' && t('arena_draw')}
            {!result && t('arena_game_over')}
          </h2>
          <p className="stat-value">
            {myScore} : {otherScore}
          </p>
          <div style={{ marginTop: 8, marginBottom: 16 }}>
            <div style={{ display: 'flex', justifyContent: 'center', gap: 16, flexWrap: 'wrap' }}>
              <span style={{ fontSize: '0.9rem', color: '#a78bfa', fontWeight: 600 }}>
                ⚡ +{rewards.xp} {t('xp')}
              </span>
              <span style={{ fontSize: '0.9rem', color: '#fbbf24', fontWeight: 600 }}>
                🪙 +{rewards.coins} {t('coins')}
              </span>
              <span style={{
                fontSize: '1.05rem',
                fontWeight: 800,
                color: rewards.elo >= 0 ? '#10b981' : '#ef4444',
                padding: '2px 8px',
                borderRadius: 6,
                background: rewards.elo >= 0 ? 'rgba(16, 185, 129, 0.12)' : 'rgba(239, 68, 68, 0.12)',
              }}>
                ELO {rewards.elo >= 0 ? `▲ +${rewards.elo}` : `▼ ${rewards.elo}`}
              </span>
            </div>
            {result === 'win' && (
              <p style={{ fontSize: '0.85rem', color: '#10b981', marginTop: 10, fontWeight: 600 }}>
                🎉 Ajoyib g'alaba! Reytingingiz oshdi!
              </p>
            )}
            {result === 'lose' && (
              <p style={{ fontSize: '0.85rem', color: '#ef4444', marginTop: 10, fontWeight: 600 }}>
                💪 Yaxshi kurash bo'ldi! Keyingi duelda albatta yutasiz.
              </p>
            )}
            {result === 'draw' && (
              <p style={{ fontSize: '0.85rem', color: '#94a3b8', marginTop: 10, fontWeight: 600 }}>
                🤝 Do'stlik g'alaba qozondi! Teng kurash bo'ldi.
              </p>
            )}
          </div>
          <button className="btn primary" onClick={() => navigate('/arena')}>
            {t('back')} →
          </button>
        </div>
      )}
    </div>
  );
}
