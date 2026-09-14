import { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useLang } from '../i18n/LangContext';
import { ArenaLobby, arenaSocketUrl, ensureSession } from '../lib/api';
import { SwordsIcon } from '../components/icons';
import { getCachedPassword } from '../auth/AuthContext';
import { useAuth } from '../auth/AuthContext';

/**
 * Arena lobby — mirrors GET /tma/api/arena/ (JWT summary: stats +
 * leaderboard + invites) and the session JSON APIs (POST
 * /arena/api/rooms/create/, POST /arena/api/rooms/join/, GET
 * /arena/api/stats|leaderboard|invites/ — all need ensureSession() first).
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
  const [busy, setBusy] = useState(false);
  const [sessionOk, setSessionOk] = useState<boolean | null>(null);
  const [queue, setQueue] = useState<QueueState>('idle');
  const [queueMsg, setQueueMsg] = useState('');
  const [queuePos, setQueuePos] = useState<number | null>(null);
  const queueWs = useRef<WebSocket | null>(null);

  useEffect(() => {
    ArenaLobby.summary()
      .then(setSummary)
      .catch(() => setSummary(null));
    if (user) {
      ensureSession(user.email, getCachedPassword() ?? '')
        .then(setSessionOk)
        .catch(() => setSessionOk(false));
    }
    return () => {
      try {
        queueWs.current?.close();
      } catch {
        /* closing */
      }
      queueWs.current = null;
    };
  }, [user]);

  const needSession = async (): Promise<boolean> => {
    if (sessionOk) return true;
    if (user) {
      const ok = await ensureSession(user.email, getCachedPassword() ?? '').catch(
        () => false,
      );
      setSessionOk(ok);
      if (ok) return true;
    }
    setMsg(t('arena_session_needed'));
    return false;
  };

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

  /** WS matchmaking (legacy lobby parity): join_queue → match_found. */
  const quickMatch = async () => {
    if (!(await needSession())) return;
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
        setMsg(String(data.message ?? 'Error'));
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
        setSessionOk(false);
        setMsg(t('arena_login_needed'));
        return;
      }
      // Server closes after match_found redirect delay — only reset when
      // we never reached the found state.
      setQueue((q) => (q === 'found' ? q : 'idle'));
    };
  };

  const createRoom = async () => {
    if (!(await needSession())) return;
    setBusy(true);
    try {
      const r = await ArenaLobby.createRoom();
      navigate(`/arena/${r.room_code}`);
    } catch (e) {
      setMsg(e instanceof Error ? e.message : 'Failed.');
    } finally {
      setBusy(false);
    }
  };

  const joinRoom = async (raw?: string) => {
    if (!(await needSession())) return;
    const value = (raw ?? code).trim().toUpperCase();
    if (!value) return;
    setBusy(true);
    try {
      const r = await ArenaLobby.joinRoom(value);
      navigate(`/arena/${r.room_code}`);
    } catch (e) {
      setMsg(e instanceof Error ? e.message : 'Failed.');
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
      {sessionOk === false && <p className="error">{t('arena_session_needed')}</p>}
      {msg && <p className="error">{msg}</p>}

      <div className="grid">
        <div className="card">
          <h2>{t('arena_quick_match')}</h2>
          <p className="muted small">{t('arena_quick_hint')}</p>
          {queue === 'idle' ? (
            <button className="btn primary" disabled={busy} onClick={quickMatch}>
              {t('arena_find_match')}
            </button>
          ) : (
            <>
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
        <div className="card">
          <h2>{t('arena_create_room')}</h2>
          <button className="btn" disabled={busy} onClick={createRoom}>
            {t('arena_create')}
          </button>
          <div className="form">
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
        <div className="card stat">
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
    </div>
  );
}
