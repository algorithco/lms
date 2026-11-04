/**
 * Plan card lines, built only from the plan row the server returns
 * (GET /api/v1/billing/plans/). No limit or price is written in the UI:
 * an administrator changes a plan in the database and every card follows.
 */

export interface PlanLimits {
  test_limit?: number | null;
  is_unlimited_tests?: boolean;
  text_essay_weekly_limit?: number | null;
  is_unlimited_text_essays?: boolean;
  image_essay_weekly_limit?: number | null;
  is_unlimited_image_essays?: boolean;
  text_essay_cooldown_hours?: number | null;
  duration_days?: number | null;
}

/** One line on a card: an i18n key plus the number it needs (if any). */
export interface PlanLine {
  key: string;
  n?: number;
}

function quota(unlimited: boolean | undefined, limit: number | null | undefined, keys: [string, string, string]): PlanLine | null {
  const [unlimitedKey, countKey, noneKey] = keys;
  if (unlimited) return { key: unlimitedKey };
  if (typeof limit !== 'number') return null; // not configured: say nothing rather than guess
  if (limit <= 0) return { key: noneKey };
  return { key: countKey, n: limit };
}

export function planLines(plan: PlanLimits): PlanLine[] {
  const lines = [
    quota(plan.is_unlimited_tests, plan.test_limit, ['pl_tests_unlimited', 'pl_tests_week', 'pl_tests_none']),
    quota(plan.is_unlimited_text_essays, plan.text_essay_weekly_limit, [
      'pl_text_unlimited',
      'pl_text_week',
      'pl_text_none',
    ]),
    quota(plan.is_unlimited_image_essays, plan.image_essay_weekly_limit, [
      'pl_photo_unlimited',
      'pl_photo_week',
      'pl_photo_none',
    ]),
  ];
  const cooldown = plan.text_essay_cooldown_hours;
  if (!plan.is_unlimited_text_essays && typeof cooldown === 'number') {
    lines.push(cooldown > 0 ? { key: 'pl_cooldown', n: cooldown } : { key: 'pl_no_cooldown' });
  }
  if (typeof plan.duration_days === 'number' && plan.duration_days > 0) {
    lines.push({ key: 'pl_duration', n: plan.duration_days });
  }
  return lines.filter((l): l is PlanLine => l !== null);
}

/** "15 000": groups of three joined by non-breaking spaces, the same in every interface language. */
export function formatPrice(value: number | string | null | undefined): string {
  const n = Math.round(Number(value ?? 0));
  if (!Number.isFinite(n)) return '0';
  return String(n).replace(/\B(?=(\d{3})+(?!\d))/g, ' ');
}
