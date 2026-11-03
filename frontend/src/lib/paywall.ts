import type { PaywallSubject } from '../components/LimitExceededModal';

export type { PaywallSubject };

/** Which subject's perks the paywall lists for a test (never another subject's). */
export function paywallSubject(test: {
  subject?: string | null;
  title?: string | null;
  category_slug?: string | null;
}): PaywallSubject {
  if (test.subject === 'english') return 'english';
  if (test.category_slug === 'attestatsiya' || String(test.title ?? '').toLowerCase().includes('attestatsiya')) {
    return 'attestation';
  }
  return 'uzbek';
}

/** "B1: average ≥ 38/75" rule sent by the API for CEFR Multi-level tests. */
export interface CefrScaleRule {
  scale_max: number;
  level: string;
  min: number;
}
