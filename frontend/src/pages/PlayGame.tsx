import { useCallback, useEffect, useRef, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { useLang } from '../i18n/LangContext';
import { Games as GamesApi } from '../lib/api';
import { isPlayableSlug, milestoneFor, num, str } from '../lib/billingPanelGames';
import { CheckIcon, CrosshairIcon, FlameIcon, RefreshIcon } from '../components/icons';

interface Level {
  id: number;
  title: string;
  difficulty: number;
  hint?: string;
  time_limit_seconds?: number;
}

interface CheckResult {
  is_correct: boolean;
  combo: number;
  xp_earned: number;
  coins_earned: number;
  total_xp: number;
  total_coins: number;
  streak: number;
  answer: Record<string, unknown>;
  new_badges: { name: string; emoji: string }[];
}

interface Card {
  id: string;
  pair_id: number;
  text: string;
  type: string;
}

/**
 * Play view — wires EVERY playable backend game (views_games):
 * - imlo_mina: click the misspelled word → { word_index, action: fix|skip }
 * - gazal_puzzle: order bayt lines → { order: "0,1,2.." }
 * - lugat_match: flip two cards → { card1_id, card2_id }
 * Slugs the model defines but the API cannot play (arena_duel,
 * telegram_quiz) render an explanatory empty state — no game left unwired.
 * Rewards (XP/coins/combo/badges/streak) mirror _award_xp via check_view.
 */
export default function PlayGame() {
  const { slug = '' } = useParams();
  const { t } = useLang();
  const [game, setGame] = useState<Record<string, unknown> | null>(null);
  const [level, setLevel] = useState<Level | null>(null);
  const [levels, setLevels] = useState<Level[]>([]);
  const [content, setContent] = useState<Record<string, unknown>>({});
  const [myScore, setMyScore] = useState<Record<string, unknown> | null>(null);
  const [combo, setCombo] = useState(0);
  const [sessionXp, setSessionXp] = useState(0);
  const [sessionCoins, setSessionCoins] = useState(0);
  const [totalXp, setTotalXp] = useState<number | null>(null);
  const [last, setLast] = useState<CheckResult | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [remaining, setRemaining] = useState<number | null>(null);

  // Per-game UI state
  const [pickedWord, setPickedWord] = useState<number | null>(null);
  const [order, setOrder] = useState<number[]>([]);
  const [selCards, setSelCards] = useState<string[]>([]);
  const [donePairs, setDonePairs] = useState<number[]>([]);
  const pendingPair = useRef<number[] | null>(null);

  const load = useCallback(
    async (levelId?: number) => {
      setErr(null);
      setLast(null);
      setPickedWord(null);
      setOrder([]);
      setSelCards([]);
      setDonePairs([]);
      pendingPair.current = null;
      try {
        const r = await GamesApi.play(slug, levelId);
        setGame(r.game as unknown as Record<string, unknown>);
        setLevel(r.level as unknown as Level);
        setLevels(r.levels as unknown as Level[]);
        setContent(r.content as unknown as Record<string, unknown>);
        setMyScore((r.my_score ?? null) as Record<string, unknown> | null);
        setRemaining(num((r.level as unknown as Level)?.time_limit_seconds, 0) || null);
        if (slug === 'gazal_puzzle') {
          const n = num((r.content as Record<string, unknown>).line_count, 0);
          setOrder(Array.from({ length: n }, (_, i) => i));
        }
      } catch (e) {
        setErr(e instanceof Error ? e.message : t('game_no_levels_msg'));
      }
    },
    [slug, t],
  );

  useEffect(() => {
    load();
  }, [load]);

  // Countdown display (legacy templates show mm:ss, red under 10s).
  useEffect(() => {
    if (remaining === null || remaining <= 0) return;
    const id = setTimeout(() => setRemaining((r) => (r !== null && r > 0 ? r - 1 : r)), 1000);
    return () => clearTimeout(id);
  }, [remaining]);

  const check = async (payload: Record<string, unknown>) => {
    if (!level || busy) return;
    setBusy(true);
    try {
      const r = await GamesApi.check(slug, { level_id: level.id, combo, ...payload });
      const res = r as unknown as CheckResult;
      setLast(res);
      setCombo(res.combo);
      setTotalXp(res.total_xp);
      setSessionXp((x) => x + num(res.xp_earned));
      setSessionCoins((c) => c + num(res.coins_earned));
    } catch (e) {
      setErr(e instanceof Error ? e.message : 'Failed.');
    } finally {
      setBusy(false);
    }
  };

  const moveLine = (from: number, dir: -1 | 1) => {
    setOrder((o) => {
      const to = from + dir;
      if (to < 0 || to >= o.length) return o;
      const next = [...o];
      [next[from], next[to]] = [next[to], next[from]];
      return next;
    });
  };

  const cards = (content.cards as Card[] | undefined) ?? [];
  const toggleCard = (id: string, pairId: number) => {
    if (donePairs.includes(pairId) || selCards.includes(id) || busy) return;
    const next = [...selCards, id];
    setSelCards(next);
    if (next.length === 2) {
      const [a, b] = next;
      const ids = cards.filter((c) => next.includes(c.id)).map((c) => c.pair_id);
      pendingPair.current = ids;
      check({ card1_id: a, card2_id: b }).then(() => {
        setSelCards([]);
      });
    }
  };

  // Confirm matched pairs when the server says the move was correct.
  useEffect(() => {
    if (last?.is_correct && pendingPair.current) {
      const [a, b] = pendingPair.current;
      if (a === b) setDonePairs((d) => (d.includes(a) ? d : [...d, a]));
    }
    pendingPair.current = null;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [last]);

  const words = (content.words as string[] | undefined) ?? [];
  const shuffled = (content.shuffled_lines as string[] | undefined) ?? [];
  const pairsCount = num(content.pairs_count, cards.length ? cards.length / 2 : 0);
  const milestone = milestoneFor(combo);

  const fmtTime = (s: number) =>
    `${String(Math.floor(s / 60)).padStart(2, '0')}:${String(s % 60).padStart(2, '0')}`;

  const answerLine = (): string | null => {
    if (!last) return null;
    const a = last.answer ?? {};
    if (slug === 'imlo_mina' && a.error_word_index !== undefined) {
      const i = num(a.error_word_index, -1);
      const w = words[i];
      return `${t('game_answer_label')}: #${i + 1}${w ? ` — ${w}` : ''}`;
    }
    if (slug === 'gazal_puzzle' && Array.isArray(a.correct_order)) {
      return `${t('game_answer_label')}: ${(a.correct_order as number[]).map((n) => n + 1).join(' → ')}`;
    }
    if (slug === 'lugat_match') return null;
    return null;
  };

  return (
    <div>
      <p>
        <Link to="/games">← {t('game_back_hub')}</Link>
      </p>
      <h1>{str(game?.name, slug)}</h1>
      {game?.description ? <p className="muted">{str(game.description)}</p> : null}
      {err && <p className="error">{err}</p>}

      {/* Non-playable backend slugs (arena_duel, telegram_quiz): explain. */}
      {!isPlayableSlug(slug) && (
        <div className="card">
          <p>
            <strong>{t('game_unknown_msg')}</strong>
          </p>
          {content.data !== undefined && (
            <pre className="muted small">{JSON.stringify(content.data, null, 2)}</pre>
          )}
        </div>
      )}

      {/* Stats bar — mirrors legacy per-game stats bars. */}
      <div className="grid">
        <div className="card stat">
          <span className="stat-label">⚡ XP</span>
          <span className="stat-value">{totalXp ?? sessionXp}</span>
        </div>
        <div className="card stat">
          <span className="stat-label">🪙 {t('coins')}</span>
          <span className="stat-value">{sessionCoins}</span>
        </div>
        <div className="card stat">
          <span className="stat-label">
            <FlameIcon size={13} className="ico" /> {t('game_streak_label')}
          </span>
          <span className="stat-value">{combo}</span>
          {milestone && <span className="badge green">{milestone}</span>}
        </div>
        {remaining !== null && (
          <div className="card stat">
            <span className="stat-label">⏱ {t('game_time_label')}</span>
            <span className="stat-value" style={remaining <= 10 ? { color: '#dc2626' } : undefined}>
              {fmtTime(remaining)}
            </span>
          </div>
        )}
      </div>

      {level && (
        <p className="muted">
          {level.title} · {t('difficulty')} {level.difficulty}
          {level.hint ? ` · 💡 ${t('game_hint_label')}: ${level.hint}` : ''}
        </p>
      )}
      {myScore && (
        <p className="muted small">
          {t('game_my_score_title')}: XP {str(myScore.total_xp)} · {t('game_streak_label')}{' '}
          {str(myScore.best_streak)}
        </p>
      )}

      {last && (
        <p className={last.is_correct ? 'badge green' : 'badge rose'} style={{ fontSize: 14 }}>
          {last.is_correct ? `✓ +${last.xp_earned} XP +${last.coins_earned} 🪙` : '✗'}
          {last.new_badges.map((b) => (
            <span key={b.name}>
              {' '}
              {b.emoji} {b.name}
            </span>
          ))}
        </p>
      )}
      {answerLine() && <p className="muted small">{answerLine()}</p>}

      {/* IMLO — click the misspelled word (legacy imlo_mines.html rules). */}
      {slug === 'imlo_mina' && (
        <div className="card" style={{ marginTop: 12 }}>
          <p className="muted small">💣 {str(game?.description)}</p>
          <p style={{ lineHeight: 2.2 }}>
            {words.map((w, i) => (
              <button
                key={i}
                className="word-btn"
                style={{
                  margin: 2,
                  ...(pickedWord === i
                    ? { borderColor: '#EAB308', background: 'rgba(250,204,21,.12)' }
                    : {}),
                }}
                onClick={() => setPickedWord(i)}
              >
                {w}
              </button>
            ))}
          </p>
          <div className="row" style={{ marginTop: 12 }}>
            <button
              className="btn primary"
              disabled={busy || pickedWord === null}
              onClick={() => pickedWord !== null && check({ word_index: pickedWord, action: 'fix' })}
            >
              <CrosshairIcon size={15} className="ico" /> {t('game_find_mine_btn')}
            </button>
            <button className="btn" disabled={busy} onClick={() => check({ word_index: -1, action: 'skip' })}>
              {t('game_skip_btn')}
            </button>
          </div>
        </div>
      )}

      {/* GAZAL — order the bayt lines (legacy gazal_puzzle.html rules). */}
      {slug === 'gazal_puzzle' && (
        <div className="card" style={{ marginTop: 12 }}>
          <div style={{ display: 'grid', gap: 8 }}>
            {order.map((lineIdx, pos) => (
              <div key={pos} className="gazal-line">
                <span className="n">{pos + 1}</span>
                <span style={{ flex: 1 }}>{shuffled[lineIdx] ?? ''}</span>
                <button className="btn sm ghost" onClick={() => moveLine(pos, -1)}>
                  ↑
                </button>
                <button className="btn sm ghost" onClick={() => moveLine(pos, 1)}>
                  ↓
                </button>
              </div>
            ))}
          </div>
          <button
            className="btn primary"
            style={{ marginTop: 12 }}
            disabled={busy}
            onClick={() => check({ order: order.join(',') })}
          >
            <CheckIcon size={15} className="ico" /> {t('game_check_btn')}
          </button>
        </div>
      )}

      {/* LUGAT — match old↔new pairs (legacy lugat_match.html rules). */}
      {slug === 'lugat_match' && (
        <div className="card" style={{ marginTop: 12 }}>
          <p className="muted small">
            {t('game_matches_label')}: {donePairs.length}/{pairsCount || '?'}
          </p>
          <div className="match-grid">
            {cards.map((c) => (
              <button
                key={c.id}
                disabled={donePairs.includes(c.pair_id)}
                className={`match-card${selCards.includes(c.id) ? ' sel' : ''}${donePairs.includes(c.pair_id) ? ' done' : ''}`}
                onClick={() => toggleCard(c.id, c.pair_id)}
                title={c.type === 'old' ? 'Eski so‘z' : 'Zamonaviy ma’no'}
              >
                {c.text}
              </button>
            ))}
          </div>
          {pairsCount > 0 && donePairs.length >= pairsCount && (
            <p className="badge green" style={{ marginTop: 8 }}>
              🏆 {t('success')}
            </p>
          )}
        </div>
      )}

      {/* Level picker — mirrors ?level= behaviour of all three game views. */}
      {isPlayableSlug(slug) && (
        <div className="toolbar">
          <select
            aria-label="Level"
            onChange={(e) => e.target.value && load(Number(e.target.value))}
            defaultValue=""
          >
            <option value="">{t('game_new_level_btn')}</option>
            {levels.map((l) => (
              <option key={l.id} value={l.id}>
                {l.title} (Lv.{l.difficulty})
              </option>
            ))}
          </select>
          <button className="btn" onClick={() => load()}>
            <RefreshIcon size={15} className="ico" /> {t('game_next_level')}
          </button>
        </div>
      )}
    </div>
  );
}
