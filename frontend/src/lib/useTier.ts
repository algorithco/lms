import { useEffect, useState } from 'react';
import { useAuth } from '../auth/AuthContext';
import { Billing, isPlatformAdmin, type BillingEntitlement } from './api';

export interface Tier {
  /** FREE | STARTER | PRO | PREMIUM | ADMIN — the server's single tier function, read from /me. */
  code: string;
  isAdmin: boolean;
  isPaid: boolean;
}

/**
 * Every "Tarif: …" label on screen reads the tier here. The value is the one
 * `/api/auth/me/` returns (`plan`, from `get_user_plan_tier` on the server);
 * no component derives a tier on its own.
 */
export function useTier(): Tier {
  const { user } = useAuth();
  if (!user) return { code: 'FREE', isAdmin: false, isPaid: false };
  if (isPlatformAdmin(user)) return { code: 'ADMIN', isAdmin: true, isPaid: true };
  const code = (user.plan || 'FREE').toUpperCase();
  return { code, isAdmin: false, isPaid: code !== 'FREE' };
}

let cache: { key: string; request: Promise<BillingEntitlement | null> } | null = null;

/** Real term and allowances (GET /billing/entitlement/), fetched once per account and plan. */
export function useEntitlement(): BillingEntitlement | null {
  const { user } = useAuth();
  const [ent, setEnt] = useState<BillingEntitlement | null>(null);
  const key = user ? `${user.id}:${user.plan}` : '';

  useEffect(() => {
    if (!key) return;
    let alive = true;
    if (!cache || cache.key !== key) cache = { key, request: Billing.entitlement().catch(() => null) };
    void cache.request.then((value) => alive && setEnt(value));
    return () => {
      alive = false;
    };
  }, [key]);

  return ent;
}

/** Whole days left until `iso` (never negative); null when there is no date. */
export function daysLeft(iso: string | null | undefined): number | null {
  if (!iso) return null;
  const ms = new Date(iso).getTime() - Date.now();
  return Number.isNaN(ms) ? null : Math.max(0, Math.ceil(ms / 86_400_000));
}
