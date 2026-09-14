/**
 * Shared domain helpers for the Billing + Admin Panel + Games stream.
 * Pure helpers only — no API calls, no routing. Keeps the page
 * components small and guarantees identical labels/rules everywhere.
 */

/** Backend game slugs (Game.GameType + webapi check_view). */
export const PLAYABLE_GAME_SLUGS = ['imlo_mina', 'gazal_puzzle', 'lugat_match'] as const;
export type PlayableGameSlug = (typeof PLAYABLE_GAME_SLUGS)[number];

/** All slugs the backend model defines (incl. non-playable ones). */
export const ALL_GAME_SLUGS = [
  'imlo_mina',
  'gazal_puzzle',
  'lugat_match',
  'arena_duel',
  'telegram_quiz',
] as const;

export function isPlayableSlug(slug: string): slug is PlayableGameSlug {
  return (PLAYABLE_GAME_SLUGS as readonly string[]).includes(slug);
}

/** Combo milestones — mirrors apps/games/views.py STREAK_MILESTONES. */
export const STREAK_MILESTONES: Record<number, string> = {
  3: '🔥 3x COMBO!',
  5: '⚡ 5x SUPER COMBO!',
  10: '🌟 10x LEGENDARY!',
};

export function milestoneFor(combo: number): string | null {
  let hit: string | null = null;
  for (const k of Object.keys(STREAK_MILESTONES).map(Number).sort((a, b) => a - b)) {
    if (combo >= k) hit = STREAK_MILESTONES[k];
  }
  return hit;
}

/** Question types — mirrors Question.QuestionType. */
export const QUESTION_TYPES = ['single', 'multiple', 'text'] as const;
export type QuestionType = (typeof QUESTION_TYPES)[number];

export function isQuestionType(v: string): v is QuestionType {
  return (QUESTION_TYPES as readonly string[]).includes(v);
}

export function num(v: unknown, fallback = 0): number {
  const n = Number(v);
  return Number.isFinite(n) ? n : fallback;
}

export function str(v: unknown, fallback = ''): string {
  if (v === null || v === undefined) return fallback;
  return String(v);
}

/** Format ISO date as dd.mm.yyyy hh:mm (legacy my_subscription table). */
export function formatDateTime(v: unknown): string {
  if (!v) return '—';
  const d = new Date(str(v));
  if (Number.isNaN(d.getTime())) return str(v);
  const p = (n: number) => String(n).padStart(2, '0');
  return `${p(d.getDate())}.${p(d.getMonth() + 1)}.${d.getFullYear()} ${p(d.getHours())}:${p(d.getMinutes())}`;
}

export function formatDate(v: unknown): string {
  if (!v) return '—';
  const d = new Date(str(v));
  if (Number.isNaN(d.getTime())) return str(v);
  const p = (n: number) => String(n).padStart(2, '0');
  return `${p(d.getDate())}.${p(d.getMonth() + 1)}.${d.getFullYear()}`;
}

/** Payment history status → translation key (legacy my_subscription.html). */
export function paymentStatusKey(status: unknown): string {
  const s = str(status);
  if (s === 'completed') return 'status_passed';
  if (s === 'pending') return 'pp_reviewing';
  if (s === 'failed') return 'status_failed';
  return '';
}

/** Plan price formatting — backend sends Decimal as string. */
export function price(v: unknown): string {
  const n = Number(v);
  if (!Number.isFinite(n)) return str(v, '0');
  return String(Math.round(n * 100) / 100);
}

export function isFreePlan(plan: Record<string, unknown>): boolean {
  return num(plan.price_monthly, 0) <= 0;
}

export function planEmoji(planType: unknown): string {
  const t = str(planType);
  if (t === 'premium') return '⭐';
  if (t === 'pro') return '🚀';
  if (t === 'starter') return '🌱';
  if (t === 'family') return '👨‍👩‍👧';
  return '💎';
}
