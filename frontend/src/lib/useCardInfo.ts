import { useCallback, useEffect, useState } from 'react';
import { useAuth } from '../auth/AuthContext';
import { PaymentsApi, type ApiError } from './api';

export type CardStatus = 'loading' | 'ready' | 'login' | 'error';

export interface CardInfo {
  card_number: string;
  card_holder: string;
  starter_price: number;
  pro_price: number;
  premium_price: number;
}

/**
 * Payment card details come only from the server and only for a signed-in
 * user (the endpoint answers 401 to guests). Nothing is baked into the bundle,
 * so a guest can never see a card number, not even as a "fallback".
 */
export function useCardInfo(enabled = true) {
  const { user } = useAuth();
  const [info, setInfo] = useState<CardInfo | null>(null);
  const [status, setStatus] = useState<CardStatus>('loading');
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    if (!enabled) return;
    if (!user) {
      setInfo(null);
      setStatus('login');
      return;
    }
    let cancelled = false;
    setStatus('loading');
    PaymentsApi.cardInfo()
      .then((d) => {
        if (cancelled) return;
        if (!d?.card_number) {
          setStatus('error');
          return;
        }
        setInfo({
          card_number: d.card_number,
          card_holder: d.card_holder,
          starter_price: d.starter_price,
          pro_price: d.pro_price ?? d.plans?.pro.price ?? 0,
          premium_price: d.premium_price,
        });
        setStatus('ready');
      })
      .catch((e: ApiError) => {
        if (!cancelled) setStatus(e?.status === 401 ? 'login' : 'error');
      });
    return () => {
      cancelled = true;
    };
  }, [enabled, user, attempt]);

  const reload = useCallback(() => setAttempt((n) => n + 1), []);
  return { info, status, reload };
}
