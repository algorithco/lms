import { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useLang } from '../i18n/LangContext';
import { ArenaLobby, arenaSocketUrl } from '../lib/api';
import { SwordsIcon } from '../components/icons';
import { useAuth } from '../auth/AuthContext';
import TiltCard from '../components/TiltCard';
import LimitExceededModal from '../components/LimitExceededModal';

/**
 * Arena lobby — mirrors GET /tma/api/arena/ (JWT summary: stats +
 * leaderboard + invites) and the arena JSON APIs (POST
 * /arena/api/rooms/create/, POST /arena/api/rooms/join/, GET
 * /arena/api/stats|leaderboard|invites/ — all using JWT).
 *
 * Matchmaking parity with templates/arena/lobby.html: quick match opens a
 * WebSocket to /ws/arena/ and sends {type: "join_queue"}; the server answers
 * queue_update (position + bot-fallback countdown) and match_found
 * (→ navigate to /arena/<room_code>/). The REST POST /arena/api/queue/
 * only reports matched/position for one shot, so WS is primary.
 */

interface BoardRow {
  rank?: number;
  name?: string;
  rating?: number;
  wins?: number;
  current_win_streak?: number;
  accuracy?: number;
}

interface ArenaStats {
  rating?: number;
  rank?: number;
  wins?: number;
  losses?: number;
  draws?: number;
  duels_played?: number;
  current_win_streak?: number;
  best_win_streak?: number;
  accuracy?: number;
  win_rate?: number;
  xp?: number;
  coins?: number;
}

interface Invite {
  room_code: string;
  url?: string;
}

type QueueState = 'idle' | 'connecting' | 'waiting' | 'found';

export default function Arena() {
  const { t } = useLang();
  const { user } = useAuth();
  const navigate = useNavigate();
  const [summary, setSummary] = useState<Record<string, unknown> | null>(null);
  const [code, setCode] = useState('');
  const [msg, setMsg] = useState<string | null>(null);
  const [limitModalOpen, setLimitModalOpen] = useState(false);
  const [limitModalMsg, setLimitModalMsg] = useState<string | undefined>();
  const [busy, setBusy] = useState(false);
  const [queue, setQueue] = useState<QueueState>('idle');
  const [queueMsg, setQueueMsg] = useState('');
  const [queuePos, setQueuePos] = useState<number | null>(null);
  const queueWs = useRef<WebSocket | null>(null);

  useEffect(() => {
    ArenaLobby.summary()
      .then(setSummary)
      .catch(() => setSummary(null));
    return () => {
      try {
        queueWs.current?.close();
      } catch {
        /* closing */
      }
      queueWs.current = null;
    };
  }, []);

  const cancelQueue = () => {
    try {
      queueWs.current?.close();
    } catch {
      /* closing */
    }
    queueWs.current = null;
    setQueue('idle');
    setQueueMsg('');
    setQueuePos(null);
  };

  /** WS matchmaking: join_queue → match_found with JWT token in URL. */
  const quickMatch = async () => {
    if (!user) {
      setMsg(t('arena_login_needed'));
      return;
    }
    if (queue === 'connecting' || queue === 'waiting') return;
    setMsg(null);
    setQueue('connecting');
    setQueueMsg(t('loading'));
    setQueuePos(null);
    let settled = false;
    const sock = new WebSocket(arenaSocketUrl());
    queueWs.current = sock;
    sock.onopen = () => {
      if (settled) return;
      setQueue('waiting');
      sock.send(JSON.stringify({ type: 'join_queue' }));
    };
    sock.onmessage = (e: MessageEvent) => {
      let data: Record<string, unknown>;
      try {
        data = JSON.parse(String(e.data)) as Record<string, unknown>;
      } catch {
        return;
      }
      if (data.type === 'queue_update') {
        setQueueMsg(String(data.message ?? ''));
        setQueuePos(
          data.position !== undefined ? Number(data.position) : null,
        );
      } else if (data.type === 'match_found') {
        settled = true;
        setQueue('found');
        setQueueMsg(t('arena_match_found'));
        const roomCode = String(data.room_code ?? '');
        try {
          sock.close();
        } catch {
          /* closing */
        }
        queueWs.current = null;
        setTimeout(() => navigate(`/arena/${roomCode}`), 1500);
      } else if (data.type === 'error') {
        const errStr = String(data.message ?? 'Error');
        if (errStr.includes('LIMIT_EXCEEDED') || errStr.includes('limitingiz tugadi')) {
          setLimitModalMsg("Bugungi bepul 1v1 Arena limitingiz tugadi (kuniga 3 ta o'yin). Cheksiz janglar uchun STARTER (15 000 so'm) yoki PRO (49 000 so'm) tarifiga o'ting!");
          setLimitModalOpen(true);
        } else {
          setMsg(errStr);
        }
      }
    };
    sock.onerror = () => {
      if (settled) return;
      setQueue('idle');
      setMsg(t('arena_ws_error'));
    };
    sock.onclose = (ev) => {
      queueWs.current = null;
      if (settled) return;
      if (ev.code === 4001) {
        setQueue('idle');
        setMsg(t('arena_login_needed'));
        return;
      }
      // Server closes after match_found redirect delay — only reset when
      // we never reached the found state.
      setQueue((q) => (q === 'found' ? q : 'idle'));
    };
  };

  const createRoom = async () => {
    if (!user) {
      setMsg(t('arena_login_needed'));
      return;
    }
    setBusy(true);
    try {
      const r = await ArenaLobby.createRoom();
      navigate(`/arena/${r.room_code}`);
    } catch (e) {
      const errorText = e instanceof Error ? e.message : 'Failed.';
      if (errorText.includes('LIMIT_EXCEEDED') || errorText.includes('limitingiz tugadi')) {
        setLimitModalMsg("Bugungi bepul 1v1 Arena limitingiz tugadi (kuniga 3 ta o'yin). Cheksiz janglar uchun STARTER (15 000 so'm) yoki PRO (49 000 so'm) tarifiga o'ting!");
        setLimitModalOpen(true);
      } else {
        setMsg(errorText);
      }
    } finally {
      setBusy(false);
    }
  };

  const joinRoom = async (raw?: string) => {
    if (!user) {
      setMsg(t('arena_login_needed'));
      return;
    }
    const value = (raw ?? code).trim().toUpperCase();
    if (!value) return;
    setBusy(true);
    try {
      const r = await ArenaLobby.joinRoom(value);
      navigate(`/arena/${r.room_code}`);
    } catch (e) {
      const errorText = e instanceof Error ? e.message : 'Failed.';
      if (errorText.includes('LIMIT_EXCEEDED') || errorText.includes('limitingiz tugadi')) {
        setLimitModalMsg("Bugungi bepul 1v1 Arena limitingiz tugadi (kuniga 3 ta o'yin). Cheksiz janglar uchun STARTER (15 000 so'm) yoki PRO (49 000 so'm) tarifiga o'ting!");
        setLimitModalOpen(true);
      } else {
        setMsg(errorText);
      }
    } finally {
      setBusy(false);
    }
  };

  const board = (summary?.leaderboard as BoardRow[] | undefined) ?? [];
  const stats = (summary?.stats as ArenaStats | undefined) ?? {};
  const invites = (summary?.invites as Invite[] | undefined) ?? [];

  return (
    <div>
      <h1>
        <SwordsIcon size={24} className="ico" /> {t('arena')}
      </h1>
      <p className="muted">{t('arena_realtime_hint')}</p>
      {msg && <p className="error">{msg}</p>}

      <div className="grid">
        <TiltCard glare maxTilt={8} scale={1.02} style={{ borderRadius: 'var(--radius)', height: '100%' }}>
          <div className="card" style={{ height: '100%', margin: 0 }}>
            <h2>{t('arena_quick_match')}</h2>
            <p className="muted small">{t('arena_quick_hint')}</p>
            {queue === 'idle' ? (
              <button className="btn primary" disabled={busy} onClick={quickMatch}>
                {t('arena_find_match')}
              </button>
            ) : (
              <>
                <div className="laser-beam-wrapper" aria-hidden="true" style={{ margin: '10px 0' }}>
                  <div className="laser-beam-line" />
                </div>
                <p className="muted small">
                  {queuePos !== null ? `${t('arena_queue_position')}: ${queuePos} · ` : ''}
                  {queueMsg}
                </p>
                <button className="btn sm" onClick={cancelQueue}>
                  {t('cancel')}
                </button>
              </>
            )}
          </div>
        </TiltCard>
        <TiltCard glare maxTilt={8} scale={1.02} style={{ borderRadius: 'var(--radius)', height: '100%' }}>
          <div className="card" style={{ height: '100%', margin: 0 }}>
            <h2>{t('arena_create_room')}</h2>
            <button className="btn" disabled={busy} onClick={createRoom}>
              {t('arena_create')}
            </button>
            <div className="form" style={{ marginTop: 12 }}>
              <label>
                {t('arena_enter_code')}
                <input
                  value={code}
                  onChange={(e) => setCode(e.target.value)}
                  placeholder="ABC123"
                />
              </label>
              <button className="btn" disabled={busy} onClick={() => joinRoom()}>
                {t('arena_join')}
              </button>
            </div>
          </div>
        </TiltCard>
        <TiltCard glare maxTilt={8} scale={1.02} style={{ borderRadius: 'var(--radius)', height: '100%' }}>
          <div className="card stat stat-gradient-amber" style={{ height: '100%', margin: 0 }}>
            <span className="stat-label">{t('arena_my_stats')}</span>
            <span className="stat-value">
              {stats.rating ?? '—'}
              <small className="muted">
                {' '}
                ELO{stats.rank ? ` · #${stats.rank}` : ''}
              </small>
            </span>
            <p className="muted small">
              {t('arena_wins')}: {stats.wins ?? '—'} · {t('arena_losses')}:{' '}
              {stats.losses ?? '—'} · {t('arena_draws')}: {stats.draws ?? '—'}
            </p>
            <p className="muted small">
              {t('arena_streak')}: {stats.current_win_streak ?? '—'} ·{' '}
              {t('arena_accuracy')}: {stats.accuracy ?? '—'}% · {t('arena_duels')}:{' '}
              {stats.duels_played ?? '—'}
            </p>
            {(stats.xp !== undefined || stats.coins !== undefined) && (
              <p className="muted small">
                ⚡ {stats.xp ?? 0} {t('xp')} · 🪙 {stats.coins ?? 0} {t('coins')}
              </p>
            )}
          </div>
        </TiltCard>
      </div>

      <h2>{t('arena_invites')}</h2>
      {invites.length === 0 ? (
        <p className="muted small">{t('arena_no_invites')}</p>
      ) : (
        <div className="grid">
          {invites.map((inv) => (
            <div key={inv.room_code} className="card">
              <strong style={{ letterSpacing: '0.2em' }}>{inv.room_code}</strong>
              <p className="muted small">{t('arena_invite_hint')}</p>
              <button
                className="btn primary sm"
                disabled={busy}
                onClick={() => joinRoom(inv.room_code)}
              >
                {t('arena_join')}
              </button>
            </div>
          ))}
        </div>
      )}

      <h2>{t('arena_leaderboard')}</h2>
      <div className="table-wrap">
        <table className="data">
          <thead>
            <tr>
              <th>{t('lb_rank')}</th>
              <th>{t('lb_student')}</th>
              <th>{t('arena_rating')}</th>
              <th>{t('arena_wins')}</th>
              <th>{t('arena_streak')}</th>
            </tr>
          </thead>
          <tbody>
            {board.slice(0, 20).map((r, i) => (
              <tr key={r.rank ?? i}>
                <td>{r.rank ?? i + 1}</td>
                <td>{r.name ?? '—'}</td>
                <td>{r.rating ?? '—'}</td>
                <td>{r.wins ?? '—'}</td>
                <td>{r.current_win_streak ?? '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <LimitExceededModal
        isOpen={limitModalOpen}
        onClose={() => setLimitModalOpen(false)}
        title="⚔️ 1v1 Arena Limiti Tugadi"
        message={limitModalMsg}
        feature="arena"
      />
    </div>
  );
}
