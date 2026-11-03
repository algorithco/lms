import { useEffect, useState } from 'react';
import { LockIcon, XIcon, ZapIcon } from './icons';
import CardPaymentModal from './CardPaymentModal';
import { useAuth } from '../auth/AuthContext';
import { useLang } from '../i18n/LangContext';
import { isPlatformAdmin, PaymentsApi } from '../lib/api';

export type PaywallSubject = 'english' | 'uzbek' | 'attestation';

export interface PaywallTrial {
  /** e.g. "Reading · Part 1 (6 savol)" */
  label: string;
  used: boolean;
  onStart: () => void;
}

interface LimitExceededModalProps {
  isOpen: boolean;
  onClose: () => void;
  title?: string;
  /** Why the user hit the wall (server message); prices are added here. */
  message?: string;
  feature?: 'test' | 'essay' | 'arena' | 'general';
  /** Perks are listed for this subject only — never another subject's exam. */
  subject?: PaywallSubject;
  trial?: PaywallTrial | null;
}

const PERKS: Record<PaywallSubject, string[]> = {
  english: ['paywall_perk_en_mocks', 'paywall_perk_en_writing', 'paywall_perk_estimate'],
  uzbek: ['paywall_perk_uz_mocks', 'paywall_perk_uz_essay', 'paywall_perk_estimate'],
  attestation: ['paywall_perk_att_mocks', 'paywall_perk_analysis'],
};

type Prices = { starter: number; pro: number; premium: number };

const fmt = (n: number) => n.toLocaleString('ru-RU').replace(/ /g, ' ');

export default function LimitExceededModal({
  isOpen,
  onClose,
  title,
  message,
  feature = 'general',
  subject,
  trial,
}: LimitExceededModalProps) {
  const { user } = useAuth();
  const { t } = useLang();
  const [showPaymentModal, setShowPaymentModal] = useState(false);
  const [prices, setPrices] = useState<Prices | null>(null);

  useEffect(() => {
    if (!isOpen || prices) return;
    PaymentsApi.cardInfo()
      .then((d) =>
        setPrices({
          starter: d.starter_price,
          pro: d.pro_price ?? d.plans?.pro.price ?? 0,
          premium: d.premium_price,
        }),
      )
      .catch(() => setPrices(null));
  }, [isOpen, prices]);

  // Admins never hit paywalls or limits.
  if (isPlatformAdmin(user) || !isOpen) return null;

  if (showPaymentModal) {
    return (
      <CardPaymentModal
        isOpen={true}
        initialTariff="PRO"
        onClose={() => {
          setShowPaymentModal(false);
          onClose();
        }}
        onSuccess={() => {
          setShowPaymentModal(false);
          onClose();
        }}
      />
    );
  }

  const perks = subject ? PERKS[subject] : ['paywall_perk_analysis', 'paywall_perk_estimate'];
  const priceLine =
    prices && prices.starter && prices.pro
      ? t('paywall_prices')
          .replace('{starter}', fmt(prices.starter))
          .replace('{pro}', fmt(prices.pro))
          .replace('{premium}', fmt(prices.premium))
      : '';

  return (
    <div className="paywall-backdrop" role="dialog" aria-modal="true" aria-labelledby="paywall-title">
      <div className="paywall card">
        <button type="button" className="paywall-close" onClick={onClose} aria-label={t('paywall_close')}>
          <XIcon size={20} />
        </button>

        <div className="paywall-head">
          <span className="paywall-lock" aria-hidden>
            <LockIcon size={28} />
          </span>
          <h3 id="paywall-title">{title || t(`paywall_title_${feature}`, t('paywall_title_general'))}</h3>
          {message && <p className="muted">{message}</p>}
          {priceLine && <p className="paywall-prices">{priceLine}</p>}
        </div>

        <ul className="paywall-perks">
          {perks.map((k) => (
            <li key={k}>{t(k)}</li>
          ))}
        </ul>

        <div className="paywall-actions">
          {trial && !trial.used && (
            <button type="button" className="btn paywall-trial" onClick={trial.onStart}>
              {t('paywall_trial_start').replace('{part}', trial.label)}
            </button>
          )}
          {trial?.used && <p className="muted small">{t('paywall_trial_used')}</p>}
          <button type="button" className="btn primary" onClick={() => setShowPaymentModal(true)}>
            <ZapIcon size={18} />
            <span>{t('paywall_upgrade')}</span>
          </button>
          <button type="button" className="btn ghost" onClick={onClose}>
            {t('paywall_later')}
          </button>
        </div>
      </div>
    </div>
  );
}
