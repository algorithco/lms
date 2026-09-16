import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { useLang } from '../i18n/LangContext';
import { Auth, Games as GamesApi } from '../lib/api';
import { num, str } from '../lib/billingPanelGames';
import {
  AwardIcon,
  BombIcon,
  FlameIcon,
  GamepadIcon,
  ScrollTextIcon,
  TrophyIcon,
} from '../components/icons';
import type { ReactNode } from 'react';

const GAME_ICONS: Record<string, (p: { size?: number; className?: string }) => ReactNode> = {
  imlo_mina: (p) => <BombIcon {...p} />,
  gazal_puzzle: (p) => <ScrollTextIcon {...p} />,
  lugat_match: (p) => <GamepadIcon {...p} />,
};

function GameIcon({ slug, size = 32 }: { slug: string; size?: number }) {
  const Cmp = GAME_ICONS[slug] ?? GamepadIcon;
  return <Cmp size={size} />;
}

interface Game {
  id: number;
  name: string;
  slug: string;
  description: string;
  icon_emoji: string;
  xp_per_correct: number;
  coins_per_correct: number;
  combo_multiplier: number | string;
}

interface Score {
  game_slug: string;
  game_name: string;
  total_xp: number;
  total_coins: number;
  games_played: number;
  correct_answers: number;
  wrong_answers: number;
  best_streak: number;
  high_score: number;
}

/**
 * Games hub — parity with templates/web/games_index.html:
 * stats bar (XP/coins/badges), game cards (rules + my score),
 * top-10 leaderboard + recent badges.
 * Full leaderboard — GET /api/v1/games/leaderboard/ → { leaderboard, my_stats }.
 */
export default function Games() {
  const { t } = useLang();
  const [games, setGames] = useState<Game[]>([]);
  const [scores, setScores] = useState<Score[]>([]);
  const [stats, setStats] = useState({ total_xp: 0, total_coins: 0 });
  const [badges, setBadges] = useState<{ name: string; emoji: string }[]>([]);
  const [board, setBoard] = useState<Record<string, unknown>[]>([]);
  const [fullBoard, setFullBoard] = useState<Record<string, unknown>[]>([]);
  const [myStats, setMyStats] = useState<Record<string, unknown> | null>(null);
  const [meId, setMeId] = useState<number | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    Auth.me()
      .then((me) => setMeId(me.id))
      .catch(() => undefined);
    GamesApi.hub()
      .then((h) => {
        setGames(h.games as unknown as Game[]);
        setScores(h.scores as unknown as Score[]);
        setStats(h.stats);
        setBadges(h.recent_badges);
        setBoard(h.leaderboard as unknown as Record<string, unknown>[]);
      })
      .catch((e: unknown) => setErr(e instanceof Error ? e.message : 'Failed.'));
    // Full leaderboard endpoint (my_stats + top-10 with games_played).
    GamesApi.leaderboard()
      .then((r) => {
        setFullBoard(r.leaderboard as unknown as Record<string, unknown>[]);
        setMyStats((r.my_stats ?? null) as Record<string, unknown> | null);
      })
      .catch(() => undefined);
  }, []);

  const scoreFor = (slug: string) => scores.find((s) => s.game_slug === slug);
  const rows = fullBoard.length > 0 ? fullBoard : board;

  return (
    <div>
      <h1>
        <GamepadIcon size={24} className="ico" /> {t('games')}
      </h1>
      {err && <p className="error">{err}</p>}

      {/* Stats bar — mirrors games_index user_stats cards. */}
      <div className="grid">
        <div className="card stat stat-gradient-blue">
          <span className="stat-label">⚡ XP</span>
          <span className="stat-value">{stats.total_xp}</span>
        </div>
        <div className="card stat stat-gradient-amber">
          <span className="stat-label">🪙 {t('coins')}</span>
          <span className="stat-value">{stats.total_coins}</span>
        </div>
        <div className="card stat stat-gradient-purple">
          <span className="stat-label">
            <AwardIcon size={13} className="ico" /> {t('badges')}
          </span>
          <span className="stat-value small">
            {badges.length
              ? badges.map((b) => `${b.emoji} ${b.name}`).join(' · ')
              : t('game_badges_empty')}
          </span>
        </div>
      </div>

      {/* Game cards — every active game the hub returns is linked. */}
      {games.length === 0 && !err ? (
        <div className="card">
          <p>
            <strong>{t('game_empty_title')}</strong>
          </p>
          <p className="muted small">{t('loading')}</p>
        </div>
      ) : (
        <div className="grid">
          {games.map((g) => {
            const s = scoreFor(g.slug);
            return (
              <Link key={g.id} to={`/games/${g.slug}`} className="card link-card">
                <span style={{ fontSize: 40 }}>{g.icon_emoji || <GameIcon slug={g.slug} />}</span>
                <strong>
                  <GameIcon slug={g.slug} size={16} /> {g.name}
                </strong>
                <span className="muted small">{g.description}</span>
                <span className="muted small">
                  ⚡ {num(g.xp_per_correct)} XP · 🪙 {num(g.coins_per_correct)} · 🔥{' '}
                  {str(g.combo_multiplier)}x
                </span>
                {s && (
                  <span className="muted small">
                    XP {s.total_xp} · <FlameIcon size={12} className="ico" /> {s.best_streak} ·{' '}
                    {s.games_played} {t('games_played_suffix')}
                  </span>
                )}
                <span className="badge green">{t('play')} →</span>
              </Link>
            );
          })}
        </div>
      )}

      {/* Leaderboard — full /leaderboard/ endpoint when available. */}
      <h2>
        <TrophyIcon size={20} className="ico" /> {t('leaderboard')}
      </h2>
      {myStats && (
        <p className="muted small">
          XP {str(myStats.total_xp ?? '—')} · 🪙 {str(myStats.total_coins ?? '—')}
        </p>
      )}
      {rows.length === 0 ? (
        <p className="muted">{t('game_board_empty')}</p>
      ) : (
        <div className="table-wrap">
          <table className="data">
            <thead>
              <tr>
                <th>#</th>
                <th>{t('th_student')}</th>
                <th>XP</th>
                <th>🪙</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r: Record<string, unknown>) => {
                const mine =
                  meId !== null && num(r.user__id, -1) === meId ? ` · ${t('panel_you')}` : '';
                return (
                  <tr key={String(r.user__id ?? r.id ?? Math.random().toString(36).slice(2))}>
                    <td>{num(r.rank, 0) || 1}</td>
                    <td>
                      {str(r.user__first_name)} {str(r.user__last_name)}
                      {mine}
                      <br />
                      <small className="muted">
                        {str(r.games_played ?? '', '') && `${str(r.games_played)} ${t('games_played_suffix')}`}
                      </small>
                    </td>
                    <td>{str(r.total_xp ?? '—')}</td>
                    <td className="muted small">{str(r.total_coins ?? '—')}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
